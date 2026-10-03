"""Equal splitting of an amount in integer cents.

This is the only place where money is divided (the named allocation step required by the
constitution's Money Handling Constraints).
"""


def split_equally(amount_cents: int, n: int) -> list[int]:
    """Split ``amount_cents`` into ``n`` shares that sum exactly to the amount.

    Each share is the amount divided by ``n`` rounded down to the cent; the leftover cents
    go one each to the earliest participants.
    """
    if n < 1:
        raise ValueError("at least one participant is required")
    if amount_cents < 1:
        raise ValueError("amount must be at least one cent")
    base, remainder = divmod(amount_cents, n)
    return [base + 1 if i < remainder else base for i in range(n)]
