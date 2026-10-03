"""Settle-up: the minimum number of transfers that brings every balance to exactly zero.

With k non-zero balances, any set of members whose balances sum to zero can be settled among
themselves in (size - 1) transfers, so the minimum is k - (max number of disjoint zero-sum
groups). Finding that maximum is NP-hard in general; for k <= EXACT_LIMIT we solve it exactly
over all 2^k subsets, using Python big ints as bitsets (bit `m` <-> subset mask `m`) so each
round is a handful of whole-set bitwise operations instead of a 2^k * k Python loop.
"""

from array import array
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache

from expense_splitter.money import Cents

EXACT_LIMIT = 20
_INT64_MAX = 2**63 - 1


@dataclass(frozen=True)
class Transfer:
    from_id: str
    to_id: str
    amount: Cents


def settle_up(
    balances: Sequence[tuple[str, Cents]], exact_limit: int = EXACT_LIMIT
) -> list[Transfer]:
    """Return transfers (debtor -> creditor) that zero all balances, ordered deterministically.

    Uses the minimum possible number of transfers when at most `exact_limit` balances are
    non-zero; above that, falls back to in-order matching (at most k - 1 transfers).
    """
    if sum(amount for _, amount in balances) != 0:
        raise ValueError("balances must sum to zero")
    nonzero = [(member_id, amount) for member_id, amount in balances if amount != 0]
    if len(nonzero) <= exact_limit:
        groups = _max_zero_sum_groups([amount for _, amount in nonzero])
    else:
        groups = [list(range(len(nonzero)))]
    transfers: list[Transfer] = []
    for group in groups:
        transfers.extend(_settle_group([nonzero[i] for i in group]))
    return transfers


@lru_cache(maxsize=1024)
def settle_up_cached(balances: tuple[tuple[str, Cents], ...]) -> tuple[Transfer, ...]:
    """`settle_up` memoized on the exact balances.

    Any change to a group's balances is a different key, so cached results are never stale.
    """
    return tuple(settle_up(balances))


def _settle_group(balances: Sequence[tuple[str, Cents]]) -> list[Transfer]:
    """Match debtors to creditors in order; each transfer zeroes at least one side."""
    creditor_ids = [member_id for member_id, amount in balances if amount > 0]
    owed = [amount for _, amount in balances if amount > 0]
    debtor_ids = [member_id for member_id, amount in balances if amount < 0]
    owing = [-amount for _, amount in balances if amount < 0]
    transfers = []
    c = d = 0
    while c < len(owed) and d < len(owing):
        amount = min(owed[c], owing[d])
        transfers.append(Transfer(debtor_ids[d], creditor_ids[c], amount))
        owed[c] -= amount
        owing[d] -= amount
        if owed[c] == 0:
            c += 1
        if owing[d] == 0:
            d += 1
    return transfers


def _max_zero_sum_groups(values: Sequence[Cents]) -> list[list[int]]:
    """Partition indices of `values` (non-zero, summing to 0) into the most zero-sum groups.

    Groups are ordered by their smallest index; indices within a group are ascending.
    """
    k = len(values)
    if k == 0:
        return []
    n = 1 << k
    full = n - 1
    every_mask = (1 << n) - 1

    subset_sums = _subset_sums(values)
    zero_sum = _bitset(mask for mask, s in enumerate(subset_sums) if s == 0 and mask)
    del subset_sums

    # without_bit[i]: bitset of masks that do not contain element i.
    without_bit = []
    for i in range(k):
        period = 1 << (i + 1)
        one_per_period = every_mask // ((1 << period) - 1)
        without_bit.append(one_per_period * ((1 << (1 << i)) - 1))

    def supersets(masks: int) -> int:
        for i in range(k):
            masks |= (masks & without_bit[i]) << (1 << i)
        return masks

    # roots[r]: zero-sum masks that split into at least r zero-sum groups, i.e. zero-sum masks
    #           whose remainder after dropping their top element is in reach[r-1].
    # reach[r]: masks containing at least r disjoint zero-sum groups (supersets of roots[r]).
    roots, reach = [0], [every_mask]
    while True:
        drop_top = 0
        for h in range(k):
            size = 1 << h
            drop_top |= (reach[-1] & ((1 << size) - 1)) << size
        root = drop_top & zero_sum
        if not root >> full & 1:
            break
        roots.append(root)
        reach.append(supersets(root))

    # Peel groups off the full set: at level r, the remainder must be a level r-1 root.
    group_masks = []
    current = full
    for r in range(len(roots) - 1, 1, -1):
        rest = current ^ (1 << (current.bit_length() - 1))
        while not roots[r - 1] >> rest & 1:
            rest = next(rest ^ bit for bit in _bits(rest) if reach[r - 1] >> (rest ^ bit) & 1)
        group_masks.append(current ^ rest)
        current = rest
    group_masks.append(current)

    group_masks.sort(key=lambda mask: mask & -mask)
    return [[i for i in range(k) if mask >> i & 1] for mask in group_masks]


def _subset_sums(values: Sequence[Cents]) -> Sequence[Cents]:
    """Sum of every subset of `values`, indexed by subset mask.

    Packed as int64 (8 bytes per entry instead of ~36 for a list of ints) whenever no subset
    sum can overflow; at 2^20 entries that is the difference between ~8 MB and ~40 MB.
    """
    if sum(abs(value) for value in values) <= _INT64_MAX:
        packed = array("q", [0])
        for value in values:
            packed.extend(array("q", (s + value for s in packed)))
        return packed
    unbounded = [0]
    for value in values:
        unbounded += [s + value for s in unbounded]
    return unbounded


def _bitset(positions: Iterable[int]) -> int:
    raw = bytearray()
    for position in positions:
        byte = position >> 3
        if byte >= len(raw):
            raw.extend(bytes(byte - len(raw) + 1))
        raw[byte] |= 1 << (position & 7)
    return int.from_bytes(raw, "little")


def _bits(mask: int) -> list[int]:
    return [1 << i for i in range(mask.bit_length()) if mask >> i & 1]
