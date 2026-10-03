import ast
import pathlib

import pytest

from app.money import MAX_AMOUNT_CENTS, format_cents, parse_amount

APP_DIR = pathlib.Path(__file__).resolve().parent.parent / "app"


@pytest.mark.parametrize(
    ("text", "cents"),
    [
        ("12.34", 1234),
        ("12.3", 1230),
        ("12", 1200),
        ("0.01", 1),
        ("0.10", 10),
        ("007.50", 750),
        ("1000000000.00", MAX_AMOUNT_CENTS),
    ],
)
def test_parse_amount_accepts_decimal_strings(text, cents):
    assert parse_amount(text) == cents


@pytest.mark.parametrize(
    "value",
    [
        12.34,
        12,
        True,
        None,
        "",
        " 1",
        "1 ",
        "1.00\n",
        "-1",
        "+1",
        "0",
        "0.00",
        "1.234",
        "1e3",
        ".5",
        "5.",
        "1,00",
        "١٢",
        "1000000000.01",
        "9" * 5000,
    ],
)
def test_parse_amount_rejects_everything_else(value):
    with pytest.raises(ValueError):
        parse_amount(value)


@pytest.mark.parametrize(
    ("cents", "text"),
    [(0, "0.00"), (5, "0.05"), (-5, "-0.05"), (-333, "-3.33"), (123456, "1234.56")],
)
def test_format_cents(cents, text):
    assert format_cents(cents) == text


def test_format_then_parse_round_trips():
    for cents in range(1, 100_000, 7):
        assert parse_amount(format_cents(cents)) == cents


FORBIDDEN_NAMES = {"float", "Float"}


def test_app_code_never_uses_float():
    offenders = []
    for path in sorted(APP_DIR.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if (
                (isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES)
                or (isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES)
                or (isinstance(node, ast.alias) and node.name in FORBIDDEN_NAMES)
                or (isinstance(node, ast.Constant) and isinstance(node.value, float))
            ):
                offenders.append(f"{path.name}:{getattr(node, 'lineno', '?')}")
    assert offenders == []
