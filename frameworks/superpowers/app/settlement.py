"""Suggest the fewest transfers that bring every balance to zero."""

from collections.abc import Mapping
from dataclasses import dataclass

EXACT_LIMIT = 20

Entry = tuple[int, int]  # (member_id, balance_cents)


@dataclass(frozen=True)
class Transfer:
    from_member_id: int
    to_member_id: int
    amount_cents: int


def minimize_transfers(balances: Mapping[int, int]) -> tuple[list[Transfer], bool]:
    """Return (transfers, optimal). Positive balance = is owed, negative = owes.

    Exact for up to EXACT_LIMIT non-zero balances; above that a greedy
    settlement is returned with optimal=False.
    """
    if sum(balances.values()) != 0:
        raise ValueError("balances must sum to zero")
    entries = sorted((member_id, cents) for member_id, cents in balances.items() if cents != 0)
    if len(entries) > EXACT_LIMIT:
        return _ordered(_settle_greedily(entries)), False
    transfers: list[Transfer] = []
    for group in _max_zero_sum_partition(entries):
        transfers.extend(_settle_greedily(group))
    return _ordered(transfers), True


def _ordered(transfers: list[Transfer]) -> list[Transfer]:
    return sorted(transfers, key=lambda t: (t.from_member_id, t.to_member_id))


def _settle_greedily(entries: list[Entry]) -> list[Transfer]:
    """Largest debtor pays largest creditor until everyone is even (ties: lowest id)."""
    debts = {member_id: -cents for member_id, cents in entries if cents < 0}
    credits = {member_id: cents for member_id, cents in entries if cents > 0}
    transfers = []
    while debts:
        debtor = max(debts, key=lambda m: (debts[m], -m))
        creditor = max(credits, key=lambda m: (credits[m], -m))
        amount = min(debts[debtor], credits[creditor])
        transfers.append(Transfer(debtor, creditor, amount))
        debts[debtor] -= amount
        credits[creditor] -= amount
        if debts[debtor] == 0:
            del debts[debtor]
        if credits[creditor] == 0:
            del credits[creditor]
    return transfers


def _max_zero_sum_partition(entries: list[Entry]) -> list[list[Entry]]:
    """Split entries (summing to zero) into the most possible zero-sum groups."""
    count = len(entries)
    if count == 0:
        return []
    values = [cents for _, cents in entries]
    full = (1 << count) - 1
    sums = [0] * (full + 1)
    best = [0] * (full + 1)
    for mask in range(1, full + 1):
        low = mask & -mask
        sums[mask] = sums[mask ^ low] + values[low.bit_length() - 1]
        most = 0
        rest = mask
        while rest:
            bit = rest & -rest
            if best[mask ^ bit] > most:
                most = best[mask ^ bit]
            rest ^= bit
        best[mask] = most + (1 if sums[mask] == 0 else 0)

    # Walk back from the full set, recovering an order of elements whose
    # zero-sum prefixes are exactly the groups of an optimal partition.
    order = []
    mask = full
    while mask:
        target = best[mask] - (1 if sums[mask] == 0 else 0)
        rest = mask
        while best[mask ^ (rest & -rest)] != target:
            rest ^= rest & -rest
        bit = rest & -rest
        order.append(bit.bit_length() - 1)
        mask ^= bit
    order.reverse()

    groups: list[list[Entry]] = []
    current: list[Entry] = []
    running = 0
    for index in order:
        current.append(entries[index])
        running += values[index]
        if running == 0:
            groups.append(current)
            current = []
    return groups
