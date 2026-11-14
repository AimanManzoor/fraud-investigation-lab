"""Read-only, bounded queries against the typed PaySim database."""
import sqlite3
from contextlib import closing
from pathlib import Path

from src.money import MAX_INTEGER, to_minor_units

TYPES = ("CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER")


def format_amount(units):
    """Format scale-100 integer units without converting to float."""
    whole, fraction = divmod(units, 100)
    return f"{whole:,}.{fraction:02d}"


def explore(database, *, kind=None, step_min=1, step_max=None,
            amount_min="0", amount_max=None, fraud=None, legacy=None, limit=200):
    for value in (step_min, step_max):
        if value is not None and (
            type(value) is not int or not 1 <= value <= MAX_INTEGER
        ):
            raise ValueError("Steps must be positive integers within SQLite's range.")

    if step_max is not None and step_max < step_min:
        raise ValueError("Maximum step must be at least the minimum step.")

    if kind is not None and kind not in TYPES:
        raise ValueError("Unknown transaction type.")

    if any(
        value is not None and (type(value) is not int or value not in (0, 1))
        for value in (fraud, legacy)
    ):
        raise ValueError("Labels must be 0, 1, or unspecified.")

    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("Display limit must be between 1 and 500.")

    minimum = to_minor_units(amount_min)
    maximum = None if amount_max is None else to_minor_units(amount_max)

    if maximum is not None and maximum < minimum:
        raise ValueError("Maximum amount must be at least the minimum amount.")

    clauses = ["step >= ?", "amount_minor >= ?"]
    parameters = [step_min, minimum]

    for clause, value in (
        ("step <= ?", step_max),
        ("amount_minor <= ?", maximum),
        ("transaction_type = ?", kind),
        ("is_fraud = ?", fraud),
        ("legacy_flag = ?", legacy),
    ):
        if value is not None:
            clauses.append(clause)
            parameters.append(value)

    where = " WHERE " + " AND ".join(clauses)
    path = Path(database).resolve()

    if not path.is_file():
        raise FileNotFoundError("Typed database missing: data/fraud_typed.db")

    with closing(
        sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    ) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")

        groups = [
            dict(row)
            for row in connection.execute(
                "SELECT transaction_type, COUNT(*) AS records, "
                "SUM(is_fraud) AS fraud_labels, "
                "SUM(legacy_flag) AS legacy_flags "
                "FROM transactions" + where +
                " GROUP BY transaction_type ORDER BY transaction_type",
                parameters,
            )
        ]

        rows = []
        for row in connection.execute(
            "SELECT * FROM transactions" + where +
            " ORDER BY record_id LIMIT ?",
            parameters + [limit],
        ):
            record = dict(row)
            record["amount"] = format_amount(record.pop("amount_minor"))
            rows.append(record)

    return {
        "total": sum(group["records"] for group in groups),
        "fraud_labels": sum(group["fraud_labels"] for group in groups),
        "legacy_flags": sum(group["legacy_flags"] for group in groups),
        "groups": groups,
        "rows": rows,
    }
