import pytest

from app.splitting import split_equally


def test_leftover_cents_go_to_lowest_ids():
    assert split_equally(1000, [1, 2, 3]) == {1: 334, 2: 333, 3: 333}


def test_single_cent_among_three():
    assert split_equally(1, [1, 2, 3]) == {1: 1, 2: 0, 3: 0}


def test_even_split():
    assert split_equally(900, [7, 8, 9]) == {7: 300, 8: 300, 9: 300}


def test_single_member_takes_everything():
    assert split_equally(1001, [5]) == {5: 1001}


def test_input_order_does_not_matter():
    assert split_equally(1000, [3, 1, 2]) == {1: 334, 2: 333, 3: 333}
    assert list(split_equally(1000, [3, 1, 2])) == [1, 2, 3]


def test_shares_always_sum_to_total_and_differ_by_at_most_one_cent():
    for total in (0, 1, 2, 99, 100, 101, 999, 1000, 1001, 12345, 100_000_000_000):
        for size in range(1, 13):
            shares = split_equally(total, range(10, 10 + size))
            assert sum(shares.values()) == total
            assert max(shares.values()) - min(shares.values()) <= 1


@pytest.mark.parametrize(
    ("total", "members"),
    [(100, []), (100, [1, 1]), (-1, [1, 2])],
)
def test_rejects_invalid_input(total, members):
    with pytest.raises(ValueError):
        split_equally(total, members)
