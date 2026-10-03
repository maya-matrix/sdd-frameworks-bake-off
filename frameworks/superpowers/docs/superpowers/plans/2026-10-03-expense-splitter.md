# Expense Splitter API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A FastAPI service where groups record equally-split expenses, report exact net balances, and suggest the minimum transfers to settle up.

**Architecture:** Three pure modules (`money`, `splitting`, `settlement`) hold all arithmetic on integer cents. A thin SQLAlchemy layer (`models`, `repository`) persists groups, members, expenses and per-member shares. `api.py` translates JSON (decimal-string money) to and from the domain; `main.py` is an app factory.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.0, SQLite, pytest, httpx (TestClient), managed with `uv`.

**Spec:** `docs/superpowers/specs/2026-10-03-expense-splitter-design.md`

## Global Constraints

- Project root is `frameworks/superpowers/` (the git repo root is two levels up, `sdd-bake-off/`). All commands below run from the project root. Work on branch `superpowers/expense-splitter`.
- Python `>=3.13`; runtime deps only `fastapi`, `sqlalchemy`, `uvicorn`; dev deps only `pytest`, `httpx`.
- Money is integer cents everywhere in `app/`. No `float`, no `Float` columns, no float literals — enforced by a test.
- Money on the wire is a JSON string matching `^\d+(\.\d{1,2})?$` (ASCII digits), > 0, ≤ `1000000000.00`. JSON numbers are rejected with 422.
- Equal split: leftover cents go one each to the lowest member ids. `sum(shares) == amount` always.
- Balance = paid − owed; positive means the member is owed money. Balances are derived, never stored.
- Settle-up: exact minimum for ≤ 20 non-zero balances (`optimal: true`), greedy above (`optimal: false`). Transfers sorted by `(from_member_id, to_member_id)`.
- `currency`: `^[A-Z]{3}$`, default `"EUR"`. Group/member `name`: trimmed, 1–100 chars. `description`: trimmed, 1–200 chars.
- Status codes: 201 on create, 404 unknown group, 409 duplicate member name in a group, 422 any validation failure. Error body is `{"detail": ...}`.
- Commit messages end with the trailer line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Amount strings that look numeric but are not plain ASCII decimals (`"1.00\n"`, `"١٢"`, `" 1"`, `"+1"`) → rejected, never parsed. Pinned in Task 1.
2. Absurdly long amount strings (`"9" * 5000`) → 422, never a 500 from Python's int-conversion digit limit. Pinned in Task 1 (unit) and Task 5 (API).
3. JSON booleans or numeric strings used as member ids (`"payer_id": true`, `"split_between": ["1"]`) → 422, not silently coerced to member 1. Pinned in Task 5.
4. Member names that differ only by surrounding whitespace (`"Alice "` vs `"Alice"`) → 409 duplicate. Pinned in Task 4.
5. Settle-up at exactly 20 non-zero balances → exact result in about a second; at 21 → greedy fallback flagged `optimal: false`. Pinned in Task 3.

---

## File Structure

```
pyproject.toml          project + pytest config
.python-version         3.13
.gitignore
README.md               run + API usage
app/__init__.py
app/money.py            parse_amount / format_cents
app/splitting.py        split_equally
app/settlement.py       Transfer, minimize_transfers
app/models.py           SQLAlchemy ORM models
app/repository.py       DB access + domain errors
app/schemas.py          Pydantic request/response models
app/api.py              routes + error handlers
app/main.py             create_app factory
tests/__init__.py
tests/conftest.py       client + make_group fixtures, to_cents helper
tests/test_money.py
tests/test_splitting.py
tests/test_settlement.py
tests/test_api_groups.py
tests/test_api_expenses.py
tests/test_api_balances.py
```

---

### Task 1: Project scaffold and exact money parsing

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `app/__init__.py`, `app/money.py`, `tests/__init__.py`, `tests/test_money.py`

**Interfaces:**
- Consumes: nothing
- Produces: `app.money.parse_amount(value: object) -> int` (raises `ValueError`), `app.money.format_cents(cents: int) -> str`, `app.money.MAX_AMOUNT_CENTS: int = 100_000_000_000`

- [ ] **Step 1: Create the project files**

`pyproject.toml`:

```toml
[project]
name = "expense-splitter"
version = "0.1.0"
description = "Web API for splitting group expenses with exact money arithmetic"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115",
    "sqlalchemy>=2.0",
    "uvicorn>=0.30",
]

[dependency-groups]
dev = [
    "httpx>=0.27",
    "pytest>=8",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`.gitignore`:

```
.venv/
__pycache__/
.pytest_cache/
*.db
```

`app/__init__.py` and `tests/__init__.py`: empty files.

Run: `uv python pin 3.13 && uv sync`
Expected: creates `.python-version` and `.venv/`, installs dependencies, exits 0.

- [ ] **Step 2: Write the failing tests**

`tests/test_money.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_money.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'app.money'`

- [ ] **Step 4: Implement `app/money.py`**

```python
"""Exact money handling: amounts travel as decimal strings and live as integer cents."""

import re

MAX_AMOUNT_CENTS = 100_000_000_000  # 1,000,000,000.00
_MAX_AMOUNT_LENGTH = 20
_AMOUNT_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]{1,2})?")


def parse_amount(value: object) -> int:
    """Parse a positive decimal string such as "12.34" into integer cents."""
    if (
        not isinstance(value, str)
        or len(value) > _MAX_AMOUNT_LENGTH
        or not _AMOUNT_PATTERN.fullmatch(value)
    ):
        raise ValueError('amount must be a decimal string with at most 2 decimal places, e.g. "12.34"')
    whole, _, fraction = value.partition(".")
    cents = int(whole) * 100 + int(fraction.ljust(2, "0"))
    if cents <= 0:
        raise ValueError("amount must be greater than 0")
    if cents > MAX_AMOUNT_CENTS:
        raise ValueError("amount must not exceed 1000000000.00")
    return cents


