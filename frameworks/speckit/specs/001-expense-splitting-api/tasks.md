---

description: "Task list for the Expense Splitting API"
---

# Tasks: Expense Splitting API

**Input**: Design documents from `/specs/001-expense-splitting-api/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: REQUIRED. The spec (FR-014) and Constitution Principle I require every behavior to
have automated tests. Within each story, write the tests first and confirm they FAIL before
implementing.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested
on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Paths are relative to the repository root (single project, `src/` layout)

## Global rules for every task

- Money is ALWAYS an `int` number of cents internally. Never use `float`, `Decimal`
  rounding, or `round()` for money (Constitution II).
- At the API boundary money is a JSON string matching `^(0|[1-9][0-9]*)\.[0-9]{2}$` for
  inputs and `^-?(0|[1-9][0-9]*)\.[0-9]{2}$` for outputs. JSON numbers in money fields are
  rejected with 422.
- All errors use `{"error": {"code": "...", "message": "...", "field": "..."}}` with codes
  `not_found` (404), `duplicate_member_name` (409), `validation_error` (422).
- Rejected requests store nothing.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create `pyproject.toml` for a `uv` project named `splitit` (Python `>=3.12`, `src/` layout, package `splitit`) with dependencies `fastapi`, `pydantic>=2`, `uvicorn`, `numpy`, and dev dependencies `pytest`, `hypothesis`, `httpx`; add `[tool.pytest.ini_options]` with `testpaths = ["tests"]` and `pythonpath = ["src"]`; then run `uv sync` to create `uv.lock`
- [X] T002 Create package and test directories with empty `__init__.py` files: `src/splitit/__init__.py`, `tests/__init__.py`, `tests/unit/__init__.py`, `tests/property/__init__.py`, `tests/api/__init__.py`, `tests/perf/__init__.py`
- [X] T003 [P] Create `.gitignore` at repository root ignoring `.venv/`, `__pycache__/`, `.pytest_cache/`, `.hypothesis/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Money handling, domain models, storage, errors and app wiring needed by every story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 [P] Write unit tests in `tests/unit/test_money.py` for `parse_money(s: str) -> int` and `format_money(cents: int) -> str`: `"10.00"`→1000, `"0.01"`→1, `"1000000000.00"`→100000000000; reject `"10.5"`, `"10.005"`, `"1e3"`, `"-5.00"`, `"010.00"`, `"10"`, `""`, `" 10.00"` with `MoneyFormatError`; `format_money(-333)`→`"-3.33"`, `format_money(0)`→`"0.00"`, `format_money(5)`→`"0.05"`; round-trip property for ints 0..10^12
- [X] T005 [P] Implement `src/splitit/money.py`: `MoneyFormatError(ValueError)`; `parse_money` validating against regex `^(0|[1-9][0-9]*)\.[0-9]{2}$` and converting by string split into `int(whole) * 100 + int(frac)` (no float, no Decimal); `format_money` handling negatives via `divmod(abs(cents), 100)`; constants `MAX_EXPENSE_CENTS = 100_000_000_000` and `MIN_EXPENSE_CENTS = 1`
- [X] T006 [P] Create domain dataclasses in `src/splitit/models.py`: `Member(id: str, group_id: str, name: str)`, `Share(member_id: str, amount_cents: int)`, `Expense(id, group_id, description: str, amount_cents: int, payer_id: str, shares: list[Share], created_at: datetime)`, `Group(id, name: str, created_at: datetime, members: list[Member], expenses: list[Expense])`, `Transfer(from_member_id: str, to_member_id: str, amount_cents: int)`; IDs are `str(uuid.uuid4())`, timestamps `datetime.now(timezone.utc)`; constant `MAX_MEMBERS_PER_GROUP = 20`
- [X] T007 [P] Implement `src/splitit/errors.py`: exception classes `NotFoundError(message, field=None)` → 404 `not_found`, `DuplicateMemberNameError(message, field="name")` → 409 `duplicate_member_name`, `ValidationFailedError(message, field=None)` → 422 `validation_error`; function `register_error_handlers(app)` mapping these plus FastAPI `RequestValidationError` (use the first error's `loc` last element as `field` and its `msg` as `message`) to the Error schema in `contracts/openapi.yaml`
- [X] T008 Implement `src/splitit/repository.py`: class `InMemoryRepository` holding `dict[str, Group]` with a `threading.Lock` around writes; methods `create_group(name) -> Group`, `get_group(group_id) -> Group` (raises `NotFoundError(field="group_id")`), `add_member(group_id, name) -> Member`, `add_expense(group_id, expense) -> Expense`; member/expense validation is added in later stories (depends on T006, T007)
- [X] T009 Implement app factory in `src/splitit/main.py`: `create_app() -> FastAPI` creating a fresh `InMemoryRepository`, storing it on `app.state.repository`, calling `register_error_handlers`, and including the router from `src/splitit/api.py`; module-level `app = create_app()`; create `src/splitit/api.py` with an empty `APIRouter` and a dependency `get_repository(request) -> InMemoryRepository` (depends on T007, T008)
- [X] T010 Create `tests/conftest.py` with a `client` fixture returning `fastapi.testclient.TestClient(create_app())` so every test gets a fresh, empty store (depends on T009)
- [X] T011 [P] Create `src/splitit/schemas.py` with a reusable Pydantic input type `MoneyIn` that accepts ONLY `str` (strict; a JSON number fails validation) and converts via `parse_money`, raising a validation error that names the field; and helper `money_out(cents: int) -> str` wrapping `format_money` (depends on T005)

**Checkpoint**: `uv run pytest` runs and money tests pass — user story work can begin

---

## Phase 3: User Story 1 - Create a group and add members (Priority: P1) 🎯 MVP

**Goal**: Users can create a named group, add uniquely named members, and retrieve the group.

**Independent Test**: Create a group, add three members, `GET` the group and confirm its name and all three members (with IDs) are returned.

### Tests for User Story 1 ⚠️

> Write these tests FIRST and ensure they FAIL before implementation

- [X] T012 [P] [US1] API tests in `tests/api/test_groups.py`: `POST /groups {"name":"Lisbon trip"}` → 201 with `id`, `name`, `members: []`; `GET /groups/{id}` → 200 same body; name trimmed (`"  Trip  "` → `"Trip"`); empty name, whitespace-only name, name of 101 chars, missing `name`, extra field → 422 `validation_error` with `field: "name"` (or the extra field); `GET /groups/<random uuid>` → 404 `not_found`
- [X] T013 [P] [US1] API tests in `tests/api/test_members.py`: add Ana, Ben, Cleo → 201 each with distinct `id`; `GET /groups/{id}` lists them in insertion order; adding `"ana"` or `" ANA "` again → 409 `duplicate_member_name`, `field: "name"`; empty name / 101-char name → 422; adding to an unknown group → 404; adding a 21st member → 422 with a message stating the 20-member limit; rejected requests leave the member list unchanged

### Implementation for User Story 1

- [X] T014 [US1] Add Pydantic models to `src/splitit/schemas.py`: `CreateGroup` and `CreateMember` (`name: str`, stripped, "Required; trimmed; 1–100 chars", `extra="forbid"`), `MemberOut(id, name)`, `GroupOut(id, name, members: list[MemberOut])`
- [X] T015 [US1] Extend `InMemoryRepository.add_member` in `src/splitit/repository.py` to enforce member name "unique per group, case-insensitive" (compare `name.strip().casefold()`; raise `DuplicateMemberNameError`) and the "max 20" member limit (raise `ValidationFailedError(field="name")`)
- [X] T016 [US1] Implement routes in `src/splitit/api.py`: `POST /groups` (201, `GroupOut`), `GET /groups/{group_id}` (200, `GroupOut`), `POST /groups/{group_id}/members` (201, `MemberOut`), per `contracts/openapi.yaml`

**Checkpoint**: User Story 1 tests pass; groups and members work end to end

---

## Phase 4: User Story 2 - Record an expense split equally (Priority: P1)

**Goal**: A member records an expense (payer, amount, description, participants) that is split equally, exact to the cent.

**Independent Test**: With Ana, Ben, Cleo, record "Dinner" `"30.00"` paid by Ana for all three; `GET /groups/{id}/expenses` shows the expense with three shares of `"10.00"`.

### Tests for User Story 2 ⚠️

- [X] T017 [P] [US2] Unit tests in `tests/unit/test_splitting.py` for `split_equally(amount_cents, n)`: (3000, 3)→[1000,1000,1000]; (1000, 3)→[334,333,333]; (1, 3)→[1,0,0]; (200, 3)→[67,67,66]; (5, 1)→[5]; `n < 1` or `amount_cents < 1` → `ValueError`
- [X] T018 [P] [US2] Property test in `tests/property/test_invariants.py` (hypothesis): for amount in 1..100_000_000_000 and n in 1..20, `sum(split_equally(a, n)) == a`, `len == n`, max−min ≤ 1, shares non-increasing (leftover cents go to earliest participants)
- [X] T019 [P] [US2] API tests in `tests/api/test_expenses.py`: "Dinner" `"30.00"` → shares `"10.00"`×3; "Taxi" `"10.00"` split Ana, Ben, Cleo → `"3.34"`, `"3.33"`, `"3.33"` in that order; listing participants as Cleo, Ana, Ben gives Cleo the `"3.34"`; payer not among participants accepted; payer as only participant accepted; `GET /groups/{id}/expenses` returns expenses in recording order with `id`, `payer_id`, `amount`, `description`, `shares`, `created_at`; rejections → 422 and no expense stored: amount `"0.00"`, `"-5.00"`, `"10.005"`, `"10.5"`, `10.0` (JSON number), `"1000000000.01"`, empty/whitespace description, description of 201 chars, `participant_ids: []`, duplicate participant IDs; unknown payer or participant (incl. a member of another group) → 404 `not_found` with `field` `payer_id` / `participant_ids`; unknown group → 404

### Implementation for User Story 2

- [X] T020 [US2] Implement `split_equally(amount_cents: int, n: int) -> list[int]` in `src/splitit/splitting.py`: `base, r = divmod(amount_cents, n)`; participant at index `i` owes `base + (1 if i < r else 0)`; this is the ONLY place money is divided (Money Handling Constraints)
- [X] T021 [US2] Add to `src/splitit/schemas.py`: `CreateExpense` (`payer_id: str`, `amount: MoneyIn` with "1 ≤ amount ≤ 100,000,000,000" cents, `description: str` "Required; trimmed; 1–200 chars", `participant_ids: list[str]` min 1 item and no duplicates, `extra="forbid"`), `ShareOut(member_id, amount: str)`, `ExpenseOut(id, payer_id, amount: str, description, shares: list[ShareOut], created_at)`, `ExpenseListOut(expenses: list[ExpenseOut])`
- [X] T022 [US2] Implement `record_expense(group_id, payer_id, amount_cents, description, participant_ids) -> Expense` in `src/splitit/repository.py`: verify payer and every participant belong to the group (else `NotFoundError` with the field name), compute shares with `split_equally` in request order, append atomically under the lock
- [X] T023 [US2] Implement routes in `src/splitit/api.py`: `POST /groups/{group_id}/expenses` (201, `ExpenseOut`) and `GET /groups/{group_id}/expenses` (200, `ExpenseListOut`), formatting all amounts with `money_out`

**Checkpoint**: User Stories 1 and 2 tests pass

---

## Phase 5: User Story 3 - View net balances (Priority: P1)

**Goal**: Show each member's net balance (positive = is owed, negative = owes); balances sum to exactly zero.

**Independent Test**: Record known expenses, `GET /groups/{id}/balances`, compare to hand-calculated values, and confirm they sum to `0.00`.

### Tests for User Story 3 ⚠️

- [X] T024 [P] [US3] Unit tests in `tests/unit/test_balances.py` for `compute_balances(group) -> dict[str, int]`: Ana paid 3000 split three ways → Ana +2000, Ben −1000, Cleo −1000; Ana paid 1000 split three ways → +666, −333, −333; payer-only expense → all 0; no expenses → every member 0; result keys in member insertion order
- [X] T025 [P] [US3] Add hypothesis property to `tests/property/test_invariants.py`: for random groups (2–20 members) and random expense lists (random payer, random non-empty participant subset, amount 1..10^9 cents), `sum(compute_balances(group).values()) == 0`
- [X] T026 [P] [US3] API tests in `tests/api/test_balances_api.py`: `GET /groups/{id}/balances` returns `{"balances": [{"member_id","name","balance"}...]}` in member order; spec scenarios: `"20.00"`, `"-10.00"`, `"-10.00"`; Taxi `"10.00"` → `"6.66"`, `"-3.33"`, `"-3.33"` and parsed sum is 0; members with no expenses show `"0.00"`; unknown group → 404

### Implementation for User Story 3

- [X] T027 [US3] Implement `compute_balances(group: Group) -> dict[str, int]` in `src/splitit/balances.py`: start every member at 0, add `amount_cents` to the payer and subtract each share from its member; integers only
- [X] T028 [US3] Add `BalanceOut(member_id, name, balance: str)` and `BalanceListOut(balances: list[BalanceOut])` to `src/splitit/schemas.py`, and route `GET /groups/{group_id}/balances` in `src/splitit/api.py`

**Checkpoint**: User Stories 1–3 tests pass

---

## Phase 6: User Story 4 - Settle up with the fewest transfers (Priority: P2)

**Goal**: A read-only suggestion of transfers that clears all balances exactly using the minimum number of transfers.

**Independent Test**: Record expenses producing known balances, `GET /groups/{id}/settle-up`, apply the transfers by hand, and confirm all balances become exactly zero with the minimum count.

### Tests for User Story 4 ⚠️

- [X] T029 [P] [US4] Unit tests in `tests/unit/test_settle.py` for `minimum_transfers(balances: dict[str, int]) -> list[Transfer]`: {A:+2000, B:−1000, C:−1000} → B→A 1000, C→A 1000; {A:+500, B:−500, C:+700, D:−700} → exactly 2 transfers (B→A 500, D→C 700); all zero → []; greedy counterexample {a:−700, b:−800, c:+200, d:+600, e:+700} → exactly 3 transfers (research §4); every transfer amount > 0; output sorted by the debtor's position in member order, then the creditor's; deterministic for equal input; the overflow guard path (pure-Python fallback) returns the same result as the NumPy path for a sample input
- [X] T030 [P] [US4] Add hypothesis properties to `tests/property/test_invariants.py`: for random zero-sum balances (2–8 members, values −10^6..10^6), applying `minimum_transfers` output yields all zeros, and the transfer count equals a brute-force minimum computed in the test (pure-Python subset DP over `k − max zero-sum partition count`)
- [X] T031 [P] [US4] API tests in `tests/api/test_settle_up_api.py`: `GET /groups/{id}/settle-up` returns `{"transfers": [{"from_member_id","to_member_id","amount"}...]}`; spec scenarios 1–3; applying transfers to the `/balances` response yields zeros; calling settle-up twice returns identical results and `/balances` is unchanged (read-only, FR-010); unknown group → 404

### Implementation for User Story 4

- [X] T032 [US4] Implement `minimum_transfers` in `src/splitit/settle.py` per research §4: drop zero balances; build subset sums (`numpy.int64`) and `dp` (`numpy.int8`, max zero-sum groups) processed by popcount layer, `dp[mask] = max_i dp[mask without i] + (sum(mask) == 0)`; reconstruct the partition into zero-sum groups by walking back from the full mask; settle each group by repeatedly matching the largest debtor with the largest creditor; if `sum(abs(b)) >= 2**62`, use an equivalent pure-Python integer implementation instead; return transfers sorted by debtor position in member order, then creditor position
- [X] T033 [US4] Add `TransferOut(from_member_id, to_member_id, amount: str)` and `SettleUpOut(transfers: list[TransferOut])` to `src/splitit/schemas.py`, and route `GET /groups/{group_id}/settle-up` in `src/splitit/api.py` computing `minimum_transfers(compute_balances(group))` without mutating state

**Checkpoint**: All four user stories pass their tests independently

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Performance goal, contract conformance and end-to-end validation

- [X] T034 [P] Performance test in `tests/perf/test_performance.py` (SC-005): group with 20 members and 1,000 random expenses (seeded RNG, all members nonzero balances); time `GET /balances` + `GET /settle-up` through `TestClient` and assert total < 1.0 s
- [X] T035 [P] Contract conformance test in `tests/api/test_contract.py`: load `specs/001-expense-splitting-api/contracts/openapi.yaml` and assert every path+method in it is served by the app (compare against `app.openapi()["paths"]`), and that money fields in sample responses match the `Money` pattern
- [X] T036 [P] Add `README.md` at repository root with setup (`uv sync`), test (`uv run pytest`) and run (`uv run uvicorn splitit.main:app --reload`) commands, the money format, and the leftover-cent rule
- [X] T037 Audit `src/splitit/` for any use of `float`, `round(`, or `Decimal` in money paths (`grep -rnE "float|round\(|Decimal" src/splitit`) and remove any found; add `tests/unit/test_no_float_money.py` asserting that grep finds no matches
- [X] T038 Run `uv run pytest` and confirm the full suite passes; then run the manual scenario in `specs/001-expense-splitting-api/quickstart.md` and confirm each expected result

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Stories (Phases 3–6)**: Depend on Foundational
- **Polish (Phase 7)**: Depends on all user stories

### User Story Dependencies

- **US1 (P1)**: After Foundational. No story dependencies.
- **US2 (P1)**: After Foundational. API tests need groups/members, so it builds on US1's routes; `split_equally` (T017, T018, T020) can be built in parallel with US1.
- **US3 (P1)**: Needs expenses from US2 for its API tests; `compute_balances` unit tests (T024, T027) only need the domain models and can start after Foundational.
- **US4 (P2)**: Needs balances from US3 for its API tests; `minimum_transfers` (T029, T030, T032) takes a plain `dict[str, int]` and can be built right after Foundational.

### Within Each User Story

- Tests written first and FAIL before implementation
- Pure domain functions before schemas, schemas before routes
- `src/splitit/api.py`, `src/splitit/schemas.py` and `src/splitit/repository.py` are shared files: tasks touching them run sequentially in task-ID order

### Parallel Opportunities

- Phase 2: T004, T005, T006, T007 in parallel; T011 after T005
- Pure domain modules across stories in parallel once Phase 2 is done: `splitting.py` (T017, T020), `balances.py` (T024, T027), `settle.py` (T029, T032)
- All test tasks marked [P] within a story
- Phase 7: T034, T035, T036 in parallel

---

## Parallel Example: User Story 4

```bash
# Tests together (different files):
Task: "Unit tests for minimum_transfers in tests/unit/test_settle.py"
Task: "Settle-up API tests in tests/api/test_settle_up_api.py"

# Then the pure algorithm, independent of the web layer:
Task: "Implement minimum_transfers in src/splitit/settle.py"
```

## Parallel Example: Domain core after Phase 2

```bash
Task: "Implement split_equally in src/splitit/splitting.py"
Task: "Implement compute_balances in src/splitit/balances.py"
Task: "Implement minimum_transfers in src/splitit/settle.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1: Setup
2. Phase 2: Foundational
3. Phase 3: User Story 1
4. **STOP and VALIDATE**: `uv run pytest tests/api/test_groups.py tests/api/test_members.py`

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → groups and members (MVP)
3. US2 → expenses with exact equal splits
4. US3 → balances (core value delivered)
5. US4 → minimum-transfer settle-up
6. Polish → performance, contract check, README, quickstart validation

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- Every FR maps to tests: FR-001/002 → T012; FR-003 → T013; FR-004/012/013 → T019; FR-005 → T017, T018, T019; FR-006 → T019; FR-007 → T024–T026; FR-008/009 → T029–T031; FR-010 → T031; FR-011 → T004, T019; FR-014 → T038
- Commit after each task or logical group

---

## Phase 8: Convergence

- [X] T039 CRITICAL: Add API tests asserting the 422 `validation_error` response shape (and `field` where applicable) for currently untested behaviors: malformed JSON body (`{bad`) and empty body on `POST /groups`; a JSON array body on `POST /groups`; non-string items in `participant_ids` (`[1]`) on `POST /groups/{id}/expenses`; an extra field on `POST /groups/{id}/members`; and acceptance (201) of a description of exactly 200 characters — in `tests/api/test_groups.py`, `tests/api/test_members.py`, `tests/api/test_expenses.py` per Constitution I (partial)
- [X] T040 Let `POST /groups` accept an optional `members: list[str]` (each name "Required; trimmed; 1–100 chars", unique per group case-insensitive, max 20; any invalid or duplicate name rejects the whole request with nothing stored) and return them in `GroupOut.members`, so group + members + expense + balances takes 4 requests; update `CreateGroup` in `src/splitit/schemas.py`, `InMemoryRepository.create_group` in `src/splitit/repository.py`, the route in `src/splitit/api.py`, the `CreateGroup` schema in `specs/001-expense-splitting-api/contracts/openapi.yaml`, and add tests in `tests/api/test_groups.py` including a 4-request end-to-end flow per SC-004 (partial)
- [X] T041 Strip Pydantic's `"Value error, "` prefix from validation messages in `_handle_request_validation` in `src/splitit/errors.py` so messages read e.g. `amount: invalid amount '10.005': expected exactly two decimals`, and assert the cleaned message in `tests/api/test_expenses.py` per FR-012 (partial)
