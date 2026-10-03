import pytest
from hypothesis import given
from hypothesis import strategies as st

from expense_splitter.split import split_equally


def test_remainder_cents_go_to_first_listed_members() -> None:
    assert split_equally(1000, ["a", "b", "c"]) == [("a", 334), ("b", 333), ("c", 333)]


def test_request_order_decides_who_gets_remainder() -> None:
    assert split_equally(1000, ["c", "a", "b"]) == [("c", 334), ("a", 333), ("b", 333)]


def test_single_cent_among_three_goes_to_first_member() -> None:
    assert split_equally(1, ["a", "b", "c"]) == [("a", 1), ("b", 0), ("c", 0)]


def test_even_split_has_no_remainder() -> None:
    assert split_equally(900, ["a", "b", "c"]) == [("a", 300), ("b", 300), ("c", 300)]


def test_single_member_takes_everything() -> None:
    assert split_equally(1234, ["a"]) == [("a", 1234)]


def test_seven_way_split_sums_to_total() -> None:
    shares = split_equally(10000, [str(i) for i in range(7)])
    assert sum(amount for _, amount in shares) == 10000


def test_empty_member_list_is_rejected() -> None:
    with pytest.raises(ValueError):
        split_equally(1000, [])


@given(
    total=st.integers(min_value=1, max_value=100_000_000_000),
    count=st.integers(min_value=1, max_value=50),
)
def test_shares_sum_to_total_and_differ_by_at_most_one_cent(total: int, count: int) -> None:
    shares = split_equally(total, [f"m{i}" for i in range(count)])
    amounts = [amount for _, amount in shares]
    assert sum(amounts) == total
    assert max(amounts) - min(amounts) <= 1
