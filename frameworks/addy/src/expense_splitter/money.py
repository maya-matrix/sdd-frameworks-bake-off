"""Exact money handling: decimal strings at the boundary, integer cents everywhere else."""

import re

Cents = int

MAX_AMOUNT_CENTS: Cents = 100_000_000_000  # 1,000,000,000.00

_AMOUNT_PATTERN = re.compile(r"([0-9]+)(?:\.([0-9]{1,2}))?")


def parse_amount(text: str) -> Cents:
    """Parse a positive decimal string such as "10.5" into cents (1050), without floats."""
    match = _AMOUNT_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError("amount must be a decimal string with at most 2 decimal places")
    units, fraction = match.groups()
    cents = int(units) * 100 + int((fraction or "").ljust(2, "0"))
    if cents <= 0:
        raise ValueError("amount must be greater than 0")
    if cents > MAX_AMOUNT_CENTS:
        raise ValueError("amount must not exceed 1000000000.00")
    return cents


def format_cents(cents: Cents) -> str:
    """Format cents as a decimal string with exactly two decimals, e.g. -333 -> "-3.33"."""
    sign = "-" if cents < 0 else ""
    units, remainder = divmod(abs(cents), 100)
    return f"{sign}{units}.{remainder:02d}"
