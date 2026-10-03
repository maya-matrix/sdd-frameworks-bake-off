# SplitIt

A web API for splitting expenses in a group: create groups, add members, record expenses
split equally, see each member's net balance, and get the fewest transfers that settle all
debts. Money is exact — there are no rounding errors.

Specification and design: [specs/001-expense-splitting-api/](specs/001-expense-splitting-api/).

## Setup

Requires [`uv`](https://docs.astral.sh/uv/) (it fetches Python 3.12 if needed).

```bash
uv sync
```

## Test

```bash
uv run pytest
```

The suite covers unit, property-based (hypothesis), API, contract and performance tests.

## Run

```bash
uv run uvicorn splitit.main:app --reload
```

Interactive docs: http://127.0.0.1:8000/docs

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/groups` | Create a group, optionally with initial `members` (list of names) |
| GET | `/groups/{group_id}` | Get a group and its members |
| POST | `/groups/{group_id}/members` | Add a member |
| POST | `/groups/{group_id}/expenses` | Record an expense split equally |
| GET | `/groups/{group_id}/expenses` | List expenses |
| GET | `/groups/{group_id}/balances` | Net balance per member |
| GET | `/groups/{group_id}/settle-up` | Fewest transfers to clear all balances |

## Money rules

- Amounts are JSON **strings** with exactly two decimals, e.g. `"10.00"`; balances may be
  negative, e.g. `"-3.33"`. JSON numbers and amounts with more than two decimals are rejected
  (422), never rounded.
- Internally every amount is an integer number of cents.
- **Leftover cents**: an expense is split by giving each participant the amount divided by
  the number of participants, rounded down to the cent; the leftover cents go one each to the
  participants listed first. €10.00 split between Ana, Ben and Cleo is 3.34 + 3.33 + 3.33.
- A group's balances always sum to exactly zero, and the settle-up transfers clear them
  exactly using the minimum possible number of transfers.

## Limits

- At most 20 members per group; names 1–100 characters, unique per group (case-insensitive).
- Expense amount from `"0.01"` to `"1000000000.00"`; description 1–200 characters.
- Data is kept in memory and is lost when the server stops.
