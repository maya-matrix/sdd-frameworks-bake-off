# Design

## Context

The repository is greenfield: it contains only OpenSpec scaffolding, no application code, no package manifest and no tests. No language, framework or storage was specified, so this design picks them (see Decisions). Motivation and scope: see proposal.md. Behavioral contract: see `specs/group-management`, `specs/expense-recording`, `specs/balance-settlement`.

## Goals / Non-Goals

**Goals:**
- Money is never represented as a floating-point number anywhere in the domain or on the wire.
- Domain logic (money parsing/formatting, splitting, balances, settle-up) is pure and framework-free, so it can be unit-tested exhaustively, separately from HTTP.
- Settle-up is provably minimal for realistic group sizes and deterministic.

**Non-Goals:**
- Durable storage, authentication, concurrency control across multiple processes.
- Multi-currency or currencies with other than two minor-unit digits.
- Pagination of expense lists.

## Decisions

### D1. Stack: TypeScript on Node.js 20+, Fastify, Vitest
- **Fastify** gives built-in JSON-schema request validation, a clean error-handler hook for the uniform `{"error": {...}}` shape, and `app.inject()` for HTTP tests without opening a port.
- **Vitest** for unit and HTTP tests; `fast-check` for property-based tests on money/split/settle-up invariants.
- Alternatives: Express (no built-in validation, needs supertest), Python/FastAPI (equally viable; TS chosen for a single-language, type-checked JSON API). Strict `tsconfig` (`strict: true`).

### D2. Money as integer minor units (`bigint`)
- Internally every amount is a `bigint` count of cents. Parsing accepts only strings matching `^\d+(\.\d{1,2})?$` and converts by string manipulation (`"7.5"` → `750n`), never via `Number`/`parseFloat`. Formatting renders `bigint` → `"-0.15"` with exactly two fraction digits.
- `bigint` rather than `number`: rules out silent precision loss even as balances accumulate; the cap of `1000000000.00` per expense keeps inputs sane but `bigint` means sums can never overflow.
- Alternatives: decimal library (`decimal.js`) — exact enough but adds a dependency and invites accidental non-integer division; `number` cents — safe up to 2^53 but relies on discipline. Rejected.
- Amount fields in Fastify schemas are typed `string` with a `pattern`, so a JSON number is rejected with `400` before reaching the domain.

### D3. Equal split algorithm
- `base = amount / n`, `remainder = amount % n` (bigint division). Participants are sorted by the member's position in the group (insertion index); the first `remainder` participants get `base + 1`, the rest `base`. This makes shares sum exactly to `amount`, differ by ≤ 1 cent, and be independent of request ordering.
- Shares are computed once at record time and stored on the expense, so balances are a plain sum and later member additions cannot change past shares.
- Alternative: give remainder to the payer — simpler to explain but biased when the payer isn't a participant; rejected.

### D4. Balances
- `balance(m) = Σ amount where payer = m − Σ share(m)` over all expenses, computed on demand from stored expenses (O(expenses × participants)); fine for in-memory scale. Invariant `Σ balances = 0` holds by construction because each expense contributes `+amount` and `−Σshares = −amount`.
- Output ordered by member insertion order.

### D5. Minimum-transfer settle-up
- Finding the minimum number of transfers is equivalent to partitioning the non-zero balances into the **maximum number of disjoint zero-sum subsets** `k`; the minimum is `n − k` (each zero-sum subset of size s settles in s − 1 transfers, and no fewer is possible).
- Exact algorithm (n ≤ 20 non-zero members): bitmask DP. Precompute `sum[mask]`; `dp[mask]` = max number of zero-sum groups that `mask` can be completely split into, computed by the standard recurrence `dp[mask] = max over i in mask of dp[mask without i]`, plus 1 if `sum[mask] == 0`. Reconstruct the partition by walking back from the full mask. Cost O(2^n · n) time, O(2^n) memory → ~20M ops at n = 20, well under 1 s. Sums use `bigint`; for speed the DP may store cents as `number` since they are bounded by the per-expense cap × expense count — but implementation MUST verify each cent value is a safe integer and otherwise fall back to `bigint`.
- Within each zero-sum subset, settle greedily: repeatedly match the largest debtor with the largest creditor, transferring `min(|debt|, credit)`. This yields exactly s − 1 transfers per subset, and debtors only send / creditors only receive.
- Fallback (n > 20): the same greedy over the whole set, giving ≤ n − 1 transfers; response sets `optimal: false`.
- Determinism: members are indexed by insertion order before DP; ties in greedy are broken by insertion order; DP reconstruction picks the lowest-index choice. Transfers are output sorted by (`from` order, `to` order).
- Alternatives: greedy only (simple, but not minimal — fails the `+5,+7,−5,−7` scenario with 3 transfers); exhaustive search with pruning (harder to bound). Rejected.

### D6. Layering and module layout
```
src/
  domain/money.ts        parse/format, bigint cents
  domain/split.ts        equal split (D3)
  domain/balances.ts     balance computation (D4)
  domain/settle.ts       min-transfer settle-up (D5)
  store/memoryStore.ts   groups, members, expenses in Maps; Repository interface
  http/app.ts            buildApp(store) → Fastify instance; error handler
  http/routes/*.ts       groups, members, expenses, balances, settle-up
  server.ts              listen on PORT (default 3000)
test/
  unit/*.test.ts         domain tests incl. property-based
  http/*.test.ts         app.inject() end-to-end tests per spec scenario
```
- `buildApp` takes the store as a parameter so each test gets a fresh, isolated in-memory store.
- IDs are `crypto.randomUUID()`.

### D7. Errors
- A single Fastify error handler maps: schema validation and JSON parse errors → `400 VALIDATION_ERROR`; domain `NotFoundError` → `404 NOT_FOUND`; `ConflictError` (duplicate member name) → `409 CONFLICT`; domain `ValidationError` (non-member payer, duplicate participants, amount bounds) → `400 VALIDATION_ERROR`; anything else → `500 INTERNAL` without leaking stack traces.
- Expense recording validates everything before mutating the store, so a rejected request records nothing.

## Risks / Trade-offs

- [In-memory store loses data on restart] → Accepted for this scope; the `Repository` interface isolates storage so a DB-backed implementation can replace it later.
- [Exponential DP cost for large groups] → Hard threshold of 20 non-zero members, greedy fallback, and `optimal` flag makes the guarantee explicit to clients.
- [Remainder cents always favor earliest-added members] → Deterministic and bounded to < 1 cent per participant per expense; documented in spec. A rotating policy could be added later without breaking the sum invariant.
- [Single-process concurrency] → Node's single thread serializes handler execution; each request's mutation is synchronous, so no interleaving within one process.
- [Two-decimal assumption] → Excludes currencies like JPY (0) or KWD (3); acceptable for a single-currency deployment and isolated in `money.ts`.
