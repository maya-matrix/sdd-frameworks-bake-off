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
