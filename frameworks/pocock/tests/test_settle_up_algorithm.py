import time
from collections.abc import Iterator

from hypothesis import assume, given
from hypothesis import strategies as st

from expense_splitter.settle_up import EXACT_LIMIT, Transfer, settle_up


def test_nothing_to_settle_when_everyone_is_at_zero() -> None:
    result = settle_up([("a", 0), ("b", 0)])

    assert result.transfers == []
    assert result.optimal is True


def test_one_debtor_pays_one_creditor() -> None:
    result = settle_up([("a", 500), ("b", -500)])

    assert result.transfers == [Transfer(from_id="b", to_id="a", amount=500)]
    assert result.optimal is True


def apply(balances: list[tuple[str, int]], transfers: list[Transfer]) -> dict[str, int]:
    remaining = dict(balances)
    for t in transfers:
        remaining[t.from_id] += t.amount
        remaining[t.to_id] -= t.amount
    return remaining


def test_finds_the_minimum_where_greedy_would_not() -> None:
    # Greedy matches f(+18) with a(-9) first and needs 5 transfers. Splitting into the
    # zero-sum subgroups {a, c} and {b, d, e, f} needs only 4.
    balances = [("a", -9), ("b", -8), ("c", 9), ("d", -6), ("e", -4), ("f", 18)]

    result = settle_up(balances)

    assert len(result.transfers) == 4
    assert result.optimal is True
    assert set(apply(balances, result.transfers).values()) == {0}
    assert Transfer(from_id="a", to_id="c", amount=9) in result.transfers


def balances_summing_to_zero(
    min_size: int, max_size: int, max_amount: int = 10_000
) -> st.SearchStrategy[list[tuple[str, int]]]:
    """Lists of (member_id, Balance) with distinct ids whose Balances sum to zero."""

    def build(values: list[int]) -> list[tuple[str, int]]:
        values = [*values, -sum(values)]
        return [(f"m{i}", v) for i, v in enumerate(values)]

    return st.lists(
        st.integers(-max_amount, max_amount), min_size=min_size - 1, max_size=max_size - 1
    ).map(build)


def set_partitions(items: list[int]) -> Iterator[list[list[int]]]:
    if not items:
        yield []
        return
    first, rest = items[0], items[1:]
    for partition in set_partitions(rest):
        for i in range(len(partition)):
            yield [*partition[:i], [first, *partition[i]], *partition[i + 1 :]]
        yield [[first], *partition]


def brute_force_minimum_transfers(balances: list[tuple[str, int]]) -> int:
    """Independent reference: try every partition of the non-zero Balances into blocks;
    the best partition with all-zero-sum blocks needs (n - number of blocks) transfers."""
    values = [b for _, b in balances if b != 0]
    best_blocks = max(
        len(p)
        for p in set_partitions(values)
        if all(sum(block) == 0 for block in p)
    ) if values else 0
    return len(values) - best_blocks


def check_transfers_are_well_formed(
    balances: list[tuple[str, int]], transfers: list[Transfer]
) -> None:
    ids = {member_id for member_id, _ in balances}
    for t in transfers:
        assert t.amount > 0
        assert t.from_id != t.to_id
        assert {t.from_id, t.to_id} <= ids
    assert set(apply(balances, transfers).values()) <= {0}


@given(balances_summing_to_zero(min_size=1, max_size=EXACT_LIMIT))
def test_transfers_clear_every_balance_exactly(balances: list[tuple[str, int]]) -> None:
    result = settle_up(balances)

    check_transfers_are_well_formed(balances, result.transfers)
    assert result.optimal is True


@given(balances_summing_to_zero(min_size=1, max_size=8, max_amount=20))
def test_number_of_transfers_is_the_true_minimum(balances: list[tuple[str, int]]) -> None:
    # Small amounts make zero-sum subgroups (where greedy can go wrong) common.
    result = settle_up(balances)

    assert len(result.transfers) == brute_force_minimum_transfers(balances)


@given(balances_summing_to_zero(min_size=EXACT_LIMIT + 1, max_size=EXACT_LIMIT + 8))
def test_falls_back_to_greedy_above_the_exact_limit(balances: list[tuple[str, int]]) -> None:
    assume(sum(1 for _, b in balances if b != 0) > EXACT_LIMIT)

    result = settle_up(balances)

    assert result.optimal is False
    check_transfers_are_well_formed(balances, result.transfers)
    assert len(result.transfers) <= len(balances) - 1


@given(balances_summing_to_zero(min_size=1, max_size=EXACT_LIMIT + 4, max_amount=50))
def test_same_balances_always_give_the_same_settle_up(balances: list[tuple[str, int]]) -> None:
    assert settle_up(balances) == settle_up(list(balances))


def test_exact_search_handles_the_limit_quickly() -> None:
    balances = [(f"m{i}", (i + 1) * 1_000 + i) for i in range(EXACT_LIMIT - 1)]
    balances.append(("last", -sum(b for _, b in balances)))

    start = time.perf_counter()
    result = settle_up(balances)

    assert time.perf_counter() - start < 1.0
    assert result.optimal is True
    assert len(result.transfers) == EXACT_LIMIT - 1
