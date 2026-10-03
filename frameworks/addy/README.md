# Expense Splitter API

HTTP JSON API for splitting group expenses exactly. Groups have members; any member can record an expense split equally between some members; the API reports each member's net balance and the minimum set of transfers that settles everyone up.

Spec: [`SPEC.md`](SPEC.md) · Plan: [`tasks/plan.md`](tasks/plan.md)

## Setup

Requires [uv](https://docs.astral.sh/uv/) (Python 3.13 is selected via `.python-version`).

```sh
uv sync
uv run uvicorn expense_splitter.main:app --reload --port 8000
```

Data is stored in SQLite at `EXPENSES_DB_PATH` (default `./expenses.db`). Interactive docs: http://localhost:8000/docs

## Commands

```sh
uv run pytest                                                   # tests
uv run pytest --cov=expense_splitter --cov-report=term-missing   # coverage
uv run mypy src tests                                           # strict type check
uv run ruff check . && uv run ruff format --check .             # lint + format
```

## Money

- Amounts are **JSON strings** with up to two decimals (`"10.5"`, `"10.50"`); JSON numbers are rejected. Responses always use two decimals (`"-3.33"`).
- Internally every amount is integer cents, so there is no rounding error anywhere.
- Equal splits give leftover cents to the first members listed in `splitBetween`: €10.00 split between `[a, b, c]` is 3.34 / 3.33 / 3.33.
- Balances: positive = is owed money, negative = owes money. They always sum to exactly 0.00.

## Endpoints

| Method | Path | Success |
|---|---|---|
| POST | `/groups` `{name, currency?}` | 201 group (currency defaults to `EUR`) |
| GET | `/groups/{groupId}` | 200 group with members in join order |
| POST | `/groups/{groupId}/members` `{name}` | 201 member |
| POST | `/groups/{groupId}/expenses` `{payerId, amount, description, splitBetween}` | 201 expense with per-member `shares` |
| GET | `/groups/{groupId}/expenses` | 200 `{expenses}` oldest first |
| GET | `/groups/{groupId}/balances` | 200 `{currency, balances: [{memberId, name, balance}]}` |
| GET | `/groups/{groupId}/settle-up` | 200 `{currency, transfers: [{fromMemberId, toMemberId, amount}]}` |

Errors always look like `{"error": {"code": "...", "message": "..."}}`:
`400 VALIDATION_ERROR`, `400 UNKNOWN_MEMBER`, `404 GROUP_NOT_FOUND`, `409 DUPLICATE_MEMBER`, `409 GROUP_FULL`.

## Example

```sh
J='content-type: application/json'
G=$(curl -s -XPOST localhost:8000/groups -H "$J" -d '{"name":"Trip"}' | jq -r .id)
A=$(curl -s -XPOST localhost:8000/groups/$G/members -H "$J" -d '{"name":"Ana"}' | jq -r .id)
B=$(curl -s -XPOST localhost:8000/groups/$G/members -H "$J" -d '{"name":"Bo"}' | jq -r .id)
C=$(curl -s -XPOST localhost:8000/groups/$G/members -H "$J" -d '{"name":"Cy"}' | jq -r .id)

curl -s -XPOST localhost:8000/groups/$G/expenses -H "$J" \
  -d "{\"payerId\":\"$A\",\"amount\":\"10.00\",\"description\":\"Taxi\",\"splitBetween\":[\"$A\",\"$B\",\"$C\"]}"

curl -s localhost:8000/groups/$G/balances    # Ana 6.66, Bo -3.33, Cy -3.33
curl -s localhost:8000/groups/$G/settle-up   # Bo -> Ana 3.33, Cy -> Ana 3.33
```

## Settle-up

The minimum number of transfers is `k − g`, where `k` is the number of members with a non-zero balance and `g` is the largest number of disjoint groups whose balances each sum to zero (each such group settles internally in `size − 1` transfers). This is computed exactly over all subsets when `k ≤ 20`; above that it falls back to in-order debtor/creditor matching, which still clears every debt exactly but may use more than the minimum (at most `k − 1` transfers).

Cost at the exact limit (20 non-zero balances) is roughly 0.15 s CPU and 20 MB peak memory per call; groups are capped at 50 members (`409 GROUP_FULL`).
