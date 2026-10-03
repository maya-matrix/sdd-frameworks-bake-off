# Expense Splitter API — Design

Date: 2026-10-03
Status: Approved in conversation; pending written-spec review

## Goal

A web API for splitting expenses within groups. Users create groups and add
members. Any member can record an expense with a payer, amount, description,
and the members it is split equally between. The API reports each member's
net balance and suggests the minimum set of transfers that clears all debts.
Money calculations are exact — no floating point anywhere.

## Decisions

| Topic | Decision |
|---|---|
| Stack | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.0, SQLite, pytest; managed with `uv` |
| Money on the wire | Decimal **strings** (`"12.34"`). JSON numbers are rejected. |
| Money internally | Integer minor units (cents) everywhere; `Integer` DB columns |
| Currency | One per group, 3 uppercase letters, default `"EUR"`, no conversion. Assumed to have 2 decimal places. |
| Auth | None. A "user" is a member record within a group. "Any member can record" = payer and split participants must belong to the group. |
| Persistence | SQLAlchemy + SQLite file; tests use a fresh database per test |
| Scope | Create group, add/list members, record/list expenses, balances, settle-up. **No** edit/delete, settlements recording, or member removal. |
| Settle-up | Exact minimum via subset DP; greedy fallback above 20 non-zero balances, flagged `optimal: false` |

Known future change (not built now): unequal splits by exact amounts or
percentages. The design isolates share computation so this slots in.

## Architecture

```
app/
  money.py        parse_amount(str) -> int cents; format_cents(int) -> str
  splitting.py    split_equally(total_cents, member_ids) -> dict[id, cents]
  settlement.py   minimize_transfers(balances: dict[id, cents]) -> (transfers, optimal)
  models.py       SQLAlchemy ORM: Group, Member, Expense, ExpenseShare
  repository.py   DB access functions (session-scoped)
  schemas.py      Pydantic request/response models
  api.py          FastAPI router; domain errors -> HTTP errors
  main.py         create_app(database_url) app factory; module-level `app`
tests/
  test_money.py, test_splitting.py, test_settlement.py, test_api_*.py
```

`money`, `splitting`, and `settlement` are pure functions with no I/O and no
dependency on FastAPI or SQLAlchemy.

### Data model

- `Group(id, name, currency)`
- `Member(id, group_id → Group, name)`; unique `(group_id, name)`
- `Expense(id, group_id → Group, payer_id → Member, amount_cents, description, created_at)`
- `ExpenseShare(expense_id → Expense, member_id → Member, share_cents)`; PK `(expense_id, member_id)`

Shares are computed once when the expense is recorded and persisted.
Invariant: for every expense, `sum(share_cents) == amount_cents`.

Balance of a member = `sum(amount_cents of expenses they paid) − sum(share_cents owed)`.
Balances are always derived, never stored. Invariant: the sum of all balances in a group is 0.

## Core algorithms

### Money parsing / formatting

- `parse_amount(s: str) -> int`: input must be a `str` matching
  `^\d+(\.\d{1,2})?$`; converts via integer arithmetic (split on `.`, right-pad
  fraction to 2 digits). Must be > 0 and ≤ 100_000_000_000 cents
  (1,000,000,000.00). Raises `ValueError` otherwise.
- `format_cents(c: int) -> str`: `-333 → "-3.33"`, `5 → "0.05"`, `0 → "0.00"`.

### Equal split

`split_equally(total, member_ids)`: sort member ids ascending;
`base, rem = divmod(total, n)`; the first `rem` members (by ascending id) get
`base + 1`, the rest `base`. Example: 1000 over [1,2,3] → {1: 334, 2: 333, 3: 333}.
1 over 3 members → {1: 1, 2: 0, 3: 0}.

### Minimum transfers

Input: `{member_id: balance_cents}` summing to 0.

