import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from src.validation import numeric_issue

FIELDS = ["step", "amount", "oldbalanceOrg", "newbalanceOrig",
          "oldbalanceDest", "newbalanceDest"]


def audit_numeric(database):
    database = Path(database).resolve()
    if not database.is_file():
        raise FileNotFoundError("Database missing. Run ingestion first.")

    validator = Path(__file__).with_name("validation.py")

    with closing(sqlite3.connect(
        database.as_uri() + "?mode=ro", uri=True
    )) as connection:
        connection.create_function(
            "numeric_issue",
            2,
            lambda value, integer: numeric_issue(
                value, integer=bool(integer)
            ),
            deterministic=True,
        )

        connection.execute("BEGIN")
        columns = {
            row[1] for row in connection.execute(
                "PRAGMA table_info(raw_transactions)"
            )
        }
        missing = set(FIELDS) - columns
        if missing:
            raise ValueError(
                "Missing columns: " + ", ".join(sorted(missing))
            )

        total = connection.execute(
            "SELECT COUNT(*) FROM raw_transactions"
        ).fetchone()[0]

        results = {}
        for name in FIELDS:
            print("Checking column:", name, flush=True)
            counts = dict(connection.execute(
                f'SELECT numeric_issue("{name}", ?) AS issue, COUNT(*) '
                'FROM raw_transactions GROUP BY issue ORDER BY issue',
                (int(name == "step"),),
            ))

            if sum(counts.values()) != total:
                raise RuntimeError("Audit record count mismatch.")

            results[name] = {
                "valid": counts.get("valid", 0),
                "invalid": sum(
                    count for issue, count in counts.items()
                    if issue != "valid"
                ),
                "issue_counts": counts,
            }

    invalid_cells = sum(
        result["invalid"] for result in results.values()
    )
    status = (
        "empty" if total == 0
        else "issues_found" if invalid_cells
        else "passed"
    )

    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "validator_sha256": hashlib.sha256(
            validator.read_bytes()
        ).hexdigest(),
        "rows_checked": total,
        "numeric_status": status,
        "invalid_cells": invalid_cells,
        "columns": results,
        "notes": [
            "Invalid cells are counted per column, not as distinct transactions.",
            "Passed means these numeric rules passed; it does not certify all data quality.",
            "Raw values were not converted and no records were removed.",
            "Monetary precision, duplicate assessment and domain-specific checks remain pending.",
        ],
    }


def main():
    root = Path(__file__).resolve().parents[1]
    report = audit_numeric(root / "data/fraud_lab.db")

    output = root / "reports/generated/numeric_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, indent=2))
    print("Report saved:", output)


if __name__ == "__main__":
    main()
