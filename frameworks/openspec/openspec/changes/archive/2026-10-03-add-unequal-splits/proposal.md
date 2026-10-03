# Proposal

## Why

Today every expense is split equally between its participants, but real shared costs rarely are: one person orders the expensive dish, or a rent split follows room sizes. Users need to record those expenses as they actually happened — by exact amounts or by percentages — without breaking any client that already records equal splits or reads balances.

## What Changes

- `POST /groups/{groupId}/expenses` accepts an optional `splitType`: `"equal"` (default), `"exact"`, or `"percentage"`.
  - `equal`: unchanged — uses `splitBetween`, same remainder rule. Requests without `splitType` behave exactly as before.
  - `exact`: a `splits` list of `{ memberId, amount }`; the amounts (exact decimal strings) must sum exactly to the expense `amount`.
  - `percentage`: a `splits` list of `{ memberId, percentage }`; percentages are decimal strings with up to two fraction digits and must sum exactly to `100`. Shares are computed in whole cents with the **largest-remainder** method (ties go to the earlier member in group order), so shares always sum exactly to the amount.
- New validation errors (`400`, nothing recorded): mismatched sums, missing/extra fields for the chosen split type, duplicate or non-member participants in `splits`, malformed or out-of-range per-member values.
- Expense responses (create and list) gain a `splitType` field; unequal expenses also echo their normalized `splits`. `splitBetween` is still returned for every expense (the participant ids), so existing readers keep working. This is additive — no existing field changes.
- `GET /groups/{groupId}/balances` and `GET /groups/{groupId}/settle-up`: response formats unchanged; they simply reflect the unequal shares.

## Capabilities

### New Capabilities

_None._ Unequal splits are part of how an expense is recorded, so they belong to the existing `expense-recording` capability.

### Modified Capabilities

- `expense-recording`: recording an expense gains a split type; validation rules depend on the split type; new requirements for exact-amount and percentage splits (including percentage remainder allocation); listed/returned expenses include `splitType` and `splits`.
- `balance-settlement`: "Net balances per member" makes explicit that balances reflect any split type and that the response shape stays exactly as today.

## Impact

- **Code**: `src/domain/split.ts` (new exact and percentage split functions), `src/domain/money.ts` (percentage parsing to basis points), `src/store/memoryStore.ts` (`NewExpense`/`Expense` carry split type and per-member inputs; validation), `src/http/routes/expenses.ts` (request schema and serialization). Balance and settle-up code is untouched.
- **API**: backward compatible. Old requests and response fields are unchanged; new optional request fields and new response fields are added.
- **Tests**: new unit tests (including property-based) for the split functions and HTTP tests for the new modes and validation; all existing tests must pass unmodified.
- **Docs**: README request/response examples and the "Not supported" list.
- **Dependencies**: none.