def format_cents(cents: int) -> str:
    """Format integer cents as a decimal string, e.g. -333 -> "-3.33"."""
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{sign}{whole}.{fraction:02d}"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_money.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .python-version .gitignore app/__init__.py app/money.py tests/__init__.py tests/test_money.py
git commit -m "feat: project scaffold and exact money parsing" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Equal splitting

**Files:**
- Create: `app/splitting.py`, `tests/test_splitting.py`

**Interfaces:**
- Consumes: nothing
- Produces: `app.splitting.split_equally(total_cents: int, member_ids: Iterable[int]) -> dict[int, int]` — keys in ascending id order; raises `ValueError` on empty, duplicate ids, or negative total.

- [ ] **Step 1: Write the failing tests**

`tests/test_splitting.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_splitting.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'app.splitting'`

- [ ] **Step 3: Implement `app/splitting.py`**

```python
"""Divide an amount of cents into shares that add up exactly to the total."""

from collections.abc import Iterable


def split_equally(total_cents: int, member_ids: Iterable[int]) -> dict[int, int]:
    """Split total_cents equally; leftover cents go one each to the lowest member ids."""
    ids = sorted(member_ids)
    if not ids:
        raise ValueError("cannot split between zero members")
    if len(set(ids)) != len(ids):
        raise ValueError("member ids must be unique")
    if total_cents < 0:
        raise ValueError("total must not be negative")
    base, remainder = divmod(total_cents, len(ids))
    return {member_id: base + (1 if index < remainder else 0) for index, member_id in enumerate(ids)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_splitting.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/splitting.py tests/test_splitting.py
git commit -m "feat: equal splitting with exact leftover-cent distribution" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Minimum-transfer settlement

**Files:**
- Create: `app/settlement.py`, `tests/test_settlement.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `app.settlement.Transfer` — frozen dataclass `(from_member_id: int, to_member_id: int, amount_cents: int)`
  - `app.settlement.minimize_transfers(balances: Mapping[int, int]) -> tuple[list[Transfer], bool]` — `bool` is `optimal`; raises `ValueError` if balances do not sum to 0
  - `app.settlement.EXACT_LIMIT: int = 20`

Algorithm (from the spec): drop zero balances; if more than 20 remain, settle greedily and return `optimal=False`. Otherwise find the partition of balances into the maximum number of zero-sum groups with a DP over bitmasks (`best[mask] = max(best[mask without one element]) + (1 if sum(mask) == 0 else 0)`), walk back to recover an element order whose zero-sum prefixes form the groups, and settle each group greedily — a group with no zero-sum proper subset needs exactly `len(group) - 1` transfers, which greedy achieves.

- [ ] **Step 1: Write the failing tests**

`tests/test_settlement.py`:

```python
import random
from itertools import combinations

import pytest

from app.settlement import EXACT_LIMIT, Transfer, minimize_transfers


def apply(balances, transfers):
    result = dict(balances)
    for transfer in transfers:
        assert transfer.amount_cents > 0
        result[transfer.from_member_id] += transfer.amount_cents
        result[transfer.to_member_id] -= transfer.amount_cents
    return result


def max_zero_sum_groups(values):
    if not values:
        return 0
    first, rest = values[0], values[1:]
    best = -len(values)
    for size in range(len(rest) + 1):
        for chosen in combinations(range(len(rest)), size):
            if first + sum(rest[i] for i in chosen) == 0:
                remaining = [rest[i] for i in range(len(rest)) if i not in chosen]
                best = max(best, 1 + max_zero_sum_groups(remaining))
    return best


def brute_force_minimum(values):
    nonzero = [v for v in values if v != 0]
    return len(nonzero) - max_zero_sum_groups(nonzero)


def test_no_balances():
    assert minimize_transfers({}) == ([], True)


def test_all_zero_balances():
    assert minimize_transfers({1: 0, 2: 0}) == ([], True)


def test_single_debt():
    assert minimize_transfers({1: 500, 2: -500}) == ([Transfer(2, 1, 500)], True)


def test_one_creditor_two_debtors():
    transfers, optimal = minimize_transfers({1: 666, 2: -333, 3: -333})
    assert optimal
    assert transfers == [Transfer(2, 1, 333), Transfer(3, 1, 333)]


def test_beats_greedy_where_greedy_needs_four_transfers():
    # Greedy (largest debtor pays largest creditor) uses 4 transfers here;
    # {+4, -2, -2} and {+3, -3} settle in 3.
    balances = {1: 400, 2: 300, 3: -300, 4: -200, 5: -200}
    transfers, optimal = minimize_transfers(balances)
    assert optimal
    assert transfers == [Transfer(3, 2, 300), Transfer(4, 1, 200), Transfer(5, 1, 200)]


def test_rejects_balances_that_do_not_sum_to_zero():
    with pytest.raises(ValueError):
        minimize_transfers({1: 100, 2: -99})


def test_matches_brute_force_minimum_on_random_cases():
    rng = random.Random(1234)
    for _ in range(300):
        size = rng.randint(2, 7)
        values = [rng.choice([-1, 1]) * rng.randint(1, 6) * 100 for _ in range(size - 1)]
        values.append(-sum(values))
        balances = {index + 1: value for index, value in enumerate(values)}
        transfers, optimal = minimize_transfers(balances)
        assert optimal
        assert all(value == 0 for value in apply(balances, transfers).values())
        assert len(transfers) == brute_force_minimum(values)


def test_transfers_are_sorted_and_deterministic():
    balances = {9: -700, 3: 200, 5: 500}
    first, _ = minimize_transfers(balances)
    second, _ = minimize_transfers(dict(reversed(list(balances.items()))))
    assert first == second
    assert first == sorted(first, key=lambda t: (t.from_member_id, t.to_member_id))


def test_exactly_twenty_nonzero_balances_is_solved_exactly():
    rng = random.Random(7)
    amounts = [100 * k for k in range(1, 11)]
    debts = amounts[:]
    rng.shuffle(debts)
    balances = {i + 1: amount for i, amount in enumerate(amounts)}
    balances.update({i + 11: -debt for i, debt in enumerate(debts)})
    assert sum(1 for v in balances.values() if v) == EXACT_LIMIT == 20
    transfers, optimal = minimize_transfers(balances)
    assert optimal
    assert len(transfers) == 10
    assert all(value == 0 for value in apply(balances, transfers).values())


def test_more_than_twenty_nonzero_balances_falls_back_to_greedy():
    balances = {i: 200 for i in range(1, 8)}
    balances.update({i: -100 for i in range(8, 22)})
    transfers, optimal = minimize_transfers(balances)
    assert not optimal
    assert all(value == 0 for value in apply(balances, transfers).values())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_settlement.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'app.settlement'`

