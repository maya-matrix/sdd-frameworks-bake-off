# Implementation Plan: Expense Splitting API

**Branch**: `001-expense-splitting-api` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-expense-splitting-api/spec.md`

## Summary

A JSON web API to create groups, add members, record expenses split equally, view net
balances and get a minimum-transfer settle-up suggestion. Money is held as integer cents and
exchanged as two-decimal strings; equal splits hand out leftover cents in participant order so
shares always sum to the amount. Settle-up finds the true minimum number of transfers with a
subset DP over nonzero balances (NumPy-vectorized to meet the 1 s goal). Built with Python
3.12 + FastAPI, in-memory storage, and a pytest suite (unit, property-based, API,
performance).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI, Pydantic v2, Uvicorn, NumPy (settle-up DP only)

**Storage**: In-memory repository (thread-safe), replaceable behind a repository class

**Testing**: pytest, hypothesis (property-based), FastAPI `TestClient` (httpx)

**Target Platform**: Any OS with Python 3.12; run locally via `uv`

**Project Type**: web-service (single project)

**Performance Goals**: Balances + settle-up for 20 members / 1,000 expenses < 1 s (SC-005)

**Constraints**: No floating point for money; exact minimum settle-up; ≤ 20 members/group

**Scale/Scope**: 6 endpoints, 3 stored entities, single process

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Requirement | Status |
|------|-------------|--------|
| I. Every behavior tested | Each endpoint, rule, validation error and not-found path has a test; single command `uv run pytest`; bug fixes add a failing-first test | PASS — test layers defined in research §6; FR-014 maps every FR to tests |
| II. Exact money — representation | Integer cents internally; no float anywhere in money paths | PASS — research §2 |
| II. Exact money — allocation | Splits allocate every cent by a documented rule | PASS — `divmod` + leftover cents in participant order (research §3) |
| II. Exact money — conservation | Balances sum to 0; settle-up clears all balances exactly | PASS — invariants in data-model; asserted by property tests |
| II. Exact money — boundary | Lossless format; over-precise amounts rejected, not rounded | PASS — two-decimal strings, JSON numbers rejected |
| Money Handling Constraints | Uneven-split tests and conservation assertions; rounding only at a named step | PASS — single named step `split_equally` |
| Quality Gates | Plan names money representation and remainder rule | PASS — this plan |

**Post-design re-check**: PASS. NumPy is used only for the settle-up DP over integer subset
sums (`int64`), never for amounts as floats; an overflow guard falls back to exact Python
ints (research §4). No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-expense-splitting-api/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── openapi.yaml     # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
pyproject.toml           # uv project; deps + pytest config
src/splitit/
├── __init__.py
├── main.py              # FastAPI app factory (create_app) + `app`
├── money.py             # parse/format two-decimal strings <-> int cents
├── splitting.py         # split_equally(amount_cents, n) -> list[int]
├── balances.py          # compute_balances(group) -> dict[member_id, int]
├── settle.py            # minimum_transfers(balances) -> list[Transfer]
├── models.py            # domain dataclasses: Group, Member, Expense, Share, Transfer
├── repository.py        # in-memory store with lock
├── schemas.py           # Pydantic request/response models (Money as str)
├── errors.py            # error types + handlers producing the Error schema
└── api.py               # routes for the six endpoints

tests/
├── conftest.py          # fresh app + TestClient per test
├── unit/
│   ├── test_money.py
│   ├── test_splitting.py
│   ├── test_balances.py
│   └── test_settle.py   # incl. greedy counterexample + brute-force comparison
├── property/
│   └── test_invariants.py   # hypothesis: shares sum, zero-sum balances, settle-up clears & is minimal
├── api/
│   ├── test_groups.py
│   ├── test_members.py
│   ├── test_expenses.py
│   ├── test_balances_api.py
│   └── test_settle_up_api.py
└── perf/
    └── test_performance.py  # SC-005
```

**Structure Decision**: Single project with a `src/` layout. Pure domain logic (`money`,
`splitting`, `balances`, `settle`) has no web or storage dependencies so it can be unit- and
property-tested directly; `api.py` is a thin layer over the repository and domain functions.

## Complexity Tracking

No constitution violations to justify.
