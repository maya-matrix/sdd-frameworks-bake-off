# Implementation Plan: Expense Splitter API

Source of truth: [`../SPEC.md`](../SPEC.md) (approved 2026-10-03). Task details live in [`todo.md`](todo.md).

## Overview

A FastAPI + SQLite JSON API for shared group expenses: groups, members, equal-split expenses, net balances and minimum-transfer settle-up. All money is integer cents internally and decimal strings in camelCase JSON. We build the pure domain core first, starting with the riskiest part (exact minimum settle-up), and then add the HTTP/SQLite layer one endpoint at a time.

## Architecture Decisions

- **Pure domain core, thin I/O shell.** `money`, `split`, `balances` and `settle` are pure functions over `int` cents with no FastAPI/Pydantic/sqlite imports. They are unit- and property-tested on their own, and the API layer only translates.
- **Money parsing by string handling, not `float`.** `parse_amount("10.5") → 1050` validates the string with a regex and builds the integer from its digits. `format_cents(-333) → "-3.33"` uses `divmod`, never division.
- **Persist the computed shares.** `expense_shares` stores the exact cent allocation per member. Balances are computed from the stored shares, never re-split at read time. This lets the later exact/percentage splits (PROMPTS.md round 2) plug in without touching balances.
- **Settle-up = subset DP + greedy within subsets.** A bitmask DP over the `k ≤ 20` non-zero balances finds the maximum number of disjoint zero-sum subsets. Each subset is then cleared with `|subset| − 1` greedy transfers. Above 20 non-zero balances it falls back to plain greedy. Ties break by member join order, so output is deterministic.
- **App factory with an injected DB path.** `create_app(db_path)` lets each test use its own temp DB, and lets the restart test reopen the same file. `main.app` reads `EXPENSES_DB_PATH`.
- **One connection per request** (`sqlite3.connect`, `PRAGMA foreign_keys=ON`, `row_factory=Row`), provided through a FastAPI dependency. Inserting an expense and its shares runs in a single `with conn:` transaction.
- **camelCase at the boundary.** A base Pydantic model with `alias_generator=to_camel` and `populate_by_name=True`; responses use `response_model_by_alias` (the FastAPI default).
- **Uniform errors.** `ApiError(status, code, message)` plus handlers that convert `RequestValidationError` (422 → 400 `VALIDATION_ERROR`) and malformed JSON into `{"error": {"code", "message"}}`.
- **Strict amount type.** `amount` is declared as a `StrictStr`, so a JSON number is rejected rather than coerced.

## Dependency Graph

```
money ──► split ──► balances ──► settle            (pure core)
  │                                │
  └──► db/repository ──► API: groups ──► members ──► expenses ──► balances endpoint ──► settle-up endpoint
                                                                            │
                                                     restart persistence + quality gates (final)
```

## Task List

### Phase 1: Domain core (pure, no I/O)
- [x] Task 1: Project scaffold + `money` module
- [x] Task 2: Equal split + balances
- [x] Task 3: Exact minimum settle-up

### Checkpoint A: Domain core
- [ ] `uv run pytest` green, `uv run mypy src` and `uv run ruff check .` clean
- [ ] 100% coverage on `money.py`, `split.py`, `settle.py`
- [ ] Human review of the settle-up algorithm before building the API

### Phase 2: Persistence + API slices
- [x] Task 4: SQLite schema + repository
- [x] Task 5: App factory, error handling, groups endpoints
- [x] Task 6: Add-member endpoint
- [x] Task 7: Expense endpoints (record + list)

### Checkpoint B: Data entry flow
- [ ] Create group → add members → record expenses → list them, via `TestClient` and manually via uvicorn + curl
- [ ] All validation error codes covered

### Phase 3: Read-side endpoints + finish
- [x] Task 8: Balances endpoint
- [ ] Task 9: Settle-up endpoint
- [ ] Task 10: Restart persistence, README, final quality gates

### Checkpoint C: Complete
- [ ] All 8 spec Success Criteria verified
- [ ] Coverage ≥ 90% overall; 100% on money/split/settle
- [ ] Ready for review

## Parallelization

Tasks 2 and 3 depend only on Task 1's `money` types, and Task 4 depends only on Task 1. They could run in parallel, but this plan runs sequentially in one session; parallelism isn't worth the coordination cost at this size.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Settle-up DP is wrong or not truly minimal | High | Built first (Task 3). A hypothesis test compares it with a brute-force minimum on ≤ 8 balances, plus hand cases where greedy is suboptimal (e.g. `[+5,+5,−5,−5,+3,−3]`-style mixes) |
| Float slipping into money paths (e.g. Pydantic coercing `10.5`) | High | `StrictStr` amount, a test that numeric amounts get 400, and the "no float" rule in code review |
| FastAPI 422/default error shapes leaking | Medium | Global handlers tested for malformed JSON, missing fields and wrong types |
| camelCase aliasing inconsistent (some snake_case keys leak) | Medium | Shared base model; integration tests assert exact key sets |
| SQLite FK not enforced (off by default) | Medium | PRAGMA on every connection, plus a repository test that a bad FK raises |
| 2^20 DP too slow at the limit | Low | Benchmark-style test: 20 non-zero balances finish in < 2s; greedy fallback above 20 |

## Open Questions

None. All spec questions were resolved.
