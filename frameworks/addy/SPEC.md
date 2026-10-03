# Spec: Expense Splitter API

Status: **APPROVED** (2026-10-03). Decisions: no auth, SQLite, exact minimum settle-up, remainder to first-listed members, Python stack, camelCase JSON, 400 for validation errors.

## Decisions & Assumptions

1. **No authentication.** "Any member can record an expense" means the API trusts the caller; payer and participants must be members of the group, but caller identity is not verified.
2. **SQLite persistence** via the standard-library `sqlite3` module (no ORM). DB file path from `EXPENSES_DB_PATH` (default `./expenses.db`); tests use a fresh temporary database per test.
3. **One currency per group, 2 decimal places** (e.g. EUR). No conversion. Currency code is stored for display only; default `EUR`.
4. **Money travels as decimal strings** in JSON (`"10.00"`), never JSON numbers. Internally and in the database, all money is **integer cents** (`int` / SQLite `INTEGER`).
5. **Append-only for v1:** no editing/deleting expenses, no removing members, no recording settlements as payments.
6. **Remainder cents in equal splits** go one each to the first participants in the order the IDs appear in `splitBetween`. (€10.00 / 3 → 3.34, 3.33, 3.33.)
7. **Settle-up returns the exact minimum number of transfers.**
8. Groups hold **at most 50 members**, enforced: adding a 51st member → `409 GROUP_FULL`. This bounds settle-up cost, which is exponential in the number of non-zero balances (see Settle-up rules).

## Objective

A small HTTP JSON API that lets a group of people record shared expenses and see who owes whom.

User stories:
- As a user, I create a group and add members to it by name.
- As a member, I record an expense: who paid, how much, a description, and which members share it equally (the payer may or may not be among them).
- As a member, I see each member's net balance in the group.
- As a member, I ask how to settle up and get the fewest transfers that bring every balance to zero.

Success means every amount shown is exact to the cent, balances always sum to exactly zero, and the suggested transfers clear all debts exactly.

## API Contract

All bodies are JSON. IDs are server-generated UUID4 strings.

| Method | Path | Body | Success |
|---|---|---|---|
| POST | `/groups` | `{ "name": str, "currency"?: str }` | 201 Group |
| GET | `/groups/{group_id}` | — | 200 Group (with members) |
| POST | `/groups/{group_id}/members` | `{ "name": str }` | 201 Member |
| POST | `/groups/{group_id}/expenses` | `{ "payerId", "amount", "description", "splitBetween": [memberId, ...] }` | 201 Expense |
| GET | `/groups/{group_id}/expenses` | — | 200 `{ "expenses": [Expense] }` (oldest first) |
| GET | `/groups/{group_id}/balances` | — | 200 Balances |
| GET | `/groups/{group_id}/settle-up` | — | 200 SettleUp |

Shapes:

```jsonc
// Group
{ "id": "…", "name": "Trip", "currency": "EUR", "members": [ { "id": "…", "name": "Ana" } ] }

// Member
{ "id": "…", "name": "Ana" }

// Expense — `shares` records the exact cent allocation, so later split types (exact / percentage)
// plug in without changing how balances are computed or returned.
{
  "id": "…", "payerId": "…", "amount": "10.00", "description": "Taxi",
  "splitType": "equal",
  "shares": [ { "memberId": "a", "amount": "3.34" }, { "memberId": "b", "amount": "3.33" }, { "memberId": "c", "amount": "3.33" } ],
  "createdAt": "2026-10-03T12:00:00Z"
}

// Balances — positive = is owed money, negative = owes money.
// One entry per member (including "0.00"), in member join order.
{ "currency": "EUR", "balances": [ { "memberId": "a", "name": "Ana", "balance": "6.66" } ] }

// SettleUp
{ "currency": "EUR", "transfers": [ { "fromMemberId": "b", "toMemberId": "a", "amount": "3.33" } ] }

// Error (all 4xx/5xx)
{ "error": { "code": "VALIDATION_ERROR", "message": "amount must have at most 2 decimal places" } }
```

