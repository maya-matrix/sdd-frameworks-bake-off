"""Exact money arithmetic. Amounts are always integers in a Currency's minor units (ADR 0002)."""

# ISO 4217 codes whose minor unit is exactly 2 decimal places. Currencies with 0 or 3
# decimals (JPY, KWD, ...) are deliberately unsupported.
SUPPORTED_CURRENCIES = frozenset(
    {
        "AUD", "BGN", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "GBP",
        "HKD", "ILS", "INR", "MXN", "NOK", "NZD", "PLN", "RON", "SEK", "SGD",
        "THB", "TRY", "USD", "ZAR",
    }
)  # fmt: skip

# Largest Amount we can store exactly (SQLite INTEGER is a signed 64-bit value).
MAX_AMOUNT = 2**63 - 1


def split_equally(amount: int, participant_ids: list[str]) -> list[tuple[str, int]]:
    """Split an Amount into whole-minor-unit Shares that add up exactly to it.

    `participant_ids` must already be in join order: the Remainder goes one minor unit
    each to the earliest-joined Participants (ADR 0002).
    """
    base, remainder = divmod(amount, len(participant_ids))
    return [
        (member_id, base + (1 if i < remainder else 0))
        for i, member_id in enumerate(participant_ids)
    ]
