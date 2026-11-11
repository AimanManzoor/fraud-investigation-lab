import csv
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ["step", "type", "amount", "nameOrig", "oldbalanceOrg",
          "newbalanceOrig", "nameDest", "oldbalanceDest", "newbalanceDest",
          "isFraud", "isFlaggedFraud"]


def ingest(source, database, report_path):
    source, database, report_path = map(Path, (source, database, report_path))
    if database.exists():
        raise FileExistsError("Database already exists; no data was overwritten.")
    if len({source.resolve(), database.resolve(), report_path.resolve()}) != 3:
        raise ValueError("Input and output paths must be different.")

    database.parent.mkdir(parents=True, exist_ok=True)
    temporary = database.with_name(database.name + ".building")
    with temporary.open("x"):
        pass

    try:
        fingerprint = hashlib.sha256()
        before = source.stat()
        with source.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                fingerprint.update(block)

        with closing(sqlite3.connect(temporary)) as connection:
            with connection:
                definition = ", ".join(f'"{name}" TEXT' for name in FIELDS)
                connection.execute("CREATE TABLE raw_transactions "
                                   f"(record_id INTEGER PRIMARY KEY, {definition})")
                placeholders = ",".join("?" for _ in range(len(FIELDS) + 1))
                statement = f"INSERT INTO raw_transactions VALUES ({placeholders})"
                count, batch = 0, []

                with source.open(newline="", encoding="utf-8-sig") as handle:
                    reader = csv.reader(handle, strict=True)
                    if next(reader, None) != FIELDS:
                        raise ValueError("CSV header does not match the expected PaySim schema.")

                    for count, row in enumerate(reader, start=1):
                        if len(row) != len(FIELDS):
                            raise ValueError(f"Wrong column count in data record {count}.")
                        batch.append((count, *row))

                        if len(batch) == 5000:
                            connection.executemany(statement, batch)
                            batch.clear()

                        if count % 500000 == 0:
                            print(f"Read {count:,} records...", flush=True)

                    if batch:
                        connection.executemany(statement, batch)

                if not count:
                    raise ValueError("CSV contains no transaction records.")

                after = source.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError("CSV changed during ingestion.")

                actual = connection.execute(
                    "SELECT COUNT(*) FROM raw_transactions"
                ).fetchone()[0]

                if actual != count:
                    raise RuntimeError("CSV and database row counts do not match.")

                print("Running SQL quality checks...", flush=True)
                expressions = [
                    f'SUM(CASE WHEN "{name}" IS NULL OR TRIM("{name}") = \'\' '
                    'THEN 1 ELSE 0 END)' for name in FIELDS
                ]
                blanks = connection.execute(
                    "SELECT " + ",".join(expressions) + " FROM raw_transactions"
                ).fetchone()

                labels, invalid_labels = {}, {}
                for name in ("isFraud", "isFlaggedFraud"):
                    labels[name] = dict(connection.execute(
                        f'SELECT "{name}", COUNT(*) FROM raw_transactions GROUP BY "{name}"'
                    ))
                    invalid_labels[name] = connection.execute(
                        f'SELECT COUNT(*) FROM raw_transactions WHERE "{name}" IS NULL '
                        f'OR "{name}" NOT IN (\'0\', \'1\')'
                    ).fetchone()[0]

                report = {
                    "source_file": source.name,
                    "source_sha256": fingerprint.hexdigest(),
                    "loaded_at_utc": datetime.now(timezone.utc).isoformat(),
                    "csv_records": count,
                    "sqlite_records": actual,
                    "blank_or_space_counts": dict(zip(FIELDS, blanks)),
                    "label_counts": labels,
                    "invalid_label_counts": invalid_labels,
                    "transaction_type_counts": dict(connection.execute(
                        'SELECT "type", COUNT(*) FROM raw_transactions GROUP BY "type"'
                    )),
                    "pending_checks": ["numeric types and ranges", "duplicate candidates"],
                }

                connection.execute(
                    "CREATE TABLE ingestion_metadata (report_json TEXT NOT NULL)"
                )
                connection.execute(
                    "INSERT INTO ingestion_metadata VALUES (?)",
                    (json.dumps(report),)
                )

        if database.exists():
            raise FileExistsError("Database was created by another process; stopped.")
        temporary.rename(database)
    finally:
        temporary.unlink(missing_ok=True)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    root = Path(__file__).resolve().parents[1]
    files = sorted((root / "data/raw").glob("*.csv"))
    if len(files) != 1:
        raise SystemExit("Expected exactly one CSV in data/raw/.")

    database = root / "data/fraud_lab.db"
    report_path = root / "reports/generated/ingestion_report.json"

    print("Importing CSV into a new SQLite database...", flush=True)
    report = ingest(files[0], database, report_path)
    print(json.dumps(report, indent=2))
    print("Database:", database)
    print("Report:", report_path)


if __name__ == "__main__":
    main()