- [ ] **Step 3: Implement `app/settlement.py`**

```python
"""Suggest the fewest transfers that bring every balance to zero."""

from collections.abc import Mapping
from dataclasses import dataclass

EXACT_LIMIT = 20

Entry = tuple[int, int]  # (member_id, balance_cents)


@dataclass(frozen=True)
class Transfer:
    from_member_id: int
    to_member_id: int
    amount_cents: int


def minimize_transfers(balances: Mapping[int, int]) -> tuple[list[Transfer], bool]:
    """Return (transfers, optimal). Positive balance = is owed, negative = owes.

    Exact for up to EXACT_LIMIT non-zero balances; above that a greedy
    settlement is returned with optimal=False.
    """
    if sum(balances.values()) != 0:
        raise ValueError("balances must sum to zero")
    entries = sorted((member_id, cents) for member_id, cents in balances.items() if cents != 0)
    if len(entries) > EXACT_LIMIT:
        return _ordered(_settle_greedily(entries)), False
    transfers: list[Transfer] = []
    for group in _max_zero_sum_partition(entries):
        transfers.extend(_settle_greedily(group))
    return _ordered(transfers), True


def _ordered(transfers: list[Transfer]) -> list[Transfer]:
    return sorted(transfers, key=lambda t: (t.from_member_id, t.to_member_id))


def _settle_greedily(entries: list[Entry]) -> list[Transfer]:
    """Largest debtor pays largest creditor until everyone is even (ties: lowest id)."""
    debts = {member_id: -cents for member_id, cents in entries if cents < 0}
    credits = {member_id: cents for member_id, cents in entries if cents > 0}
    transfers = []
    while debts:
        debtor = max(debts, key=lambda m: (debts[m], -m))
        creditor = max(credits, key=lambda m: (credits[m], -m))
        amount = min(debts[debtor], credits[creditor])
        transfers.append(Transfer(debtor, creditor, amount))
        debts[debtor] -= amount
        credits[creditor] -= amount
        if debts[debtor] == 0:
            del debts[debtor]
        if credits[creditor] == 0:
            del credits[creditor]
    return transfers


def _max_zero_sum_partition(entries: list[Entry]) -> list[list[Entry]]:
    """Split entries (summing to zero) into the most possible zero-sum groups."""
    count = len(entries)
    if count == 0:
        return []
    values = [cents for _, cents in entries]
    full = (1 << count) - 1
    sums = [0] * (full + 1)
    best = [0] * (full + 1)
    for mask in range(1, full + 1):
        low = mask & -mask
        sums[mask] = sums[mask ^ low] + values[low.bit_length() - 1]
        most = 0
        rest = mask
        while rest:
            bit = rest & -rest
            if best[mask ^ bit] > most:
                most = best[mask ^ bit]
            rest ^= bit
        best[mask] = most + (1 if sums[mask] == 0 else 0)

    # Walk back from the full set, recovering an order of elements whose
    # zero-sum prefixes are exactly the groups of an optimal partition.
    order = []
    mask = full
    while mask:
        target = best[mask] - (1 if sums[mask] == 0 else 0)
        rest = mask
        while best[mask ^ (rest & -rest)] != target:
            rest ^= rest & -rest
        bit = rest & -rest
        order.append(bit.bit_length() - 1)
        mask ^= bit
    order.reverse()

    groups: list[list[Entry]] = []
    current: list[Entry] = []
    running = 0
    for index in order:
        current.append(entries[index])
        running += values[index]
        if running == 0:
            groups.append(current)
            current = []
    return groups
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_settlement.py -v --durations=3`
Expected: all PASS; `test_exactly_twenty_nonzero_balances_is_solved_exactly` takes roughly 1s.

- [ ] **Step 5: Commit**

```bash
git add app/settlement.py tests/test_settlement.py
git commit -m "feat: exact minimum-transfer settlement with greedy fallback" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Persistence, app factory, groups and members endpoints

**Files:**
- Create: `app/models.py`, `app/repository.py`, `app/schemas.py`, `app/api.py`, `app/main.py`, `tests/conftest.py`, `tests/test_api_groups.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `app.main.create_app(database_url: str | None = None) -> FastAPI` (falls back to env `DATABASE_URL`, then `sqlite:///./expenses.db`)
  - `app.models`: `Base`, `Group(id, name, currency, members)`, `Member(id, group_id, name)`
  - `app.repository`: `GroupNotFound`, `DuplicateMemberName`, `create_group(session, name, currency) -> Group`, `get_group(session, group_id) -> Group`, `add_member(session, group_id, name) -> Member`, `list_members(session, group_id) -> list[Member]`
  - `app.schemas`: `GroupCreate`, `MemberCreate`, `MemberOut`, `GroupOut`
  - `app.api`: `router`, `SessionDep`, `register_error_handlers(app)`, `_ERROR_STATUS` dict mapping exception type → status
  - test fixtures `client`, `make_group(*names, currency="EUR") -> (group_id, [member_ids])`, helper `tests.conftest.to_cents(text) -> int`

