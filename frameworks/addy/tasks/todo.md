# Tasks: Expense Splitter API

Spec: [`../SPEC.md`](../SPEC.md) · Plan: [`plan.md`](plan.md)

Every task also meets the standing Definition of Done: tests are written first and fail without the change, `uv run pytest` passes, `uv run mypy src` and `uv run ruff check .` are clean, and there is no float on any money path.

---

## Phase 1: Domain core

### Task 1: Project scaffold + `money` module ✅
**Description:** Create the uv project (Python 3.13, src layout) with the deps and tool config from the spec, plus `money.py`: `parse_amount(str) -> int` and `format_cents(int) -> str`.

**Acceptance criteria:**
- [x] `uv sync` installs fastapi, uvicorn, pydantic, pytest, hypothesis, pytest-cov, httpx, ruff, mypy; `.gitignore` excludes `.venv`, `*.db` and caches
- [x] `parse_amount` accepts `"10"`, `"10.5"`, `"10.50"`, `"1000000000.00"`; rejects `"0"`, `"0.00"`, `"-1"`, `"1.234"`, `"1e3"`, `" 1"`, `""`, and values over the max (raises `ValueError`)
- [x] `format_cents` outputs `"0.00"`, `"0.01"`, `"-3.33"`, `"1000000000.00"`; hypothesis round-trip `parse(format(c)) == c` for valid `c`

**Verification:** `uv run pytest tests/test_money.py`; `uv run mypy src`; 100% coverage on `money.py`

**Dependencies:** None
**Files:** `pyproject.toml`, `.gitignore`, `src/expense_splitter/__init__.py`, `src/expense_splitter/money.py`, `tests/test_money.py`
**Scope:** S

### Task 2: Equal split + balances ✅
**Description:** `split.split_equally(total, member_ids) -> list[tuple[str, int]]` (order-preserving, remainder to first members) and `balances.compute_balances(member_ids, expenses) -> dict[str, int]`, where each expense is (payer, shares).

**Acceptance criteria:**
- [x] 1000 / [a,b,c] → 334, 333, 333; 1 / [a,b,c] → 1, 0, 0; 10000 / 7 sums to 10000; empty member list raises `ValueError`
- [x] Balances include every member (zeros too); the payer gets credited even when not in the split
- [x] Hypothesis: shares always sum to the total and differ by at most 1; Σ balances == 0 for random expense lists

**Verification:** `uv run pytest tests/test_split.py tests/test_balances.py`; 100% coverage on `split.py`

**Dependencies:** Task 1
**Files:** `src/expense_splitter/split.py`, `src/expense_splitter/balances.py`, `tests/test_split.py`, `tests/test_balances.py`
**Scope:** S

### Task 3: Exact minimum settle-up ✅
**Description:** `settle.settle_up(balances: list[tuple[str, int]]) -> list[Transfer]` where `Transfer(from_id, to_id, amount)`. Uses the bitmask DP for maximum disjoint zero-sum subsets when there are ≤ 20 non-zero balances, then greedy matching inside each subset. Above 20 it falls back to greedy. Deterministic, using the input order as the tiebreak.

**Acceptance criteria:**
- [x] Applying the transfers zeroes every balance; all amounts > 0; never debtor→debtor; an all-zero input returns `[]`
- [x] Transfer count equals the brute-force minimum (hypothesis, ≤ 8 non-zero balances), including a hand case where naive greedy uses more transfers
- [x] 20 non-zero balances finish in < 2s; 25 balances use the greedy fallback and still zero all balances; identical input gives identical output

**Verification:** `uv run pytest tests/test_settle.py`; 100% coverage on `settle.py`

**Dependencies:** Task 1
**Files:** `src/expense_splitter/settle.py`, `tests/test_settle.py`
**Scope:** S (algorithmically the riskiest task)

### ✅ Checkpoint A: Domain core
- [x] Full suite green; mypy strict and ruff clean
- [x] 100% coverage on `money.py`, `split.py`, `settle.py`
- [ ] **Human review** of the settle-up algorithm before continuing (deferred: `/build auto` run; flagged in summary)

---

## Phase 2: Persistence + API slices

### Task 4: SQLite schema + repository ✅
**Description:** `db.py` (`connect(path)` with FK pragma and `Row` factory, `init_schema(conn)` using the spec DDL) and `repository.py` with functions for: create/get group, add/list members (ordered by `position`), insert expense with shares in one transaction, list expenses with shares (ordered by creation, shares by `position`).

**Acceptance criteria:**
- [x] Round-trip tests against a temp DB file for each repository function; all money columns are `INTEGER` cents
- [x] A duplicate member name (case-insensitive) raises a distinct `DuplicateMemberError`; an FK violation raises `sqlite3.IntegrityError`
- [x] A failing share insert rolls back the expense row (no partial expense)

**Verification:** `uv run pytest tests/test_repository.py`

**Dependencies:** Task 1
**Files:** `src/expense_splitter/db.py`, `src/expense_splitter/repository.py`, `tests/test_repository.py`
**Scope:** S

### Task 5: App factory, error handling, groups endpoints ✅
**Description:** `create_app(db_path)` with the per-request connection dependency; `ApiError` plus global handlers (validation → 400, malformed JSON → 400, `ApiError` → its status); camelCase base model; `POST /groups`, `GET /groups/{group_id}`; `main.app` built from `EXPENSES_DB_PATH`; test fixtures.

