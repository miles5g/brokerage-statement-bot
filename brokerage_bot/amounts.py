"""Whole-dollar parsing and formatting for the demo."""

from __future__ import annotations

import re
from typing import Any


class AmountError(ValueError):
    """Raised when a value is not a round whole-dollar integer."""


def parse_whole_dollars(value: Any, *, field: str = "amount") -> int:
    """Parse a value that must be a round whole-dollar integer.

    Accepts 1000, "1000", "$1,000", "(1000)" for negatives, and integer-valued
    floats such as 1000.0. Rejects cents and empty values.
    """
    if value is None:
        raise AmountError(f"{field} is missing; demo requires whole dollars")

    if isinstance(value, bool):
        raise AmountError(f"{field} must be a whole-dollar amount, not a boolean")

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if not value.is_integer():
            raise AmountError(
                f"{field}={value!r} has cents; demo allows round dollars only"
            )
        return int(value)

    text = str(value).strip()
    if text == "":
        raise AmountError(f"{field} is blank; demo requires whole dollars")

    if re.search(r"[.]\d*[1-9]", text):
        raise AmountError(
            f"{field}={value!r} has cents; demo allows round dollars only"
        )

    compact = text.replace(" ", "")
    if compact.startswith("(") and compact.endswith(")"):
        compact = "-" + compact[1:-1]

    compact = compact.replace("$", "").replace(",", "")
    if compact.endswith(".0") or compact.endswith(".00"):
        compact = compact.rsplit(".", 1)[0]

    try:
        number = int(compact)
    except ValueError as exc:
        raise AmountError(
            f"{field}={value!r} is not a whole-dollar integer"
        ) from exc
    return number


def parse_optional_whole_dollars(value: Any, *, field: str = "amount") -> int | None:
    """Parse a whole-dollar amount, returning None when the cell is empty."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return parse_whole_dollars(value, field=field)


def format_dollars(amount: int) -> str:
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,}"
