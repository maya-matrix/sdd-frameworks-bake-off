# Splitit

Group expense splitting API with exact money arithmetic. TypeScript + Fastify, in-memory storage.

Design spec: `spdd/prompt/GGQPA-XXX-202610032120-[Feat]-api-splitit-group-expense-splitting.md`.

```sh
npm install
npm test          # unit, property-based and API tests
npm run dev       # http://localhost:3000 (PORT to override)
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/groups` | Create a group `{ "name" }` |
| GET | `/groups/:groupId` | Group with its members |
| POST | `/groups/:groupId/members` | Add a member `{ "name" }` (unique per group, case-insensitive) |
| GET | `/groups/:groupId/members` | Members in insertion order |
| POST | `/groups/:groupId/expenses` | Record an expense split equally |
| GET | `/groups/:groupId/expenses` | Expenses in insertion order |
| GET | `/groups/:groupId/balances` | Net balance per member (positive = is owed) |
| GET | `/groups/:groupId/settle-up` | Minimum transfers that clear all debts |

Money is always a decimal string with up to 2 decimals (`"12.34"`); JSON numbers are rejected.
When an amount does not divide evenly, the leftover cents go to the first-listed participants.

```sh
curl -X POST localhost:3000/groups -H 'content-type: application/json' -d '{"name":"Trip"}'
curl -X POST localhost:3000/groups/$G/members -H 'content-type: application/json' -d '{"name":"Alice"}'
curl -X POST localhost:3000/groups/$G/expenses -H 'content-type: application/json' \
  -d '{"payerId":"'$A'","amount":"10.00","description":"Dinner","participantIds":["'$A'","'$B'","'$C'"]}'
curl localhost:3000/groups/$G/balances
curl localhost:3000/groups/$G/settle-up
# {"transfers":[{"from":{"id":"…","name":"Bob"},"to":{"id":"…","name":"Alice"},"amount":"3.33"}, …],"optimal":true}
```

`optimal` is `true` when the transfer count is the proven minimum (up to 16 members with non-zero
balances); larger groups get a greedy plan that still clears every debt, flagged `optimal: false`.

Errors use `{ "error": { "code", "message", "details"? } }` with codes `VALIDATION_ERROR` (400),
`GROUP_NOT_FOUND` / `ROUTE_NOT_FOUND` (404), `DUPLICATE_MEMBER_NAME` (409),
`UNKNOWN_MEMBER` / `DUPLICATE_PARTICIPANT` / `INVALID_AMOUNT` (422).

No authentication — do not expose publicly without adding an auth layer.