**Acceptance criteria:**
- [x] `POST /groups {"name":"Trip"}` → 201 with `id`, `name`, `currency:"EUR"`, `members:[]`; a custom `currency:"USD"` is accepted; `"usd"`/`"EURO"` → 400
- [x] Empty/whitespace/over-100-char name, missing body and malformed JSON → 400 `{"error":{"code":"VALIDATION_ERROR",...}}`
- [x] `GET /groups/{unknown}` → 404 `GROUP_NOT_FOUND`; response keys match the spec exactly

**Verification:** `uv run pytest tests/test_api.py -k group`; manual: `uv run uvicorn expense_splitter.main:app` + `curl -XPOST localhost:8000/groups -d '{"name":"Trip"}' -H 'content-type: application/json'`

**Dependencies:** Task 4
**Files:** `src/expense_splitter/schemas.py`, `src/expense_splitter/errors.py`, `src/expense_splitter/main.py`, `tests/conftest.py`, `tests/test_api.py`
**Scope:** M

### Task 6: Add-member endpoint ✅
**Description:** `POST /groups/{group_id}/members`; members appear in `GET /groups/{id}` in join order.

**Acceptance criteria:**
- [x] 201 `{id, name}`; the name is trimmed; members are listed in join order on the group
- [x] Duplicate name (case-insensitive, e.g. "Ana" vs "ana") → 409 `DUPLICATE_MEMBER`; invalid name → 400; unknown group → 404
- [x] The same name in two different groups is allowed

**Verification:** `uv run pytest tests/test_api.py -k member`

**Dependencies:** Task 5
**Files:** `src/expense_splitter/main.py`, `src/expense_splitter/schemas.py`, `tests/test_api.py`
**Scope:** S

### Task 7: Expense endpoints (record + list) ✅
**Description:** `POST /groups/{group_id}/expenses` validates the input, runs `split_equally` and persists the expense and its shares; `GET /groups/{group_id}/expenses` lists expenses oldest first with `shares`.

**Acceptance criteria:**
- [x] €10.00 among [a,b,c] → 201 with `splitType:"equal"`, shares `"3.34","3.33","3.33"` in request order, `amount:"10.00"`, `createdAt` in ISO-8601 UTC
- [x] 400s: numeric `amount` (`10.5`), `"1.234"`, `"0"`, empty description, empty or duplicate `splitBetween`; a non-member payer or split member (including a member of *another* group) → 400 `UNKNOWN_MEMBER`; unknown group → 404
- [x] The list endpoint returns `{"expenses":[...]}` in creation order with exact camelCase keys; the payer doesn't have to be in the split

**Verification:** `uv run pytest tests/test_api.py -k expense`

**Dependencies:** Tasks 2, 6
**Files:** `src/expense_splitter/main.py`, `src/expense_splitter/schemas.py`, `tests/test_api.py`
**Scope:** M

### ✅ Checkpoint B: Data entry flow
- [x] Full suite green; mypy and ruff clean
- [x] Manual run: uvicorn + curl through create group → add 3 members → record expense → list expenses
- [x] All validation error codes have tests

---

## Phase 3: Read side + finish

### Task 8: Balances endpoint ✅
**Description:** `GET /groups/{group_id}/balances` loads members and stored shares, runs `compute_balances` and formats the result.

**Acceptance criteria:**
- [x] The 10.00/3 example with payer `a` → `a:"6.66"`, `b:"-3.33"`, `c:"-3.33"`; summing the parsed balances gives 0
- [x] Every member is listed in join order, including `"0.00"` and members with no expenses; `currency` is present; unknown group → 404
- [x] A multi-expense scenario (several payers and overlapping splits) matches hand-computed values

**Verification:** `uv run pytest tests/test_api.py -k balance`

**Dependencies:** Task 7
**Files:** `src/expense_splitter/main.py`, `src/expense_splitter/schemas.py`, `tests/test_api.py`
**Scope:** S

### Task 9: Settle-up endpoint
**Description:** `GET /groups/{group_id}/settle-up` computes balances (in member join order) and runs `settle_up`, returning `{currency, transfers:[{fromMemberId,toMemberId,amount}]}`.

**Acceptance criteria:**
- [ ] A group with no expenses, or an already-balanced one, → `"transfers": []`
- [ ] For the multi-expense scenario, applying the returned transfers to the `/balances` output zeroes everything, and the count matches the known minimum
- [ ] Unknown group → 404; same data gives the same response

**Verification:** `uv run pytest tests/test_api.py -k settle`

**Dependencies:** Tasks 3, 8
**Files:** `src/expense_splitter/main.py`, `src/expense_splitter/schemas.py`, `tests/test_api.py`
**Scope:** S

### Task 10: Restart persistence, README, final quality gates
**Description:** Prove data survives an app restart, write a short README (setup, commands, API summary with curl examples), and close any coverage gaps.

**Acceptance criteria:**
- [ ] Test: two `create_app(same_path)` instances; data written by the first is read by the second (group, members, expenses, balances)
- [ ] `uv run pytest --cov=expense_splitter --cov-report=term-missing` ≥ 90% overall and 100% on money/split/settle
- [ ] `uv run mypy src`, `uv run ruff check .` and `uv run ruff format --check .` are clean; the README commands work as written

**Verification:** run all commands from the spec's Commands section; walk the 8 spec Success Criteria

**Dependencies:** Task 9
**Files:** `tests/test_api.py` (or `tests/test_persistence.py`), `README.md`
**Scope:** S

### ✅ Checkpoint C: Complete
- [ ] All 8 spec Success Criteria checked off with evidence
- [ ] Ready for review (`/review`)
