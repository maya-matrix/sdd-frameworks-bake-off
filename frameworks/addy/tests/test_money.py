import pytest
from hypothesis import given
from hypothesis import strategies as st

from expense_splitter.money import MAX_AMOUNT_CENTS, format_cents, parse_amount


@pytest.mark.parametrize(
    ("text", "cents"),
    [
        ("10", 1000),
        ("10.5", 1050),
        ("10.50", 1050),
        ("0.01", 1),
        ("0.1", 10),
        ("007.20", 720),
        ("1000000000.00", 100_000_000_000),
    ],
)
def test_parse_amount_accepts_valid_decimal_strings(text: str, cents: int) -> None:
    assert parse_amount(text) == cents


@pytest.mark.parametrize(
    "text",
    ["", "0", "0.00", "-1", "+1", "1.234", "1e3", " 1", "1 ", "1.", ".5", "1,00", "abc", "١٢"],
)
def test_parse_amount_rejects_malformed_or_non_positive(text: str) -> None:
    with pytest.raises(ValueError):
        parse_amount(text)


def test_parse_amount_rejects_values_above_maximum() -> None:
    with pytest.raises(ValueError):
        parse_amount("1000000000.01")


def test_max_amount_is_one_billion() -> None:
    assert MAX_AMOUNT_CENTS == 100_000_000_000


@pytest.mark.parametrize(
    ("cents", "text"),
    [
        (0, "0.00"),
        (1, "0.01"),
        (10, "0.10"),
        (333, "3.33"),
        (-333, "-3.33"),
        (-1, "-0.01"),
        (100_000_000_000, "1000000000.00"),
    ],
)
def test_format_cents_always_uses_two_decimals(cents: int, text: str) -> None:
    assert format_cents(cents) == text


@given(st.integers(min_value=1, max_value=MAX_AMOUNT_CENTS))
def test_parse_inverts_format_for_valid_amounts(cents: int) -> None:
    assert parse_amount(format_cents(cents)) == cents
