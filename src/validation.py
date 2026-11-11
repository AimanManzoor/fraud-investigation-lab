import math
import re
from decimal import Decimal, InvalidOperation

NUMBER = re.compile(
    r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
)
INTEGER = re.compile(r"[0-9]+")


def numeric_issue(value, *, integer=False):
    text = "" if value is None else str(value).strip()

    if not text:
        return "missing"

    try:
        number = Decimal(text)
    except InvalidOperation:
        return "not_numeric"

    if not number.is_finite():
        return "non_finite"

    if not NUMBER.fullmatch(text):
        return "invalid_format"

    if number < 0:
        return "negative"

    if integer:
        if not INTEGER.fullmatch(text):
            return "not_integer_literal"
        if not 1 <= number <= 9223372036854775807:
            return "out_of_range"
    else:
        converted = float(number)
        if not math.isfinite(converted):
            return "out_of_range"
        if number != 0 and converted == 0:
            return "out_of_range"

    return "valid"
