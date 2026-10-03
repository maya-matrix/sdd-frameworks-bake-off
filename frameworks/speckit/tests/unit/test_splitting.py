import pytest

from splitit.splitting import split_equally


@pytest.mark.parametrize(
    ("amount", "n", "shares"),
    [
        (3000, 3, [1000, 1000, 1000]),
        (1000, 3, [334, 333, 333]),
        (1, 3, [1, 0, 0]),
        (200, 3, [67, 67, 66]),
        (5, 1, [5]),
        (100, 7, [15, 15, 14, 14, 14, 14, 14]),
    ],
)
def test_split_equally(amount, n, shares):
    assert split_equally(amount, n) == shares


@pytest.mark.parametrize(("amount", "n"), [(100, 0), (100, -1), (0, 3), (-5, 2)])
def test_split_equally_rejects_invalid(amount, n):
    with pytest.raises(ValueError):
        split_equally(amount, n)
