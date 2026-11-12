"""Exact conversion of raw monetary text to integer units at a scale of 100."""
from decimal import Decimal

from src.validation import numeric_issue

SCALE = 100
MAX_INTEGER = 9223372036854775807


def to_minor_units(value):
    if not isinstance(value, str):
        raise ValueError("Money must be supplied as raw text.")

    issue = numeric_issue(value)
    if issue != "valid":
        raise ValueError("Invalid monetary value: " + issue)

    numerator, denominator = Decimal(value.strip()).as_integer_ratio()
    units, remainder = divmod(numerator * SCALE, denominator)

    if remainder:
        raise ValueError(
            "Amount is not exactly representable at a scale of 100."
        )

    if units > MAX_INTEGER:
        raise ValueError("Amount exceeds SQLite's integer range.")

    return units
