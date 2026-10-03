"""Exact money handling: amounts travel as decimal strings and live as integer cents."""

import re

MAX_AMOUNT_CENTS = 100_000_000_000  # 1,000,000,000.00
_MAX_AMOUNT_LENGTH = 20
_AMOUNT_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]{1,2})?")


def parse_amount(value: object) -> int:
    """Parse a positive decimal string such as "12.34" into integer cents."""
    if (
        not isinstance(value, str)
        or len(value) > _MAX_AMOUNT_LENGTH
        or not _AMOUNT_PATTERN.fullmatch(value)
    ):
        raise ValueError('amount must be a decimal string with at most 2 decimal places, e.g. "12.34"')
    whole, _, fraction = value.partition(".")
    cents = int(whole) * 100 + int(fraction.ljust(2, "0"))
    if cents <= 0:
        raise ValueError("amount must be greater than 0")
    if cents > MAX_AMOUNT_CENTS:
        raise ValueError("amount must not exceed 1000000000.00")
    return cents


def format_cents(cents: int) -> str:
    """Format integer cents as a decimal string, e.g. -333 -> "-3.33"."""
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{sign}{whole}.{fraction:02d}"