- [ ] **Step 1: Write the test fixtures**

`tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def to_cents(text: str) -> int:
    """Test-side parser for response money strings, including negatives."""
    negative = text.startswith("-")
    whole, fraction = text.removeprefix("-").split(".")
    cents = int(whole) * 100 + int(fraction)
    return -cents if negative else cents


@pytest.fixture
def client(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_group(client):
    def _make(*member_names, currency="EUR"):
        group = client.post("/groups", json={"name": "Trip", "currency": currency}).json()
        member_ids = [
            client.post(f"/groups/{group['id']}/members", json={"name": name}).json()["id"]
            for name in member_names
        ]
        return group["id"], member_ids

    return _make
```

- [ ] **Step 2: Write the failing tests**

`tests/test_api_groups.py`:

```python
import pytest


def test_create_group(client):
    response = client.post("/groups", json={"name": "  Trip  ", "currency": "USD"})
    assert response.status_code == 201
    body = response.json()
    assert body == {"id": body["id"], "name": "Trip", "currency": "USD", "members": []}


def test_currency_defaults_to_eur(client):
    assert client.post("/groups", json={"name": "Trip"}).json()["currency"] == "EUR"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 101},
        {"name": "Trip", "currency": "eur"},
        {"name": "Trip", "currency": "EURO"},
        {"name": "Trip", "currency": " EUR"},
    ],
)
def test_create_group_validation(client, payload):
    assert client.post("/groups", json=payload).status_code == 422


def test_get_group_lists_members_in_id_order(client, make_group):
    group_id, (alice, bob) = make_group("Alice", "Bob")
    response = client.get(f"/groups/{group_id}")
    assert response.status_code == 200
    assert response.json()["members"] == [{"id": alice, "name": "Alice"}, {"id": bob, "name": "Bob"}]


def test_add_and_list_members(client, make_group):
    group_id, _ = make_group()
    response = client.post(f"/groups/{group_id}/members", json={"name": " Alice "})
    assert response.status_code == 201
    member = response.json()
    assert member == {"id": member["id"], "name": "Alice"}
    assert client.get(f"/groups/{group_id}/members").json() == [member]


def test_duplicate_member_name_conflicts(client, make_group):
    group_id, _ = make_group("Alice")
    response = client.post(f"/groups/{group_id}/members", json={"name": "Alice"})
    assert response.status_code == 409
    assert "Alice" in response.json()["detail"]


def test_name_differing_only_by_whitespace_is_a_duplicate(client, make_group):
    group_id, _ = make_group("Alice")
    assert client.post(f"/groups/{group_id}/members", json={"name": "Alice "}).status_code == 409


def test_same_member_name_allowed_in_different_groups(client, make_group):
    make_group("Alice")
    other_group, _ = make_group()
    assert client.post(f"/groups/{other_group}/members", json={"name": "Alice"}).status_code == 201


@pytest.mark.parametrize("payload", [{}, {"name": ""}, {"name": "x" * 101}])
def test_add_member_validation(client, make_group, payload):
    group_id, _ = make_group()
    assert client.post(f"/groups/{group_id}/members", json=payload).status_code == 422


def test_unknown_group_is_404(client):
    assert client.get("/groups/999").status_code == 404
    assert client.get("/groups/999/members").status_code == 404
    assert client.post("/groups/999/members", json={"name": "Alice"}).status_code == 404
    assert client.get("/groups/999").json() == {"detail": "group 999 not found"}


def test_non_integer_group_id_is_422(client):
    assert client.get("/groups/abc").status_code == 422
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_api_groups.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 4: Implement `app/models.py`**

```python
"""SQLAlchemy ORM models. Money columns hold integer cents."""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3))
    members: Mapped[list["Member"]] = relationship(order_by="Member.id")


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (UniqueConstraint("group_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    name: Mapped[str] = mapped_column(String(100))
```

- [ ] **Step 5: Implement `app/repository.py`**

```python
"""Database access for groups, members and expenses."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Group, Member


class GroupNotFound(Exception):
    def __init__(self, group_id: int) -> None:
        super().__init__(f"group {group_id} not found")


class DuplicateMemberName(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"a member named {name!r} already exists in this group")


def create_group(session: Session, name: str, currency: str) -> Group:
    group = Group(name=name, currency=currency)
    session.add(group)
    session.commit()
    return group


def get_group(session: Session, group_id: int) -> Group:
    group = session.get(Group, group_id)
    if group is None:
        raise GroupNotFound(group_id)
    return group


def add_member(session: Session, group_id: int, name: str) -> Member:
    get_group(session, group_id)
    member = Member(group_id=group_id, name=name)
    session.add(member)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise DuplicateMemberName(name) from None
    return member


def list_members(session: Session, group_id: int) -> list[Member]:
    return list(get_group(session, group_id).members)
```

- [ ] **Step 6: Implement `app/schemas.py`**

```python
"""Request and response bodies. Money is always a decimal string on the wire."""

from typing import Annotated

from pydantic import BaseModel, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]


class GroupCreate(BaseModel):
    name: Name
    currency: Currency = "EUR"


class MemberCreate(BaseModel):
    name: Name


class MemberOut(BaseModel):
    id: int
    name: str


class GroupOut(BaseModel):
    id: int
    name: str
    currency: str
    members: list[MemberOut]
```

- [ ] **Step 7: Implement `app/api.py`**

```python
"""HTTP routes: JSON with decimal-string money on the outside, integer cents inside."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import repository, schemas
from app.models import Group, Member

router = APIRouter()


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

_ERROR_STATUS: dict[type[Exception], int] = {
    repository.GroupNotFound: 404,
    repository.DuplicateMemberName: 409,
}


def register_error_handlers(app: FastAPI) -> None:
    for error_type, status_code in _ERROR_STATUS.items():
        app.add_exception_handler(error_type, _error_handler(status_code))


def _error_handler(status_code: int):
    async def handle(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handle


def _member_out(member: Member) -> schemas.MemberOut:
    return schemas.MemberOut(id=member.id, name=member.name)


def _group_out(group: Group) -> schemas.GroupOut:
    return schemas.GroupOut(
        id=group.id,
        name=group.name,
        currency=group.currency,
        members=[_member_out(member) for member in group.members],
    )


@router.post("/groups", status_code=201)
def create_group(body: schemas.GroupCreate, session: SessionDep) -> schemas.GroupOut:
    return _group_out(repository.create_group(session, body.name, body.currency))


@router.get("/groups/{group_id}")
def get_group(group_id: int, session: SessionDep) -> schemas.GroupOut:
    return _group_out(repository.get_group(session, group_id))


@router.post("/groups/{group_id}/members", status_code=201)
def add_member(group_id: int, body: schemas.MemberCreate, session: SessionDep) -> schemas.MemberOut:
    return _member_out(repository.add_member(session, group_id, body.name))


@router.get("/groups/{group_id}/members")
def list_members(group_id: int, session: SessionDep) -> list[schemas.MemberOut]:
    return [_member_out(member) for member in repository.list_members(session, group_id)]
```

- [ ] **Step 8: Implement `app/main.py`**

```python
"""Application factory. Run with: uv run uvicorn app.main:create_app --factory"""

import os

from fastapi import FastAPI
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api import register_error_handlers, router
from app.models import Base

DEFAULT_DATABASE_URL = "sqlite:///./expenses.db"


def create_app(database_url: str | None = None) -> FastAPI:
    url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)

    app = FastAPI(title="Expense Splitter")
    app.state.session_factory = sessionmaker(engine, expire_on_commit=False)
    app.include_router(router)
    register_error_handlers(app)
    return app
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all PASS (Tasks 1–4).

- [ ] **Step 10: Commit**

```bash
git add app/models.py app/repository.py app/schemas.py app/api.py app/main.py tests/conftest.py tests/test_api_groups.py
git commit -m "feat: groups and members endpoints with SQLite persistence" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Recording and listing expenses

**Files:**
- Modify: `app/models.py`, `app/repository.py`, `app/schemas.py`, `app/api.py`
- Create: `tests/test_api_expenses.py`

**Interfaces:**
- Consumes: `parse_amount`, `format_cents` (Task 1); `split_equally` (Task 2); `get_group`, `SessionDep`, `_ERROR_STATUS`, fixtures `client`/`make_group` (Task 4)
- Produces:
  - `app.models.Expense(id, group_id, payer_id, amount_cents, description, created_at, shares)`, `app.models.ExpenseShare(expense_id, member_id, share_cents)`
  - `app.repository.InvalidExpense`, `record_expense(session, group_id, *, payer_id, amount_cents, description, split_between) -> Expense`, `list_expenses(session, group_id) -> list[Expense]`
  - `app.schemas.ExpenseCreate` (with `.amount_cents` property), `ShareOut`, `ExpenseOut`

- [ ] **Step 1: Write the failing tests**

`tests/test_api_expenses.py`:

```python
import pytest


def expense_payload(payer_id, split_between, amount="10.00", description="Taxi"):
    return {
        "payer_id": payer_id,
        "amount": amount,
        "description": description,
        "split_between": split_between,
    }


def test_record_expense_split_three_ways(client, make_group):
    group_id, (alice, bob, carol) = make_group("Alice", "Bob", "Carol")
    response = client.post(f"/groups/{group_id}/expenses", json=expense_payload(alice, [carol, alice, bob]))
    assert response.status_code == 201
    body = response.json()
    assert body["payer_id"] == alice
    assert body["amount"] == "10.00"
    assert body["description"] == "Taxi"
    assert body["created_at"].endswith("Z")
    assert body["shares"] == [
        {"member_id": alice, "amount": "3.34"},
        {"member_id": bob, "amount": "3.33"},
        {"member_id": carol, "amount": "3.33"},
    ]


def test_payer_need_not_share_the_expense(client, make_group):
    group_id, (alice, bob) = make_group("Alice", "Bob")
    response = client.post(f"/groups/{group_id}/expenses", json=expense_payload(alice, [bob]))
    assert response.status_code == 201
    assert response.json()["shares"] == [{"member_id": bob, "amount": "10.00"}]


def test_list_expenses_in_order(client, make_group):
    group_id, (alice, bob) = make_group("Alice", "Bob")
    first = client.post(f"/groups/{group_id}/expenses", json=expense_payload(alice, [alice, bob])).json()
    second = client.post(
        f"/groups/{group_id}/expenses", json=expense_payload(bob, [alice], amount="0.01", description="Gum")
    ).json()
    assert client.get(f"/groups/{group_id}/expenses").json() == [first, second]


@pytest.mark.parametrize(
    "amount",
    [10, 10.5, "1.234", "0", "-5.00", "1e3", "", " 1", "1000000000.01", "9" * 5000, None],
)
def test_invalid_amount_is_422(client, make_group, amount):
    group_id, (alice, bob) = make_group("Alice", "Bob")
    response = client.post(f"/groups/{group_id}/expenses", json=expense_payload(alice, [alice, bob], amount=amount))
    assert response.status_code == 422


@pytest.mark.parametrize("description", ["", "   ", "x" * 201])
def test_invalid_description_is_422(client, make_group, description):
    group_id, (alice,) = make_group("Alice")
    payload = expense_payload(alice, [alice], description=description)
    assert client.post(f"/groups/{group_id}/expenses", json=payload).status_code == 422


def test_empty_split_is_422(client, make_group):
    group_id, (alice,) = make_group("Alice")
    assert client.post(f"/groups/{group_id}/expenses", json=expense_payload(alice, [])).status_code == 422


def test_duplicate_split_members_is_422(client, make_group):
    group_id, (alice, bob) = make_group("Alice", "Bob")
    payload = expense_payload(alice, [bob, bob])
    assert client.post(f"/groups/{group_id}/expenses", json=payload).status_code == 422


def test_non_integer_ids_are_422(client, make_group):
    group_id, (alice, bob) = make_group("Alice", "Bob")
    for payload in (
        expense_payload(True, [alice, bob]),
        expense_payload(str(alice), [alice, bob]),
        expense_payload(alice, [str(bob)]),
        expense_payload(alice, [True]),
        expense_payload(float(alice), [alice]),
    ):
        assert client.post(f"/groups/{group_id}/expenses", json=payload).status_code == 422


def test_members_of_another_group_are_rejected(client, make_group):
    group_id, (alice,) = make_group("Alice")
    _, (outsider,) = make_group("Mallory")
    for payload in (expense_payload(outsider, [alice]), expense_payload(alice, [alice, outsider])):
        response = client.post(f"/groups/{group_id}/expenses", json=payload)
        assert response.status_code == 422
        assert str(outsider) in response.json()["detail"]


def test_unknown_member_id_is_rejected(client, make_group):
    group_id, (alice,) = make_group("Alice")
    assert client.post(f"/groups/{group_id}/expenses", json=expense_payload(alice, [999])).status_code == 422
    assert client.post(f"/groups/{group_id}/expenses", json=expense_payload(999, [alice])).status_code == 422


def test_rejected_expense_is_not_stored(client, make_group):
    group_id, (alice,) = make_group("Alice")
    client.post(f"/groups/{group_id}/expenses", json=expense_payload(alice, [999]))
    assert client.get(f"/groups/{group_id}/expenses").json() == []


def test_unknown_group_is_404(client):
    assert client.post("/groups/999/expenses", json=expense_payload(1, [1])).status_code == 404
    assert client.get("/groups/999/expenses").status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api_expenses.py -v`
Expected: FAIL — requests return 404 (route not found) or 405 instead of the expected codes.

- [ ] **Step 3: Add expense models to `app/models.py`**

Replace the import block with:

```python
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
```

Append:

```python
class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    payer_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    amount_cents: Mapped[int]
    description: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime]  # naive UTC
    shares: Mapped[list["ExpenseShare"]] = relationship(
        order_by="ExpenseShare.member_id", cascade="all, delete-orphan"
    )


class ExpenseShare(Base):
    __tablename__ = "expense_shares"

    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), primary_key=True)
    share_cents: Mapped[int]
