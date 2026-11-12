import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from src.money import SCALE, to_minor_units
from src.validation import numeric_issue

TYPES = {"CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"}
SELECT_RAW = (
    'SELECT record_id, step, "type", amount, nameOrig, nameDest, '
    'isFraud, isFlaggedFraud FROM raw_transactions ORDER BY record_id'
)


def convert_record(row):
    record_id, step, kind, amount, origin, destination, fraud, flagged = row

    if numeric_issue(step, integer=True) != "valid":
        raise ValueError("Invalid step.")
    if kind not in TYPES:
        raise ValueError("Unknown transaction type.")
    if any(
        not isinstance(value, str) or not value.strip()
        for value in (origin, destination)
    ):
        raise ValueError("Missing account identifier.")
    if fraud not in ("0", "1") or flagged not in ("0", "1"):
        raise ValueError("Invalid fraud or legacy-flag label.")

    return (
        record_id, int(step), kind, to_minor_units(amount),
        origin, destination, int(fraud), int(flagged)
    )


def build_typed(source, destination):
    source = Path(source).resolve()
    destination = Path(destination).resolve()

    if source == destination:
        raise ValueError("Source and destination must differ.")
    if not source.is_file():
        raise FileNotFoundError("Raw database is missing.")
    if destination.exists():
        raise FileExistsError("Typed database already exists; nothing overwritten.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".building")

    with temporary.open("x"):
        pass

    try:
        with (
            closing(sqlite3.connect(
                source.as_uri() + "?mode=ro", uri=True
            )) as raw,
            closing(sqlite3.connect(temporary)) as typed,
        ):
            raw.execute("BEGIN")
            expected = raw.execute(
                "SELECT COUNT(*) FROM raw_transactions"
            ).fetchone()[0]

            if not expected:
                raise ValueError("Raw table is empty.")

            provenance = json.loads(raw.execute(
                "SELECT report_json FROM ingestion_metadata LIMIT 1"
            ).fetchone()[0])

            with typed:
                typed.execute("""CREATE TABLE transactions (
                    record_id INTEGER PRIMARY KEY,
                    step INTEGER NOT NULL CHECK(step >= 1),
                    transaction_type TEXT NOT NULL,
                    amount_minor INTEGER NOT NULL CHECK(amount_minor >= 0),
                    origin_id TEXT NOT NULL,
                    destination_id TEXT NOT NULL,
                    is_fraud INTEGER NOT NULL CHECK(is_fraud IN (0,1)),
                    legacy_flag INTEGER NOT NULL CHECK(legacy_flag IN (0,1))
                )""")

                reader = raw.execute(SELECT_RAW)
                loaded = 0

                while batch := reader.fetchmany(5000):
                    converted = []
                    for row in batch:
                        try:
                            converted.append(convert_record(row))
                        except ValueError as error:
                            raise ValueError(
                                f"Record {row[0]}: {error}"
                            ) from error

                    typed.executemany(
                        "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)",
                        converted,
                    )
                    loaded += len(converted)

                    if loaded % 500000 == 0:
                        print(f"Converted {loaded:,} records...", flush=True)

                actual = typed.execute(
                    "SELECT COUNT(*) FROM transactions"
                ).fetchone()[0]

                if actual != expected or loaded != expected:
                    raise RuntimeError("Source and typed record counts differ.")

                print("Creating query indexes...", flush=True)
                typed.execute(
                    "CREATE INDEX transactions_step_idx ON transactions(step)"
                )
                typed.execute(
                    "CREATE INDEX transactions_type_idx "
                    "ON transactions(transaction_type)"
                )

                report = {
                    "built_at_utc": datetime.now(timezone.utc).isoformat(),
                    "source_csv_sha256": provenance["source_sha256"],
                    "source_records": expected,
                    "typed_records": actual,
                    "money_scale": SCALE,
                    "notes": [
                        "Raw database unchanged; no rows removed or deduplicated.",
                        "Only amount is converted to minor units; balances remain in raw data.",
                        "Fraud labels and legacy flags are retained for evaluation, not prediction inputs.",
                    ],
                }

                typed.execute(
                    "CREATE TABLE build_metadata (report_json TEXT NOT NULL)"
                )
                typed.execute(
                    "INSERT INTO build_metadata VALUES (?)",
                    (json.dumps(report),),
                )

        if destination.exists():
            raise FileExistsError("Destination appeared during the build; stopped.")

        temporary.rename(destination)
    finally:
        temporary.unlink(missing_ok=True)

    return report


def main():
    root = Path(__file__).resolve().parents[1]
    report = build_typed(
        root / "data/fraud_lab.db",
        root / "data/fraud_typed.db",
    )
    output = root / "reports/generated/typed_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    print("Report saved:", output)


if __name__ == "__main__":
    main()
