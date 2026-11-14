"""Export a curated PaySim demo; query it without the full local database."""
import json
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from src.explorer import TYPES, explore
from src.money import MAX_INTEGER

COLUMNS = "record_id,step,transaction_type,amount_minor,origin_id,destination_id,is_fraud,legacy_flag"
SCHEMA = """CREATE TABLE transactions (
record_id INTEGER PRIMARY KEY, step INTEGER, transaction_type TEXT,
amount_minor INTEGER, origin_id TEXT, destination_id TEXT,
is_fraud INTEGER, legacy_flag INTEGER)"""
NOTICE = (
    "Curated demo: up to 500 earliest records per transaction type, plus up to "
    "100 fraud-labeled and 100 legacy-flagged examples; duplicate record IDs "
    "are included once. This sample is not representative and must not be "
    "used to estimate population fraud rates or model performance."
)


def export_demo(database, output):
    database, output = Path(database).resolve(), Path(output).resolve()
    if not database.is_file():
        raise FileNotFoundError("The full typed database is missing.")
    if output == database:
        raise ValueError("Sample output must differ from the source database.")

    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("BEGIN")
        selected = {}

        for kind in TYPES:
            for row in connection.execute(
                "SELECT " + COLUMNS + " FROM transactions WHERE transaction_type=? "
                "ORDER BY record_id LIMIT 500", (kind,),
            ):
                selected[row[0]] = list(row)

        for label in ("is_fraud", "legacy_flag"):
            for row in connection.execute(
                "SELECT " + COLUMNS + " FROM transactions WHERE " + label +
                "=1 ORDER BY record_id LIMIT 100"
            ):
                selected[row[0]] = list(row)

        provenance = json.loads(connection.execute(
            "SELECT report_json FROM build_metadata LIMIT 1"
        ).fetchone()[0])

    if not selected:
        raise ValueError("The source contains no transactions.")

    payload = {
        "format_version": 1,
        "source": "https://www.kaggle.com/datasets/ealaxi/paysim1",
        "license": "https://creativecommons.org/licenses/by-sa/4.0/",
        "source_csv_sha256": provenance["source_csv_sha256"],
        "notice": NOTICE,
        "columns": COLUMNS.split(","),
        "rows": [selected[key] for key in sorted(selected)],
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
        handle.write("\n")

    return {
        "sample_records": len(selected),
        "output": str(output),
        "notice": NOTICE,
    }


def explore_demo(sample, **filters):
    path = Path(sample)
    if not path.is_file():
        raise FileNotFoundError("Demo sample missing: demo/transactions.json")
    if path.stat().st_size > 5_000_000:
        raise ValueError("Demo sample exceeds the supported size.")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("format_version") != 1 or
        payload.get("columns") != COLUMNS.split(",")
    ):
        raise ValueError("Unsupported demo sample format.")

    rows = payload.get("rows")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 2700:
        raise ValueError("Demo sample must contain 1 to 2700 records.")

    seen = set()
    for row in rows:
        if not isinstance(row, list) or len(row) != 8:
            raise ValueError("Invalid demo record.")

        rid, step, kind, amount, origin, destination, fraud, legacy = row
        if (
            any(
                type(value) is not int or not 1 <= value <= MAX_INTEGER
                for value in (rid, step)
            ) or
            type(amount) is not int or not 0 <= amount <= MAX_INTEGER or
            kind not in TYPES or
            any(
                not isinstance(value, str) or not value.strip()
                for value in (origin, destination)
            ) or
            any(
                type(value) is not int or value not in (0, 1)
                for value in (fraud, legacy)
            ) or
            rid in seen
        ):
            raise ValueError("Invalid demo record values or repeated record ID.")
        seen.add(rid)

    with tempfile.TemporaryDirectory(prefix="fraud-demo-") as directory:
        database = Path(directory) / "sample.db"
        with closing(sqlite3.connect(database)) as connection:
            with connection:
                connection.execute(SCHEMA)
                connection.executemany(
                    "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)", rows
                )
        return explore(database, **filters)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    print("Exporting the curated demo sample...", flush=True)
    print(json.dumps(export_demo(
        root / "data/fraud_typed.db",
        root / "demo/transactions.json",
    ), indent=2))
