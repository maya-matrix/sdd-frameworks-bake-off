# Expense Splitter API

An HTTP JSON API for splitting shared expenses within a group. Members record who paid for what, the API keeps exact per-member balances, and a settle-up endpoint suggests the fewest transfers needed to clear every debt.

Planning artifacts (proposal, specs, design, tasks) live in `openspec/changes/add-expense-splitting-api/`.

## Setup

Requires Node.js 20 or newer.

```sh
npm install
npm run build
npm start            # listens on http://127.0.0.1:3000 (override with PORT / HOST)
```

| Command             | What it does                                  |
| ------------------- | --------------------------------------------- |
| `npm run dev`       | Run from source with auto-reload (`tsx`)      |
| `npm test`          | Unit, property-based and HTTP tests (Vitest)  |
| `npm run typecheck` | Type-check sources and tests                  |
| `npm run build`     | Compile to `dist/`                            |

## Money format

- Amounts are **JSON strings** with up to two fraction digits: `"12.34"`, `"7.5"`, `"20"`. JSON numbers are rejected (`400`) so no value is ever rounded by a JSON parser.
- Responses always use exactly two fraction digits; balances may be negative: `"-0.15"`.
- Internally all arithmetic uses integer cents (`bigint`), so there are no rounding errors. Every expense's shares sum exactly to its amount, and a group's balances always sum to exactly `0.00`.
- An expense amount must be greater than `0` and at most `1000000000.00`.

### Remainder rule

An expense is split equally between the listed members. When the amount does not divide evenly, the leftover cents go one each to the participants who were **added to the group first**, regardless of the order in `splitBetween`. Example: `"10.00"` between Alice, Bob and Carol (added in that order) → `3.34`, `3.33`, `3.33`.

## Endpoints

| Method | Path                           | Description                                    |
| ------ | ------------------------------ | ---------------------------------------------- |
| POST   | `/groups`                      | Create a group, optionally with initial members |
| GET    | `/groups/{groupId}`            | Get a group and its members                    |
| POST   | `/groups/{groupId}/members`    | Add a member                                   |
| POST   | `/groups/{groupId}/expenses`   | Record an expense                              |
| GET    | `/groups/{groupId}/expenses`   | List expenses in recording order               |
| GET    | `/groups/{groupId}/balances`   | Net balance per member                         |
| GET    | `/groups/{groupId}/settle-up`  | Minimum transfers to clear all debts           |

### Create a group — `POST /groups`

```json
// request
{ "name": "Trip", "members": ["Alice", "Bob"] }
// 201 response
{ "id": "…", "name": "Trip", "members": [ { "id": "…", "name": "Alice" }, { "id": "…", "name": "Bob" } ] }
```

Member names must be non-blank and unique within the group (compared case-insensitively after trimming); a duplicate gives `409`.

### Add a member — `POST /groups/{groupId}/members`

```json
// request
{ "name": "Carol" }
// 201 response
{ "id": "…", "name": "Carol" }
```

### Record an expense — `POST /groups/{groupId}/expenses`

```json
// request
{ "payerId": "<alice>", "amount": "10.00", "description": "Taxi", "splitBetween": ["<alice>", "<bob>", "<carol>"] }
// 201 response
{
  "id": "…", "groupId": "…", "payerId": "<alice>", "amount": "10.00", "description": "Taxi",
  "splitBetween": ["<alice>", "<bob>", "<carol>"],
  "shares": [
    { "memberId": "<alice>", "share": "3.34" },
    { "memberId": "<bob>", "share": "3.33" },
    { "memberId": "<carol>", "share": "3.33" }
  ],
  "createdAt": "2026-10-03T12:00:00.000Z"
}
```

The payer does not have to be a participant. The payer and every participant must be members of the group; `splitBetween` must be non-empty with no duplicates; the description must be non-blank. Any violation gives `400` and nothing is recorded.

`GET /groups/{groupId}/expenses` returns `{ "expenses": [ … ] }` with the same shape.

### Balances — `GET /groups/{groupId}/balances`

Positive means the member is owed money, negative means they owe money.

```json
{
  "balances": [
    { "memberId": "<alice>", "name": "Alice", "balance": "6.66" },
    { "memberId": "<bob>", "name": "Bob", "balance": "-3.33" },
    { "memberId": "<carol>", "name": "Carol", "balance": "-3.33" }
  ]
}
```

### Settle up — `GET /groups/{groupId}/settle-up`

```json
{
  "transfers": [
    { "from": "<bob>", "to": "<alice>", "amount": "3.33" },
    { "from": "<carol>", "to": "<alice>", "amount": "3.33" }
  ],
  "optimal": true
}
```

Paying every listed transfer brings every balance to exactly zero. No member both sends and receives, and the output is deterministic.

**Optimality threshold:** when at most **20 members** have a non-zero balance, the plan is guaranteed to use the fewest possible transfers (`"optimal": true`), computed by finding the largest partition of balances into zero-sum groups. With more than 20, the API falls back to a greedy plan with at most *n − 1* transfers and reports `"optimal": false`.

### Errors

Every error has the shape `{ "error": { "code": "…", "message": "…" } }`:

| Status | Code               | When                                            |
| ------ | ------------------ | ----------------------------------------------- |
| 400    | `VALIDATION_ERROR` | Malformed JSON or invalid input                 |
| 404    | `NOT_FOUND`        | Unknown group or route                          |
| 409    | `CONFLICT`         | Duplicate member name                           |
| 500    | `INTERNAL`         | Unexpected error (details are not exposed)      |

## Walkthrough with curl

With the server running (`npm start`) and `jq` installed:

```sh
API=http://127.0.0.1:3000

GROUP=$(curl -s -X POST $API/groups -H 'content-type: application/json' \
  -d '{"name":"Trip","members":["Alice","Bob"]}')
GID=$(echo "$GROUP" | jq -r .id)
ALICE=$(echo "$GROUP" | jq -r '.members[0].id')
BOB=$(echo "$GROUP" | jq -r '.members[1].id')
CAROL=$(curl -s -X POST $API/groups/$GID/members -H 'content-type: application/json' \
  -d '{"name":"Carol"}' | jq -r .id)

curl -s -X POST $API/groups/$GID/expenses -H 'content-type: application/json' \
  -d "{\"payerId\":\"$ALICE\",\"amount\":\"10.00\",\"description\":\"Taxi\",\"splitBetween\":[\"$ALICE\",\"$BOB\",\"$CAROL\"]}" | jq .shares

curl -s $API/groups/$GID/balances | jq .
curl -s $API/groups/$GID/settle-up | jq .
```

## Assumptions and limitations

- **In-memory storage:** all data is lost when the process stops. Storage sits behind a `Repository` interface (`src/store/memoryStore.ts`) so it can be swapped for a database.
- **No authentication:** "any member can record an expense" is enforced as "the payer and all participants must be members of the group". There is no notion of who is calling the API.
- **Single currency** with two minor-unit digits.
- Not supported: editing or deleting expenses, removing members, unequal or percentage splits, recording settlement payments.
