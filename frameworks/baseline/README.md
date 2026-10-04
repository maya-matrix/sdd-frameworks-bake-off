# Expense Splitter API

A small HTTP API for splitting shared expenses within groups. It has no runtime
dependencies and needs only Node.js 20+.

```sh
npm start        # listens on PORT (default 3000)
npm test         # runs the test suite with node:test
```

## Money handling

- Amounts are sent and returned as **decimal strings** with up to 2 decimal
  places (`"12.50"`). JSON numbers are rejected, so a float never reaches the
  money logic.
- Internally, every amount is an integer number of cents (`BigInt`), so all
  arithmetic is exact.
- Equal splits never lose or create a cent. `10.00` split three ways becomes
  `3.34 / 3.33 / 3.33`. Leftover cents go to the members listed first in
  `splitBetween`.
- In every group, the balances always add up to exactly `0.00`.

## Identity

Authentication is out of scope. The caller is identified by an `X-User-Id`
header containing an id returned by `POST /users`. In production, this would
be replaced by real authentication. Every group endpoint requires the caller to
be a member of that group.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/users` | Create a user: `{ "name": "Alice" }` |
| `GET` | `/users/:id` | Get a user |
| `POST` | `/groups` | Create a group: `{ "name": "Trip" }`. The caller becomes the first member. |
| `GET` | `/groups/:id` | Get a group and its members |
| `POST` | `/groups/:id/members` | Add a member: `{ "userId": "..." }`. Any member can add members. |
| `POST` | `/groups/:id/expenses` | Record an expense (see below). Any member can record one. |
| `GET` | `/groups/:id/expenses` | List expenses |
| `GET` | `/groups/:id/balances` | Each member's net balance |
| `GET` | `/groups/:id/settle-up` | Suggested minimum set of transfers |

### Record an expense

```json
POST /groups/:id/expenses
X-User-Id: <member id>

{
  "paidBy": "<member id>",
  "amount": "10.00",
  "description": "Pizza",
  "splitBetween": ["<member id>", "<member id>", "<member id>"]
}
```

`paidBy` and every id in `splitBetween` must be group members. `splitBetween`
must not contain duplicates. The payer does not have to be in `splitBetween`.

### Balances

A positive balance means the group owes that member money. A negative balance
means the member owes money.

```json
{ "groupId": "...", "balances": [ { "userId": "...", "name": "A", "balance": "6.67" }, ... ] }
```

### Settle up

```json
{
  "groupId": "...",
  "optimal": true,
  "transfers": [ { "from": "...", "fromName": "B", "to": "...", "toName": "A", "amount": "3.33" } ]
}
```

The suggested transfers clear every balance exactly. Finding the minimum number
of transfers is NP-hard in general (it reduces to partitioning the balances into
as many zero-sum subgroups as possible). The service solves it **exactly** with
a dynamic program over subsets when at most 20 members have a non-zero balance.
Above that, it uses a greedy heuristic that still settles everything in at most
*n − 1* transfers, and returns `"optimal": false`.

## Errors

Errors use the shape `{ "error": { "code": "...", "message": "..." } }`:

- `400 validation_error` or `invalid_json`
- `401 unauthenticated`: the `X-User-Id` header is missing or unknown
- `403 forbidden`: the caller is not a group member
- `404 not_found`
- `405 method_not_allowed`
- `409 conflict`: the user is already a member
- `413 payload_too_large`

## Layout

- `src/money.js`: parsing, formatting and equal splitting of cents
- `src/settle.js`: minimum-transfer settlement
- `src/service.js`: domain logic and in-memory storage
- `src/app.js`: HTTP routing and error mapping
- `test/`: unit tests, plus HTTP tests that run against a live server

Data is kept in memory and is lost when the process restarts.