Validation rules:
- `name` (group, member): non-empty after trim, ≤ 100 chars. Member names unique within a group, case-insensitive → `409 DUPLICATE_MEMBER`.
- A group already holding 50 members rejects new members → `409 GROUP_FULL` (checked atomically with the insert).
- `currency`: 3 uppercase letters.
- `amount`: JSON string matching `^\d+(\.\d{1,2})?$`, > 0, ≤ `"1000000000.00"`. JSON numbers are rejected (`400 VALIDATION_ERROR`).
- `description`: non-empty after trim, ≤ 200 chars.
- `payerId` and every `splitBetween` ID must be members of this group → `400 UNKNOWN_MEMBER`.
- `splitBetween`: non-empty, no duplicates.
- Unknown group → `404 GROUP_NOT_FOUND`. Malformed JSON / schema violations → `400 VALIDATION_ERROR` (FastAPI's default 422 is overridden to 400 with the error shape above).

Money rules:
- Parsing `"10.5"` → 1050 cents is done by string manipulation (or `decimal.Decimal`), never `float`.
- Equal split of `A` cents among `n` people: each gets `A // n`; the first `A % n` participants (request order) get one extra cent. Shares always sum to exactly `A`.
- Balance(member) = Σ cents paid − Σ cents of their shares. Σ balances = 0 always.
- Formatting: cents → `"-3.33"` / `"0.00"` (always two decimals, `-` prefix for negatives).

Settle-up rules:
- Only members with non-zero balances participate. Each transfer goes from a debtor to a creditor with a positive amount.
- Applying all transfers brings every balance to exactly 0.
- Transfer count is the true minimum: `k − m`, where `k` = members with non-zero balance and `m` = maximum number of disjoint zero-sum subsets of those balances. Computed with a bitmask DP over subsets (O(2^k · k)); within each zero-sum subset, transfers are produced by greedy debtor/creditor matching (exactly `|subset| − 1` transfers).
- Practical limit: `k ≤ 20` uses the exact DP. If `k > 20` (only possible in groups larger than 20), fall back to greedy matching over the whole group (≤ `k − 1` transfers, not guaranteed minimal). Documented, not an error.
- Output is deterministic for the same data (ties broken by member join order).
- Results are memoized in-process, keyed by the group's exact balance vector (`(memberId, cents)` in join order), LRU-bounded to 1024 entries. Any change to a group's balances is a new key, so a stale result can never be served and no explicit invalidation is needed; repeated reads of an unchanged group cost one balance query, not a recomputation.

## Data Model (SQLite)

```sql
CREATE TABLE groups   (id TEXT PRIMARY KEY, name TEXT NOT NULL, currency TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE members  (id TEXT PRIMARY KEY, group_id TEXT NOT NULL REFERENCES groups(id), name TEXT NOT NULL,
                       position INTEGER NOT NULL, UNIQUE (group_id, name COLLATE NOCASE));
CREATE TABLE expenses (id TEXT PRIMARY KEY, group_id TEXT NOT NULL REFERENCES groups(id),
                       payer_id TEXT NOT NULL REFERENCES members(id), amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                       description TEXT NOT NULL, split_type TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE expense_shares (expense_id TEXT NOT NULL REFERENCES expenses(id), member_id TEXT NOT NULL REFERENCES members(id),
                       position INTEGER NOT NULL, amount_cents INTEGER NOT NULL, PRIMARY KEY (expense_id, member_id));
```

- `PRAGMA foreign_keys = ON` on every connection.
- An expense and its shares are inserted in one transaction.
- Schema created on startup (`CREATE TABLE IF NOT EXISTS`); no migration tool for v1.

## Tech Stack

- Python 3.13 (installed via Homebrew), managed with **uv** (already installed)
- **FastAPI** + **Pydantic v2** — routing and request validation
- **uvicorn** — ASGI server
- stdlib **sqlite3** — persistence
- **pytest** + FastAPI `TestClient` (httpx) — tests
- **hypothesis** — property-based tests for money invariants
- **pytest-cov** — coverage
- **ruff** (lint + format), **mypy --strict** (type checking)

## Commands

```
Install:    uv sync
Dev:        uv run uvicorn expense_splitter.main:app --reload --port 8000
Test:       uv run pytest
Coverage:   uv run pytest --cov=expense_splitter --cov-report=term-missing
Lint:       uv run ruff check . && uv run ruff format --check .
Typecheck:  uv run mypy src
```

## Project Structure

```
addy/
  SPEC.md                    → this document
  pyproject.toml             → deps + tool config (pytest, ruff, mypy, coverage)
  tasks/plan.md, todo.md     → implementation plan (Phase 2)
  src/expense_splitter/
    money.py                 → parse/format decimal strings ↔ integer cents
    split.py                 → equal split allocation
    balances.py              → net balance computation
    settle.py                → minimum-transfer settle-up
    db.py                    → connection factory + schema
    repository.py            → SQL for groups, members, expenses, shares
    schemas.py               → Pydantic request/response models
    errors.py                → ApiError + exception handlers
    main.py                  → create_app(db_path) factory + `app`
  tests/
    test_money.py, test_split.py, test_balances.py, test_settle.py   → unit + property
    test_repository.py                                                → SQLite round-trips
    test_api.py                                                       → HTTP integration
    conftest.py                                                       → temp-DB app/client fixtures
```

Domain modules (`money`, `split`, `balances`, `settle`) are pure functions — no FastAPI, Pydantic, or sqlite imports.

## Code Style

```python
# Pure, typed, cents-in / cents-out. No floats anywhere in money paths.
Cents = int


def split_equally(total: Cents, member_ids: Sequence[str]) -> dict[str, Cents]:
    """Split `total` cents equally; the first `total % n` members get one extra cent."""
    base, remainder = divmod(total, len(member_ids))
    return {mid: base + (1 if i < remainder else 0) for i, mid in enumerate(member_ids)}
```

- PEP 8 snake_case in Python; **camelCase in all JSON** (requests and responses). Pydantic models use `alias_generator=to_camel` with `populate_by_name=True`, and responses serialize `by_alias=True`. Path params stay `{group_id}` in route code (not visible in JSON).
- Full type hints; `mypy --strict` clean. Ruff defaults, line length 100.
- `float` is banned in money paths (no `float(...)`, `/` on cents, or `round()`); integer `//`, `%`, `divmod` only.
- Errors raised as `ApiError(status, code, message)` and mapped to the error shape by one handler.

## Testing Strategy

- **Unit:** money parsing/formatting edge cases (`"0.1"`, `"10"`, `"1.234"` rejected, `"-1"` rejected, `"0"` rejected, max value); equal split remainders (10.00/3, 0.01/3, 100.00/7); balances; settle-up on hand-built cases (chains, cycles, already-settled, multiple zero-sum subgroups where greedy is suboptimal).
- **Property (hypothesis):** shares sum to amount; Σ balances = 0; applying transfers zeroes every balance; transfer count equals a brute-force minimum for ≤ 8 non-zero balances; format(parse(s)) round-trips.
- **Repository:** SQLite round-trips against a temp DB, including the expense+shares transaction and foreign-key enforcement.
- **Integration:** every endpoint via `TestClient`, happy paths and each error code; one test confirms data persists across two app instances sharing a DB file.
- Coverage target: ≥ 90% lines on `src/`, 100% on `money.py`, `split.py`, `settle.py`.
- Tests written before implementation for each task (TDD).

## Boundaries

- **Always:** integer cents internally, decimal strings externally; run `uv run pytest` and `uv run mypy src` before declaring a task done; validate all input at the HTTP boundary; parameterized SQL only.
- **Ask first:** adding dependencies beyond those listed; adding auth or an ORM/migrations tool; changing the API response shapes above (especially `/balances`).
- **Never:** use floats for money; silently drop or invent cents; build SQL with string formatting; skip/delete failing tests; commit the `.db` file or secrets.

## Success Criteria

1. All endpoints in the API Contract exist and return the documented shapes (camelCase keys) and status codes.
2. €10.00 split among 3 members yields shares 3.34 / 3.33 / 3.33 and balances summing to exactly 0.00.
3. For any sequence of valid expenses, Σ balances = 0 and each expense's shares sum to its amount (property tests pass).
4. Settle-up transfers, when applied, zero every balance exactly; transfer count equals the brute-force minimum on randomized inputs with ≤ 8 non-zero balances, including cases where naive greedy needs more transfers.
5. Settle-up on a fully settled group returns `"transfers": []`.
6. Invalid input (non-member payer, empty split, duplicate split member, numeric amount, 3-decimal amount, unknown group, duplicate member name, member beyond the 50-member cap) returns the documented 4xx error.
7. Data survives an app restart (same DB file).
8. `uv run pytest`, `uv run mypy src`, and `uv run ruff check .` all pass; coverage meets targets.

## Open Questions

None blocking. Confirm or adjust:
- snake_case JSON field names (`payerId`, `splitBetween`) — natural for Python; say if you'd prefer camelCase.
- Validation errors return `400` rather than FastAPI's default `422`.