```

- [ ] **Step 4: Add expense operations to `app/repository.py`**

Replace the import block with:

```python
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import Expense, ExpenseShare, Group, Member
from app.splitting import split_equally
```

Add after `DuplicateMemberName`:

```python
class InvalidExpense(Exception):
    pass
```

Append:

```python
def record_expense(
    session: Session,
    group_id: int,
    *,
    payer_id: int,
    amount_cents: int,
    description: str,
    split_between: Sequence[int],
) -> Expense:
    group = get_group(session, group_id)
    member_ids = {member.id for member in group.members}
    if payer_id not in member_ids:
        raise InvalidExpense(f"payer {payer_id} is not a member of this group")
    outsiders = sorted(set(split_between) - member_ids)
    if outsiders:
        raise InvalidExpense(f"members {outsiders} are not in this group")
    shares = split_equally(amount_cents, split_between)
    expense = Expense(
        group_id=group_id,
        payer_id=payer_id,
        amount_cents=amount_cents,
        description=description,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        shares=[ExpenseShare(member_id=member_id, share_cents=cents) for member_id, cents in shares.items()],
    )
    session.add(expense)
    session.commit()
    return expense


def list_expenses(session: Session, group_id: int) -> list[Expense]:
    get_group(session, group_id)
    query = (
        select(Expense)
        .where(Expense.group_id == group_id)
        .options(selectinload(Expense.shares))
        .order_by(Expense.id)
    )
    return list(session.scalars(query))
