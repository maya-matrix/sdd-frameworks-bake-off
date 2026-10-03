# Tasks

## 1. Exact percentage and split arithmetic (domain)

- [x] 1.1 Add `parsePercentage` (reuses `parseAmount` parsing, returns basis points, rejects values above `10000n`) and `formatPercentage` to `src/domain/money.ts` (design D1); verify unit tests in `test/unit/money.test.ts`: `"33.33"`→`3333n`, `"100"`→`10000n`, `"0"`→`0n`, rejections of `"100.01"`, `"-5"`, `"33.333"`, `"1e2"`, and `formatPercentage(6000n)` → `"60.00"`
- [x] 1.2 Add `splitExact(entries, memberOrder)` to `src/domain/split.ts`, returning shares in member order and throwing `Error` on an empty list (design D3); verify unit tests in `test/unit/split.test.ts`: `6.00/2.50/1.50` shares match their inputs, member-order output independent of entry order, zero share kept as `0n`
- [x] 1.3 Add `splitByPercentage(amount, entries, memberOrder)` using bigint largest-remainder allocation with member-order tie-break (design D2); verify unit tests for the spec scenarios: `10.00` at `33.33/33.33/33.34` → `333n/333n/334n`; `0.01` at `50/50` → `1n/0n`, also with entries reversed; `0.02` at `25/25/50` → `1n/0n/1n`; `200.00` at `50/30/20` → `10000n/6000n/4000n`
- [x] 1.4 Add fast-check properties for `splitByPercentage`: for random amounts (1 to `100_000_000_000n`) and random basis-point vectors summing to `10000n`, shares sum exactly to the amount, each share is `floor` or `floor + 1` of `amount × bp / 10000`, and the result is invariant under shuffling the entries; verify `npm test` passes

## 2. Store: split types and validation

- [x] 2.1 Extend `src/store/memoryStore.ts` types per design D4/D5: `SplitType`, `SplitInput`, optional `splitType`/`splitBetween`/`splits` on `NewExpense`; `splitType` and optional `splits` on `Expense`; `cloneExpense` deep-copies `splits`; verify `npm run typecheck` passes and existing `test/unit/memoryStore.test.ts` passes unmodified
- [x] 2.2 Implement split-type-aware validation in `recordExpense`, run before any mutation (design D4): equal keeps the existing rules and rejects `splits`; exact and percentage require non-empty, duplicate-free, all-member `splits`, reject `splitBetween`, require the matching per-entry field (and not the other), check percentage range, and check the sum (amounts = total, basis points = `10000n`), all as `ValidationError`; verify new unit tests in `test/unit/memoryStore.test.ts` throw `ValidationError` for each case and leave `listExpenses` unchanged
- [x] 2.3 Compute and store shares with `splitExact` / `splitByPercentage`, store normalized `splits` in request order, and derive `splitBetween` from them; verify unit tests that a recorded exact and a recorded percentage expense have the expected `splitType`, `splits`, `splitBetween` and shares, and that an expense with no `splitType` gets `"equal"` with shares identical to before

## 3. HTTP: request schema and responses

- [x] 3.1 Update the body schema in `src/http/routes/expenses.ts` (design D6): optional `splitType` enum, optional `splits` array of `{ memberId, amount?, percentage? }` with string+pattern fields, and `splitBetween` no longer required. Map `amount` and `percentage` with `parseAmount` and `parsePercentage`, and pass the result to the store. Verify `npm run typecheck` passes and all existing `test/http/*.test.ts` pass unmodified
- [x] 3.2 Update `serializeExpense` to always emit `splitType` and, for exact and percentage only, `splits` with two-decimal values (design D5); verify an HTTP test that an equal expense response has exactly the previous keys plus `splitType: "equal"` and no `splits` key
- [x] 3.3 Add HTTP tests in `test/http/expenses.test.ts` for every new `expense-recording` scenario. Cover the explicit `"equal"` type, unknown `splitType` → 400, exact `6.00/2.50/1.50` → 201, exact sums of `9.99` and `10.01` → 400, exact JSON number and `"5.005"` → 400, and a zero exact share → `"0.00"`. Cover percentages `50/30/20` of `200.00`, `33.33/33.33/33.34` of `10.00` → `3.33/3.33/3.34`, sums of `99.99` and `100.01` → 400, `"100.01"`, `"-5"`, `50` (number) and `"33.333"` → 400, and the `0.01` tie in both request orders. Also cover missing or empty `splits`, both `splitBetween` and `splits` present, a duplicate `memberId`, a non-member in `splits`, the percentage response echo (`"60.00"`/`"40.00"` and derived `splitBetween`), and mixed split types in `GET …/expenses`. Each 400 case must also assert that the expense list is unchanged. Verify `npm test` passes
- [x] 3.4 Add HTTP tests in `test/http/balances.test.ts` for the `balance-settlement` delta. An exact `6.00/2.50/1.50` expense paid by Alice plus a percentage `33.33/33.33/33.34` expense paid by Bob must give balances `0.67/4.17/-4.84`, summing to `0.00`. Each balance entry must have exactly the keys `memberId`, `name` and `balance`, in member order. `settle-up` must zero these balances. Verify `npm test` passes

## 4. Documentation

- [x] 4.1 Update `README.md`: document `splitType` and `splits` with exact and percentage request and response examples, string-only percentages with up to two decimals that sum to exactly `100`, the largest-remainder rule with the `33.33/33.33/33.34` → `3.33/3.33/3.34` example (and how it differs from the equal-split rule), the new validation errors, and remove "unequal or percentage splits" from "Not supported". Verify a curl walkthrough of one exact and one percentage expense against `npm start` returns the documented shares

## 5. Integration check

- [x] 5.1 Run `npm run typecheck`, `npm test` and `npm run build`, and confirm the pre-existing tests passed without modification (`git diff --stat test/` shows only additions); verify all three commands exit 0
- [x] 5.2 Run `openspec validate add-unequal-splits --strict` and confirm every spec scenario in the change maps to at least one test; verify the validation passes
