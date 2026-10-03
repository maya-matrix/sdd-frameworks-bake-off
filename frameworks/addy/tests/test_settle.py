import time
from collections.abc import Sequence

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from expense_splitter.settle import EXACT_LIMIT, Transfer, settle_up


def apply_transfers(
    balances: Sequence[tuple[str, int]], transfers: Sequence[Transfer]
) -> dict[str, int]:
    result = dict(balances)
    for transfer in transfers:
        result[transfer.from_id] += transfer.amount
        result[transfer.to_id] -= transfer.amount
    return result


def brute_force_min_transfers(values: Sequence[int]) -> int:
    """Independent reference: k - (max number of disjoint zero-sum groups), via naive mask DP."""
    nonzero = [v for v in values if v != 0]
    k = len(nonzero)
    dp = [0] * (1 << k)
    for mask in range(1, 1 << k):
        total = sum(v for i, v in enumerate(nonzero) if mask >> i & 1)
        best = max(dp[mask ^ (1 << i)] for i in range(k) if mask >> i & 1)
        dp[mask] = best + (total == 0)
    return k - dp[(1 << k) - 1]


def assert_valid_settlement(
    balances: Sequence[tuple[str, int]], transfers: Sequence[Transfer]
) -> None:
    original = dict(balances)
    assert all(t.amount > 0 for t in transfers)
    assert all(original[t.from_id] < 0 < original[t.to_id] for t in transfers)
    assert set(apply_transfers(balances, transfers).values()) <= {0}


def test_settled_group_needs_no_transfers() -> None:
    assert settle_up([("a", 0), ("b", 0)]) == []


def test_empty_group_needs_no_transfers() -> None:
    assert settle_up([]) == []


def test_single_debtor_pays_single_creditor() -> None:
    assert settle_up([("a", 500), ("b", -500)]) == [Transfer("b", "a", 500)]


def test_one_creditor_is_paid_by_each_debtor() -> None:
    balances = [("a", 666), ("b", -333), ("c", -333)]

    transfers = settle_up(balances)

    assert transfers == [Transfer("b", "a", 333), Transfer("c", "a", 333)]


def test_finds_fewer_transfers_than_naive_matching() -> None:
    # Naive in-order matching: c->a 3, c->b 2, d->b 3 (3 transfers). Optimal: d->a, c->b.
    balances = [("a", 3), ("b", 5), ("c", -5), ("d", -3)]

    transfers = settle_up(balances)

    assert len(transfers) == 2
    assert_valid_settlement(balances, transfers)
    assert len(settle_up(balances, exact_limit=0)) == 3


def test_independent_subgroups_are_settled_separately() -> None:
    balances = [("a", 7), ("b", 2), ("c", -2), ("d", 4), ("e", -7), ("f", -4)]

    transfers = settle_up(balances)

    assert len(transfers) == 3
    assert_valid_settlement(balances, transfers)


def test_zero_balances_are_ignored() -> None:
    balances = [("a", 0), ("b", 100), ("c", 0), ("d", -100)]

    assert settle_up(balances) == [Transfer("d", "b", 100)]


def test_unbalanced_input_is_rejected() -> None:
    with pytest.raises(ValueError):
        settle_up([("a", 100), ("b", -99)])


def test_same_input_gives_same_output() -> None:
    balances = [("a", 3), ("b", 5), ("c", -5), ("d", -3), ("e", 1), ("f", -1)]

    assert settle_up(balances) == settle_up(list(balances))


def zero_sum_balances(max_size: int) -> st.SearchStrategy[list[tuple[str, int]]]:
    def close(values: list[int]) -> list[tuple[str, int]]:
        values = [*values, -sum(values)]
        return [(f"m{i}", v) for i, v in enumerate(values)]

    small = st.integers(min_value=-20, max_value=20)  # small values make zero-sum subsets common
    return st.lists(small, min_size=0, max_size=max_size - 1).map(close)


@settings(max_examples=300)
@given(zero_sum_balances(max_size=8))
def test_transfer_count_is_minimal(balances: list[tuple[str, int]]) -> None:
    transfers = settle_up(balances)

    assert_valid_settlement(balances, transfers)
    assert len(transfers) == brute_force_min_transfers([v for _, v in balances])


@given(zero_sum_balances(max_size=30))
def test_large_groups_still_settle_exactly(balances: list[tuple[str, int]]) -> None:
    assert_valid_settlement(balances, settle_up(balances))


def test_balances_beyond_64_bit_range_settle_exactly() -> None:
    # Subset sums here overflow int64, so the compact int64 path must not be used.
    balances = [("a", 2**62), ("b", 2**62), ("c", -(2**63)), ("d", 5), ("e", -5)]

    transfers = settle_up(balances)

    assert_valid_settlement(balances, transfers)
    assert len(transfers) == 3


def test_fallback_above_exact_limit_still_clears_all_debts() -> None:
    values = [i * 37 % 101 + 1 for i in range(EXACT_LIMIT + 4)]
    balances = [(f"m{i}", v) for i, v in enumerate(values)]
    balances.append(("sink", -sum(values)))

    transfers = settle_up(balances)

    assert_valid_settlement(balances, transfers)
    assert len(transfers) <= len(balances) - 1


def test_exactly_exact_limit_balances_still_get_the_minimum() -> None:
    # In-order matching settles this in 15 transfers; the minimum is 10 (+3/-3 and +5/-5 pairs).
    balances = [(f"m{i}", v) for i, v in enumerate([3, 5, -5, -3] * (EXACT_LIMIT // 4))]
    assert len(balances) == EXACT_LIMIT

    transfers = settle_up(balances)

    assert_valid_settlement(balances, transfers)
    assert len(transfers) == EXACT_LIMIT // 2
    assert len(settle_up(balances, exact_limit=EXACT_LIMIT - 1)) > len(transfers)


@pytest.mark.parametrize(
    ("values", "expected_transfers"),
    [
        ([1] * 10 + [-1] * 10, 10),  # many zero-sum subsets: ten +1/-1 pairs
        ([3**i for i in range(EXACT_LIMIT - 1)], EXACT_LIMIT - 1),  # only the whole group
    ],
)
def test_exact_limit_finishes_quickly(values: list[int], expected_transfers: int) -> None:
    if sum(values) != 0:
        values = [*values, -sum(values)]
    balances = [(f"m{i}", v) for i, v in enumerate(values)]

    started = time.perf_counter()
    transfers = settle_up(balances)
    elapsed = time.perf_counter() - started

    assert elapsed < 2.0
    assert_valid_settlement(balances, transfers)
    assert len(balances) == EXACT_LIMIT
    assert len(transfers) == expected_transfers
