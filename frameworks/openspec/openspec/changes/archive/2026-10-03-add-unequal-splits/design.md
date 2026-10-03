# Design

## Context

See proposal.md for motivation and specs/ for the required behavior. Current state that shapes the approach:

- Money is `bigint` cents end to end (`src/domain/money.ts`); `parseAmount` accepts `^\d+(\.\d{1,2})?$` and `formatAmount` always prints two fraction digits.
- `MemoryStore.recordExpense` validates everything before mutating, then stores `shares` computed by `splitEqually` (`src/domain/split.ts`). Shares are stored on the expense and returned in group member order.
- `computeBalances` and `settleUp` only read `payerId`, `amount` and `shares`. As long as every expense's shares sum to its amount, balances stay exact and sum to zero, whatever produced the shares.
- Fastify's Ajv runs with `coerceTypes: false`, so a JSON number where the schema says `string` is rejected with `400`. Fastify's default `removeAdditional: true` is also in effect. It only strips properties where a schema sets `additionalProperties: false`, and no schema here does.
- `test/unit/memoryStore.test.ts` calls `store.recordExpense` with `{ payerId, amount, description, splitBetween }` directly, and those tests must keep passing unmodified.

## Goals / Non-Goals

**Goals:**
- Keep shares as the single source of truth for an expense, so balances and settle-up need no changes.
- Do all percentage arithmetic exactly in integers.
- Keep the store's `NewExpense` input and the HTTP body backward compatible.

**Non-Goals:**
- Splits by shares/weights (e.g. "2 parts vs 1 part"), itemized splits, or mixing split types within one expense.
- Editing an expense's split after recording.
- Changing the equal-split remainder rule (equal splits keep giving leftover cents in member order).

## Decisions

### 1. Percentages are stored as integer basis points (hundredths of a percent)
`"33.33"` → `3333n`, `"100"` → `10000n`. The percentage string format is the same as the money format (`\d+(\.\d{1,2})?`), so `parsePercentage` reuses `parseAmount`'s parsing and adds a `≤ 10000n` range check. `formatPercentage` is `formatAmount` under a percentage-specific name. The sum check is `Σ bp === 10000n`, which is exact.
*Alternative:* accept JSON numbers for percentages. Rejected: `33.33 + 33.33 + 33.34` in floating point is not reliably `100`, and amounts are already strings-only. Clients get one rule for every decimal value.

### 2. Largest-remainder allocation in pure `bigint`
For each participant, `product = amount × bp`, `floor = product / 10000n`, `remainder = product % 10000n`. Then `leftover = amount − Σ floor`, which is always in `[0, n−1]`. Sort participants by `remainder` descending, breaking ties by group member rank, and give `+1n` to the first `leftover` of them. Return the shares in member order, as `splitEqually` does. Because the sort key never looks at request order, the result does not depend on the order of `splits`.
*Alternative:* floor, then give leftovers in member order, mirroring the equal-split rule. The user rejected this because it can hand a cent to someone with a 0.0001-cent remainder over someone with 0.9999.
Note: with equal percentages, all remainders tie, so this reduces to the member-order rule. Equal-looking percentages such as 33.33/33.33/33.34 are not equal, though: Carol's larger percentage earns her the cent. The README will call this out.

### 3. New pure functions in `src/domain/split.ts`
- `splitExact(entries: {memberId, amount: Cents}[], memberOrder)` → `Share[]` in member order (shares equal the inputs).
- `splitByPercentage(amount, entries: {memberId, basisPoints: bigint}[], memberOrder)` → `Share[]`.

Like `splitEqually`, they throw a plain `Error` on broken preconditions (empty list, or a sum that doesn't match). These are programmer errors, because the store validates first and turns user errors into `ValidationError`. Keeping them pure makes them easy to property-test with `fast-check`.

### 4. Backward-compatible store input: a flat, optional shape that mirrors the HTTP body
```ts
type SplitType = "equal" | "exact" | "percentage";
interface SplitInput { memberId: string; amount?: Cents; basisPoints?: bigint }
interface NewExpense {
  payerId: string; amount: Cents; description: string;
  splitType?: SplitType;          // default "equal"
  splitBetween?: string[];        // equal only
  splits?: SplitInput[];          // exact (amount) / percentage (basisPoints)
}
```
`recordExpense` resolves `splitType ?? "equal"` and validates in this order. The existing checks come first and are unchanged: amount, description, payer. Then the split-type-specific rules follow:
- **equal**: `splits` absent; `splitBetween` present, non-empty, no duplicates, all members. These are the existing messages.
- **exact / percentage**: `splitBetween` absent; `splits` present and non-empty; no duplicate `memberId`; all members. Every entry carries the field for its type (`amount` or `basisPoints`) and not the other. Each `basisPoints ≤ 10000n`. Then the sum check: `Σ amount === expense.amount`, or `Σ basisPoints === 10000n`.

Existing direct callers that pass `{ splitBetween }` keep working without changes.
*Alternative:* a discriminated union (`split: { type, … }`). This is cleaner for the type checker, but it breaks every existing `recordExpense` call site and test. The flat shape keeps the "mixing splitBetween and splits" rule in one obvious place.

### 5. Stored expense and serialization
`Expense` gains `splitType: SplitType` and, for unequal types, `splits: SplitInput[]` (normalized `bigint`s, in request order). For unequal types, `splitBetween` is derived as `splits.map(s => s.memberId)`. `serializeExpense` always emits `splitType` and emits `splits` only for exact or percentage, formatting with `formatAmount` or `formatPercentage`. Equal expenses serialize exactly as before, plus `splitType: "equal"`. `cloneExpense` deep-copies `splits`.

### 6. HTTP schema
The body schema adds `splitType: { enum: ["equal","exact","percentage"] }` and `splits: array of { memberId: string, amount: string(pattern), percentage: string(pattern) }`, with `required: ["memberId"]`. `required` drops `splitBetween`, because it is now conditional. The schema stays permissive about which fields go with which type, and the store owns those rules. That gives one source of truth and testable `ValidationError` messages, and avoids `oneOf`/`if-then` Ajv error messages that are hard to read. The route maps `amount` through `parseAmount` and `percentage` through `parsePercentage`. A JSON number in either field fails the `type: "string"` check with `400`. Out-of-range percentages fail the store's range check.
No `additionalProperties: false` is added. With Fastify's `removeAdditional: true`, that setting would silently strip unknown fields instead of rejecting them, which would change today's behavior.

### 7. Balances and settle-up untouched
No code change in `src/domain/balances.ts`, `src/domain/settle.ts` or `src/http/routes/balances.ts`. New HTTP tests pin the response shape (exact key set) and the mixed-split scenario from the balance-settlement delta.

## Risks / Trade-offs

- [Percentages as strings surprise clients used to numbers] → Return the same `400 VALIDATION_ERROR` as for amounts, document it in the README with examples, and keep the rule consistent across every decimal field.
- [33.33/33.33/33.34 gives the leftover cent to Carol, while an equal split gives it to Alice] → This follows directly from the largest-remainder decision. Document it with that exact example and pin it in a spec scenario and test.
- [The permissive schema lets bad combinations reach the store] → The store validates before mutating, and every combination has an HTTP test that asserts `400` and that nothing was recorded.
- [Very large per-member exact amounts (huge digit strings)] → `bigint` has no overflow, and the sum check rejects them because the total is already capped at `1000000000.00`.

## Migration Plan

The data is in memory, so no data migration is needed. The API change is additive: deploy normally, and roll back by reverting. Any expenses recorded while the new version ran are lost on restart either way.