```

- [ ] **Step 5: Add expense schemas to `app/schemas.py`**

Replace the import block with:

```python
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StrictInt, StrictStr, StringConstraints, field_validator

from app.money import parse_amount
```

Add after `Currency = ...`:

```python
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
```

Append:

```python
class ExpenseCreate(BaseModel):
    payer_id: StrictInt
    amount: StrictStr
    description: Description
    split_between: Annotated[list[StrictInt], Field(min_length=1)]

    @field_validator("amount")
    @classmethod
    def _amount_is_exact(cls, value: str) -> str:
        parse_amount(value)
        return value

    @field_validator("split_between")
    @classmethod
    def _no_duplicate_members(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("split_between must not contain duplicate member ids")
        return value

    @property
    def amount_cents(self) -> int:
        return parse_amount(self.amount)


class ShareOut(BaseModel):
    member_id: int
    amount: str


class ExpenseOut(BaseModel):
    id: int
    payer_id: int
    amount: str
    description: str
    created_at: datetime
    shares: list[ShareOut]
```

- [ ] **Step 6: Add expense routes to `app/api.py`**

Replace the import block with:

```python
from collections.abc import Iterator
from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import repository, schemas
from app.models import Expense, Group, Member
from app.money import format_cents
```

Add `InvalidExpense` to the error map:

```python
_ERROR_STATUS: dict[type[Exception], int] = {
    repository.GroupNotFound: 404,
    repository.DuplicateMemberName: 409,
    repository.InvalidExpense: 422,
}
```

Add after `_group_out`:

```python
def _expense_out(expense: Expense) -> schemas.ExpenseOut:
    return schemas.ExpenseOut(
        id=expense.id,
        payer_id=expense.payer_id,
        amount=format_cents(expense.amount_cents),
        description=expense.description,
        created_at=expense.created_at.replace(tzinfo=UTC),
        shares=[
            schemas.ShareOut(member_id=share.member_id, amount=format_cents(share.share_cents))
            for share in expense.shares
        ],
    )
```

Append:

```python
@router.post("/groups/{group_id}/expenses", status_code=201)
def record_expense(group_id: int, body: schemas.ExpenseCreate, session: SessionDep) -> schemas.ExpenseOut:
    expense = repository.record_expense(
        session,
        group_id,
        payer_id=body.payer_id,
        amount_cents=body.amount_cents,
        description=body.description,
        split_between=body.split_between,
    )
    return _expense_out(expense)


@router.get("/groups/{group_id}/expenses")
def list_expenses(group_id: int, session: SessionDep) -> list[schemas.ExpenseOut]:
    return [_expense_out(expense) for expense in repository.list_expenses(session, group_id)]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all PASS (Tasks 1–5), including `test_app_code_never_uses_float`.

- [ ] **Step 8: Commit**

```bash
git add app/models.py app/repository.py app/schemas.py app/api.py tests/test_api_expenses.py
git commit -m "feat: record and list equally split expenses" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Balances and settle-up endpoints, README

**Files:**
- Modify: `app/repository.py`, `app/schemas.py`, `app/api.py`
- Create: `tests/test_api_balances.py`, `README.md`

**Interfaces:**
- Consumes: `minimize_transfers`, `Transfer` (Task 3); `format_cents` (Task 1); `get_group`, `Expense`, `ExpenseShare`, fixtures `client`/`make_group`, helper `to_cents` (Tasks 4–5)
- Produces:
  - `app.repository.member_balances(session, group_id) -> list[tuple[Member, int]]` (ordered by member id, every member included)
  - `app.schemas`: `BalanceOut`, `BalancesOut`, `TransferOut`, `SettleUpOut`
  - Routes `GET /groups/{id}/balances`, `GET /groups/{id}/settle-up`

- [ ] **Step 1: Write the failing tests**

`tests/test_api_balances.py`:

```python
import random

from tests.conftest import to_cents


def record(client, group_id, payer_id, amount, split_between, description="Expense"):
    response = client.post(
        f"/groups/{group_id}/expenses",
        json={"payer_id": payer_id, "amount": amount, "description": description, "split_between": split_between},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_balances_start_at_zero_for_every_member(client, make_group):
    group_id, (alice, bob) = make_group("Alice", "Bob", currency="GBP")
    assert client.get(f"/groups/{group_id}/balances").json() == {
        "currency": "GBP",
        "balances": [
            {"member_id": alice, "name": "Alice", "balance": "0.00"},
            {"member_id": bob, "name": "Bob", "balance": "0.00"},
        ],
    }


def test_ten_euros_three_ways_balances_to_exactly_zero(client, make_group):
    group_id, (alice, bob, carol) = make_group("Alice", "Bob", "Carol")
    record(client, group_id, alice, "10.00", [alice, bob, carol])
    balances = client.get(f"/groups/{group_id}/balances").json()["balances"]
    assert [b["balance"] for b in balances] == ["6.66", "-3.33", "-3.33"]
    assert sum(to_cents(b["balance"]) for b in balances) == 0


def test_settle_up_for_ten_euros_three_ways(client, make_group):
    group_id, (alice, bob, carol) = make_group("Alice", "Bob", "Carol")
    record(client, group_id, alice, "10.00", [alice, bob, carol])
    assert client.get(f"/groups/{group_id}/settle-up").json() == {
        "currency": "EUR",
        "optimal": True,
        "transfers": [
            {"from_member_id": bob, "to_member_id": alice, "amount": "3.33"},
            {"from_member_id": carol, "to_member_id": alice, "amount": "3.33"},
        ],
    }


def test_settle_up_with_no_debts(client, make_group):
    group_id, _ = make_group("Alice", "Bob")
    assert client.get(f"/groups/{group_id}/settle-up").json() == {
        "currency": "EUR",
        "optimal": True,
        "transfers": [],
    }


def test_settle_up_uses_fewer_transfers_than_greedy(client, make_group):
    group_id, (a, b, c, d, e) = make_group("A", "B", "C", "D", "E")
    record(client, group_id, a, "4.00", [d, e])  # A +4, D -2, E -2
    record(client, group_id, b, "3.00", [c])  # B +3, C -3
    assert client.get(f"/groups/{group_id}/settle-up").json()["transfers"] == [
        {"from_member_id": c, "to_member_id": b, "amount": "3.00"},
        {"from_member_id": d, "to_member_id": a, "amount": "2.00"},
        {"from_member_id": e, "to_member_id": a, "amount": "2.00"},
    ]


def test_many_uneven_expenses_stay_exact_and_settle_completely(client, make_group):
    rng = random.Random(42)
    group_id, members = make_group("A", "B", "C", "D", "E", "F")
    for _ in range(60):
        payer = rng.choice(members)
        split = rng.sample(members, rng.randint(1, len(members)))
        amount = f"{rng.randint(0, 500)}.{rng.randint(0, 99):02d}"
        if to_cents(amount) == 0:
            continue
        record(client, group_id, payer, amount, split)

    balances = {
        b["member_id"]: to_cents(b["balance"]) for b in client.get(f"/groups/{group_id}/balances").json()["balances"]
    }
    assert sum(balances.values()) == 0

    settle = client.get(f"/groups/{group_id}/settle-up").json()
    assert settle["optimal"] is True
    for transfer in settle["transfers"]:
        balances[transfer["from_member_id"]] += to_cents(transfer["amount"])
        balances[transfer["to_member_id"]] -= to_cents(transfer["amount"])
    assert all(cents == 0 for cents in balances.values())
    assert len(settle["transfers"]) <= len(members) - 1


def test_unknown_group_is_404(client):
    assert client.get("/groups/999/balances").status_code == 404
    assert client.get("/groups/999/settle-up").status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api_balances.py -v`
Expected: FAIL — `/balances` and `/settle-up` return 404 Not Found for existing groups.

- [ ] **Step 3: Add `member_balances` to `app/repository.py`**

Change `from sqlalchemy import select` to:

```python
from sqlalchemy import func, select
```

Append:

```python
def member_balances(session: Session, group_id: int) -> list[tuple[Member, int]]:
    """Each member's net balance in cents (paid - owed), ordered by member id."""
    group = get_group(session, group_id)
    paid = dict(
        session.execute(
            select(Expense.payer_id, func.sum(Expense.amount_cents))
            .where(Expense.group_id == group_id)
            .group_by(Expense.payer_id)
        ).all()
    )
    owed = dict(
        session.execute(
            select(ExpenseShare.member_id, func.sum(ExpenseShare.share_cents))
            .join(Expense, ExpenseShare.expense_id == Expense.id)
            .where(Expense.group_id == group_id)
            .group_by(ExpenseShare.member_id)
        ).all()
    )
    return [(member, paid.get(member.id, 0) - owed.get(member.id, 0)) for member in group.members]
```

- [ ] **Step 4: Add response schemas to `app/schemas.py`**

Append:

```python
class BalanceOut(BaseModel):
    member_id: int
    name: str
    balance: str


class BalancesOut(BaseModel):
    currency: str
    balances: list[BalanceOut]


class TransferOut(BaseModel):
    from_member_id: int
    to_member_id: int
    amount: str


class SettleUpOut(BaseModel):
    currency: str
    optimal: bool
    transfers: list[TransferOut]
```

- [ ] **Step 5: Add routes to `app/api.py`**

Add to the imports:

```python
from app.settlement import minimize_transfers
```

Append:

```python
@router.get("/groups/{group_id}/balances")
def get_balances(group_id: int, session: SessionDep) -> schemas.BalancesOut:
    group = repository.get_group(session, group_id)
    return schemas.BalancesOut(
        currency=group.currency,
        balances=[
            schemas.BalanceOut(member_id=member.id, name=member.name, balance=format_cents(cents))
            for member, cents in repository.member_balances(session, group_id)
        ],
    )


@router.get("/groups/{group_id}/settle-up")
def settle_up(group_id: int, session: SessionDep) -> schemas.SettleUpOut:
    group = repository.get_group(session, group_id)
    balances = {member.id: cents for member, cents in repository.member_balances(session, group_id)}
    transfers, optimal = minimize_transfers(balances)
    return schemas.SettleUpOut(
        currency=group.currency,
        optimal=optimal,
        transfers=[
            schemas.TransferOut(
                from_member_id=transfer.from_member_id,
                to_member_id=transfer.to_member_id,
                amount=format_cents(transfer.amount_cents),
            )
            for transfer in transfers
        ],
    )
```

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -v`
Expected: all PASS.

- [ ] **Step 7: Write `README.md`**

````markdown
# Expense Splitter API

Split group expenses with exact money arithmetic. Amounts are decimal strings on
the wire (`"12.34"`) and integer cents internally — no floating point.

## Run

```bash
uv sync
uv run uvicorn app.main:create_app --factory --reload
```

Data is stored in `./expenses.db` (override with `DATABASE_URL`). Interactive docs at
http://127.0.0.1:8000/docs.

## Test

```bash
uv run pytest
```

## API

| Method | Path | Body |
|---|---|---|
| POST | `/groups` | `{"name": "Trip", "currency": "EUR"}` |
| GET | `/groups/{id}` | |
| POST | `/groups/{id}/members` | `{"name": "Alice"}` |
| GET | `/groups/{id}/members` | |
| POST | `/groups/{id}/expenses` | `{"payer_id": 1, "amount": "10.00", "description": "Taxi", "split_between": [1, 2, 3]}` |
| GET | `/groups/{id}/expenses` | |
| GET | `/groups/{id}/balances` | |
| GET | `/groups/{id}/settle-up` | |

- **Equal splits** give leftover cents to the lowest member ids: `"10.00"` over three
  members is `3.34 + 3.33 + 3.33`.
- **Balances**: positive = the member is owed money, negative = they owe. A group's
  balances always sum to exactly zero.
- **Settle-up** returns the minimum number of transfers (`"optimal": true`) when at most
  20 members have a non-zero balance; beyond that it returns a greedy plan with
  `"optimal": false`.
- Errors: `404` unknown group, `409` duplicate member name, `422` invalid input.
````

- [ ] **Step 8: Smoke-test the running server**

Run:

```bash
SMOKE_DIR=$(mktemp -d)
DATABASE_URL=sqlite:///$SMOKE_DIR/smoke.db uv run uvicorn app.main:create_app --factory --port 8765 &
until curl -s localhost:8765/docs >/dev/null; do sleep 0.2; done
curl -s -X POST localhost:8765/groups -H 'content-type: application/json' -d '{"name":"Trip"}'
curl -s -X POST localhost:8765/groups/1/members -H 'content-type: application/json' -d '{"name":"Alice"}'
curl -s -X POST localhost:8765/groups/1/members -H 'content-type: application/json' -d '{"name":"Bob"}'
curl -s -X POST localhost:8765/groups/1/members -H 'content-type: application/json' -d '{"name":"Carol"}'
curl -s -X POST localhost:8765/groups/1/expenses -H 'content-type: application/json' -d '{"payer_id":1,"amount":"10.00","description":"Taxi","split_between":[1,2,3]}'
curl -s localhost:8765/groups/1/balances
curl -s localhost:8765/groups/1/settle-up
kill %1; rm -rf "$SMOKE_DIR"
```

Expected: balances `6.66 / -3.33 / -3.33`; settle-up shows two transfers of `3.33` to member 1.

- [ ] **Step 9: Commit**

```bash
git add app/repository.py app/schemas.py app/api.py tests/test_api_balances.py README.md
git commit -m "feat: balances and minimum-transfer settle-up endpoints" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
