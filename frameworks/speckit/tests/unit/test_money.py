import pytest
from hypothesis import given
from hypothesis import strategies as st

from splitit.money import MoneyFormatError, format_money, parse_money


@pytest.mark.parametrize(
    ("text", "cents"),
    [
        ("10.00", 1000),
        ("0.01", 1),
        ("0.00", 0),
        ("3.33", 333),
        ("1000000000.00", 100_000_000_000),
    ],
)
def test_parse_money_valid(text, cents):
    assert parse_money(text) == cents


@pytest.mark.parametrize(
    "text",
    ["10.5", "10.005", "1e3", "-5.00", "010.00", "10", "", " 10.00", "10.00 ", "1,00", ".50", "١٠.٠٠"],
)
def test_parse_money_rejects_invalid(text):
    with pytest.raises(MoneyFormatError):
        parse_money(text)


@pytest.mark.parametrize("value", [10.0, 10, None])
def test_parse_money_rejects_non_strings(value):
    with pytest.raises(MoneyFormatError):
        parse_money(value)


@pytest.mark.parametrize(
    ("cents", "text"),
    [(-333, "-3.33"), (0, "0.00"), (5, "0.05"), (1000, "10.00"), (-1, "-0.01"), (100_000_000_000, "1000000000.00")],
)
def test_format_money(cents, text):
    assert format_money(cents) == text


@given(st.integers(min_value=0, max_value=10**12))
def test_round_trip(cents):
    assert parse_money(format_money(cents)) == cents