1. Drop zero balances. Let `k` = number remaining.
2. If `k ≤ 20`: exact. A set of balances summing to zero can be settled with
   `|set| − 1` transfers, so minimum transfers = `k − (max number of disjoint
   zero-sum subsets partitioning the set)`. Compute via DP over bitmasks:
   `dp[mask]` = max zero-sum groups formed within `mask`, using
   `dp[mask] = max(dp[mask without bit i]) + (1 if sum(mask) == 0 else 0)`.
   Reconstruct the partition, then settle each zero-sum group greedily
   (largest creditor ↔ largest debtor), which uses exactly `|group| − 1`
   transfers. Return `optimal: true`.
3. If `k > 20`: greedy over all balances (largest debtor pays largest
   creditor, repeat). Return `optimal: false`.

Determinism: ties broken by member id; output transfers sorted by
`(from_member_id, to_member_id)`.

Every transfer amount is a positive integer number of cents; applying all
transfers zeroes every balance exactly.

## HTTP API

| Method | Path | Request | Success |
|---|---|---|---|
| POST | `/groups` | `{"name", "currency"?}` | 201 group |
| GET | `/groups/{gid}` | — | 200 group with `members` |
| POST | `/groups/{gid}/members` | `{"name"}` | 201 member |
| GET | `/groups/{gid}/members` | — | 200 list of members |
| POST | `/groups/{gid}/expenses` | `{"payer_id", "amount", "description", "split_between": [ids]}` | 201 expense |
| GET | `/groups/{gid}/expenses` | — | 200 list of expenses |
| GET | `/groups/{gid}/balances` | — | 200 balances |
| GET | `/groups/{gid}/settle-up` | — | 200 transfers |

Response shapes:

```json
// group
{"id": 1, "name": "Trip", "currency": "EUR", "members": [{"id": 1, "name": "Alice"}]}

// member
{"id": 1, "name": "Alice"}

// expense
{"id": 1, "payer_id": 1, "amount": "10.00", "description": "Taxi",
 "created_at": "2026-10-03T12:00:00Z",
 "shares": [{"member_id": 1, "amount": "3.34"}, {"member_id": 2, "amount": "3.33"}, {"member_id": 3, "amount": "3.33"}]}

// balances — every member listed, ordered by member id; positive = is owed
{"currency": "EUR", "balances": [{"member_id": 1, "name": "Alice", "balance": "6.66"}, ...]}

// settle-up
{"currency": "EUR", "optimal": true,
 "transfers": [{"from_member_id": 2, "to_member_id": 1, "amount": "3.33"}]}
```

Lists (members, expenses, shares) are ordered by id ascending.

## Validation and errors

All validation failures return **422** in FastAPI's `{"detail": ...}` shape.

- `amount`: JSON string, matches the money regex, > 0, ≤ 1,000,000,000.00.
  Rejected examples: `12.34` (number), `"-1"`, `"0"`, `"1.234"`, `"1e3"`, `""`, `" 1"`.
- `split_between`: non-empty, no duplicates, every id a member of this group.
- `payer_id`: a member of this group (need not be in `split_between`).
- `name` (group, member): trimmed, 1–100 chars. `description`: trimmed, 1–200 chars.
- `currency`: `^[A-Z]{3}$`, default `"EUR"`.

Other errors:

- Unknown group id → **404**.
- Duplicate member name within a group → **409**.

Member IDs from another group are treated as "not a member of this group" → 422.

## Testing

TDD with pytest.

- **money**: round-trips; formatting of negatives, sub-unit and zero; each
  rejection case; static check that `float` is not used in `app/` money paths.
- **splitting**: 1000/3 → [334, 333, 333]; 1/3 → [1, 0, 0]; sum invariant
  (property-style loop over many totals and sizes); order independence of input ids.
- **settlement**: empty / all-zero; simple pair; `+4,+3,−3,−2,−2` → 3 transfers
  (greedy would need 4); transfers always zero all balances; random small cases
  match a brute-force minimum; >20 non-zero balances → `optimal: false` and still zeroes.
- **API** (`TestClient`, fresh SQLite per test): full flow; €10.00 three ways
  yields balances summing to exactly `"0.00"`; many random uneven expenses keep
  balance sum at zero and settle-up transfers clear them; every 404/409/422 case.

## Out of scope

Authentication, editing/deleting expenses or members, recording settlements,
multi-currency, unequal splits (next round), pagination.
