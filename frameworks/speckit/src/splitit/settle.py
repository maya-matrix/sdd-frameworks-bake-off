"""Minimum-transfer settle-up (research §4).

With ``k`` nonzero balances, the fewest transfers that clear them is ``k - p``, where ``p``
is the largest number of disjoint zero-sum groups the members can be partitioned into: a
group of ``g`` members settles with ``g - 1`` transfers and no fewer. ``p`` is found with a
dynamic program over subsets::

    dp[mask] = max(dp[mask without i] for i in mask) + (sum(mask) == 0)

Walking back from the full set along that recurrence visits a chain of zero-sum masks whose
consecutive differences are the zero-sum groups. Each group is then settled greedily.

The DP is vectorized with NumPy on integer subset sums (never floats). If the balances are
too large for ``int64`` the same DP runs on Python integers instead, so the result is exact
either way.
"""

from collections.abc import Sequence

import numpy as np

from splitit.models import Transfer

# Every subset sum is bounded by the sum of absolute balances; keep it well inside int64.
_INT64_SAFE_LIMIT = 2**62


def minimum_transfers(balances: dict[str, int]) -> list[Transfer]:
    """Return the fewest transfers that bring every balance to exactly zero.

    ``balances`` maps member id to integer cents (positive = is owed) and must sum to zero.
    Transfers are ordered by the debtor's position in ``balances``, then the creditor's.
    """
    if sum(balances.values()) != 0:
        raise ValueError("balances must sum to zero")
    order = {member_id: index for index, member_id in enumerate(balances)}
    ids = [member_id for member_id, value in balances.items() if value != 0]
    values = [balances[member_id] for member_id in ids]

    transfers: list[Transfer] = []
    for group in _zero_sum_groups(values):
        transfers.extend(_settle_group({ids[i]: values[i] for i in group}))
    transfers.sort(key=lambda t: (order[t.from_member_id], order[t.to_member_id]))
    return transfers


def _zero_sum_groups(values: Sequence[int], use_numpy: bool | None = None) -> list[list[int]]:
    """Partition indices of ``values`` (which sum to zero) into the most zero-sum groups."""
    k = len(values)
    if k == 0:
        return []
    if use_numpy is None:
        use_numpy = sum(abs(v) for v in values) < _INT64_SAFE_LIMIT
    dp, is_zero = _dp_numpy(values) if use_numpy else _dp_python(values)

    groups: list[list[int]] = []
    mask = (1 << k) - 1
    current: list[int] = []
    while mask:
        target = int(dp[mask]) - int(is_zero[mask])
        if is_zero[mask] and current:
            groups.append(current)
            current = []
        for i in range(k):
            bit = 1 << i
            if mask & bit and int(dp[mask ^ bit]) == target:
                current.append(i)
                mask ^= bit
                break
    groups.append(current)
    return [sorted(group) for group in reversed(groups)]


def _dp_numpy(values: Sequence[int]) -> tuple[np.ndarray, np.ndarray]:
    k = len(values)
    masks = np.arange(1 << k, dtype=np.int64)
    sums = np.zeros(1 << k, dtype=np.int64)
    popcount = np.zeros(1 << k, dtype=np.int8)
    for i, value in enumerate(values):
        has_bit = (masks >> i) & 1
        sums += has_bit * np.int64(value)
        popcount += has_bit.astype(np.int8)
    is_zero = sums == 0
    is_zero[0] = False
    dp = np.zeros(1 << k, dtype=np.int8)
    for size in range(1, k + 1):
        layer = np.flatnonzero(popcount == size)
        best = np.zeros(layer.size, dtype=np.int8)
        for i in range(k):
            bit = 1 << i
            selected = (layer & bit) != 0
            best[selected] = np.maximum(best[selected], dp[layer[selected] ^ bit])
        dp[layer] = best + is_zero[layer]
    return dp, is_zero


def _dp_python(values: Sequence[int]) -> tuple[list[int], list[bool]]:
    k = len(values)
    size = 1 << k
    sums = [0] * size
    dp = [0] * size
    is_zero = [False] * size
    for mask in range(1, size):
        low = mask & -mask
        sums[mask] = sums[mask ^ low] + values[low.bit_length() - 1]
        is_zero[mask] = sums[mask] == 0
        best = 0
        rest = mask
        while rest:
            bit = rest & -rest
            rest ^= bit
            best = max(best, dp[mask ^ bit])
        dp[mask] = best + is_zero[mask]
    return dp, is_zero


def _settle_group(group: dict[str, int]) -> list[Transfer]:
    """Settle one zero-sum group: the largest debtor repeatedly pays the largest creditor."""
    remaining = dict(group)
    transfers = []
    while any(remaining.values()):
        debtor = min(remaining, key=lambda m: (remaining[m], m))
        creditor = max(remaining, key=lambda m: (remaining[m], m))
        amount = min(-remaining[debtor], remaining[creditor])
        transfers.append(Transfer(debtor, creditor, amount))
        remaining[debtor] += amount
        remaining[creditor] -= amount
    return transfers
