"""Conversion between the API's two-decimal money strings and integer cents.

Money is always an ``int`` number of cents internally (Constitution II). Parsing works on
the string directly, so no binary floating point is ever involved.
"""

import re

MIN_EXPENSE_CENTS = 1
MAX_EXPENSE_CENTS = 100_000_000_000  # 1,000,000,000.00

_MONEY_RE = re.compile(r"(0|[1-9][0-9]*)\.([0-9]{2})", re.ASCII)


class MoneyFormatError(ValueError):
    pass


def parse_money(text: str) -> int:
    """Parse a non-negative amount like ``"10.00"`` into cents; reject anything else."""
    if not isinstance(text, str):
        raise MoneyFormatError("amount must be a string with exactly two decimals, e.g. \"10.00\"")
    match = _MONEY_RE.fullmatch(text)
    if match is None:
        raise MoneyFormatError(f"invalid amount {text!r}: expected exactly two decimals, e.g. \"10.00\"")
    whole, frac = match.groups()
    return int(whole) * 100 + int(frac)


def format_money(cents: int) -> str:
    """Format cents as a two-decimal string, e.g. ``-333`` -> ``"-3.33"``."""
    whole, frac = divmod(abs(cents), 100)
    sign = "-" if cents < 0 else ""
    return f"{sign}{whole}.{frac:02d}"
