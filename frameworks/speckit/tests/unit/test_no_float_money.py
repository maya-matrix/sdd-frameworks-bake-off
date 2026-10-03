"""Constitution II: no binary floating point or implicit rounding anywhere in the source."""

import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "src/splitit"
FORBIDDEN = re.compile(r"\bfloat\b|\bround\(|\bDecimal\b|float64|float32")


def test_no_float_round_or_decimal_in_source():
    offenders = [
        f"{path.name}:{lineno}: {line.strip()}"
        for path in sorted(SOURCE.rglob("*.py"))
        for lineno, line in enumerate(path.read_text().splitlines(), 1)
        if FORBIDDEN.search(line)
    ]
    assert offenders == []
