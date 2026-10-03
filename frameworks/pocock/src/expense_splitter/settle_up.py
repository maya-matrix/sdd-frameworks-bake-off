"""Settle-up: the fewest Suggested Transfers that bring every Balance to zero (ADR 0001)."""

from collections.abc import Sequence
from dataclasses import dataclass

# Above this many non-zero Balances the exact search (O(2^n * n)) gets too slow, so we
# fall back to greedy, which is guaranteed at most n-1 transfers but may not be minimal.
EXACT_LIMIT = 16


@dataclass(frozen=True)
class Transfer:
    from_id: str
    to_id: str
    amount: int


@dataclass(frozen=True)
class SettleUpResult:
    transfers: list[Transfer]
    optimal: bool


def settle_up(balances: Sequence[tuple[str, int]]) -> SettleUpResult:
    """Suggest transfers for (member_id, Balance) pairs that sum to zero.

    The order of `balances` is the stable Member ordering used to break ties.
    """
    nonzero = [(member_id, balance) for member_id, balance in balances if balance != 0]
    if len(nonzero) > EXACT_LIMIT:
        return SettleUpResult(transfers=_greedy(nonzero), optimal=False)
    transfers = [t for group in _zero_sum_groups(nonzero) for t in _greedy(group)]
    return SettleUpResult(transfers=transfers, optimal=True)


def _zero_sum_groups(balances: Sequence[tuple[str, int]]) -> list[list[tuple[str, int]]]:
    """Partition the Balances into as many zero-sum groups as possible.

    A group of k Members can always be settled in k-1 transfers and no fewer, so the
    minimum number of transfers is n minus the maximum number of groups.
    `best[mask]` is the most zero-sum groups that the Members in `mask` can be
    partitioned into, counting only the complete groups.
    """
    n = len(balances)
    size = 1 << n
    total = [0] * size
    best = [0] * size
    for mask in range(1, size):
        low = (mask & -mask).bit_length() - 1
        total[mask] = total[mask ^ (1 << low)] + balances[low][1]
        best[mask] = max(best[mask ^ (1 << i)] for i in range(n) if mask >> i & 1) + (
            total[mask] == 0
        )

    # Walk back from the full set, peeling off one Member at a time along an optimal
    # path. Each time we reach a zero-sum set, the Members peeled since the last one
    # form a zero-sum group.
    groups: list[list[tuple[str, int]]] = []
    mask = size - 1
    current: list[int] = []
    while mask:
        target = best[mask] - (total[mask] == 0)
        i = next(i for i in range(n) if mask >> i & 1 and best[mask ^ (1 << i)] == target)
        current.append(i)
        mask ^= 1 << i
        if total[mask] == 0:
            groups.append([balances[j] for j in sorted(current)])
            current = []
    groups.reverse()
    return groups


def _greedy(balances: Sequence[tuple[str, int]]) -> list[Transfer]:
    """Repeatedly match the largest debtor with the largest creditor (ties: stable order)."""
    remaining = {member_id: balance for member_id, balance in balances}
    rank = {member_id: i for i, (member_id, _) in enumerate(balances)}
    transfers: list[Transfer] = []
    while any(remaining.values()):
        creditor = max(remaining, key=lambda m: (remaining[m], -rank[m]))
        debtor = min(remaining, key=lambda m: (remaining[m], rank[m]))
        amount = min(remaining[creditor], -remaining[debtor])
        transfers.append(Transfer(from_id=debtor, to_id=creditor, amount=amount))
        remaining[creditor] -= amount
        remaining[debtor] += amount
    return transfers
