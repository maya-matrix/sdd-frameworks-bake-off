# Research: Expense Splitting API

## 1. Language and web framework

- **Decision**: Python 3.12 with FastAPI (Pydantic v2 for request validation), served by
  Uvicorn. Project and dependencies managed with `uv`.
- **Rationale**: Python integers are arbitrary precision, so integer-cent arithmetic is exact
  with no overflow. FastAPI gives typed request/response models, automatic validation errors
  and OpenAPI output that matches `contracts/openapi.yaml`, and an in-process `TestClient`
  that makes API-level tests fast. Python 3.12 is installed locally.
- **Alternatives considered**: Node/TypeScript + Fastify (JS `number` is a float; money would
  need `bigint` or a decimal library everywhere, which is easy to get wrong — conflicts with
  Constitution II by default). Go (exact `int64` is fine, but more boilerplate for
  validation and tests). Flask (no built-in typed validation).

## 2. Money representation

- **Decision**: Internally, every amount is a Python `int` number of cents. At the API
  boundary, amounts are JSON **strings** matching `^(0|[1-9][0-9]*)\.[0-9]{2}$` (e.g.
  `"10.00"`), parsed by string manipulation directly into cents — never via `float`. A JSON
  number in an amount field is rejected (422). Output is formatted from cents back to the
  same string form; negative balances are rendered as `"-10.00"`.
- **Rationale**: Constitution II forbids binary floating point for money and requires a
  lossless boundary format. Strings with exactly two decimals are unambiguous; JSON numbers
  are commonly decoded as floats by clients and by Python's `json` module.
- **Alternatives considered**: `decimal.Decimal` internally (exact, but invites accidental
  quantize/rounding steps and is unnecessary when the unit is fixed at cents). Integer cents
  on the wire (lossless, but less readable and the spec's examples use decimal amounts).
- **Validation rules**: amount > 0, at most `1000000000.00` per expense, exactly two
  decimals; `"10.5"`, `"10.005"`, `"1e3"`, `"-5.00"`, `"010.00"` and numbers are rejected.

## 3. Equal-split remainder allocation

- **Decision**: `base, remainder = divmod(amount_cents, n)`. Each participant owes `base`;
  the first `remainder` participants in request order owe `base + 1`.
- **Rationale**: This is FR-005 verbatim; deterministic, documented, and shares sum exactly
  to the amount by construction. Shares are computed once when the expense is recorded and
  stored with it, so balances never recompute or re-round.

## 4. Minimum-transfer settle-up

- **Decision**: Exact optimum via subset dynamic programming. With nonzero balances
  `b_1..b_k` (sum 0), the minimum number of transfers is `k − p`, where `p` is the maximum
  number of disjoint zero-sum groups the members can be partitioned into (each group of size
  `g` settles with `g − 1` transfers). Steps:
  1. Drop zero balances.
  2. Compute `dp[mask]` = maximum zero-sum groups within `mask`, where
     `dp[mask] = max_i dp[mask without i] + (sum(mask) == 0)`, processed by popcount layer.
  3. Reconstruct the partition by walking back from the full mask, then settle each group
     greedily (largest debtor pays largest creditor), which uses exactly `g − 1` transfers
     inside a zero-sum group with no zero-sum proper subgroup.
  4. Order output transfers deterministically (by debtor name, then creditor name).
- **Performance**: Measured locally on Python 3.12 with 20 nonzero balances
  (2^20 states): pure-Python loop 1.85 s (misses SC-005); NumPy vectorized by popcount layer
  0.10 s. **Use NumPy** for the DP tables (`int64` subset sums, `int8` dp). Subset sums are
  bounded by the sum of absolute balances; the service asserts this stays below 2^62 and
  otherwise falls back to the pure-Python implementation (exact, slower), so exactness never
  depends on fixed-width integers.
- **Rationale**: FR-009 requires the true minimum; greedy matching of largest debtor with
  largest creditor is not optimal. Counterexample (verified by brute force): balances
  −7, −8, +2, +6, +7 — greedy uses 4 transfers, optimum is 3 ({−7, +7} and {−8, +2, +6}).
  This case MUST be a regression test. The spec caps groups at 20 members, keeping 2^20
  states feasible.
- **Alternatives considered**: Greedy (≤ k−1 transfers, not minimum). Backtracking DFS
  (fast typically, exponential worst case without a clear bound). Pure-Python DP (correct
  but 1.85 s worst case).

## 5. Storage

- **Decision**: In-memory repository (dicts keyed by UUID) behind a small repository class,
  guarded by a `threading.Lock` for writes. One instance per app; tests get a fresh app.
- **Rationale**: The spec only requires persistence while the service runs. A repository
  interface keeps a later move to SQLite/Postgres local to one module.
- **Alternatives considered**: SQLite (durable, but adds schema/migration work not required
  by the spec).

## 6. Testing

- **Decision**: `pytest` with three layers: unit tests for money parsing/formatting,
  splitting, balances and settle-up; property-based tests with `hypothesis` for the
  invariants (shares sum to amount; balances sum to zero; settle-up clears all balances and
  matches a brute-force minimum for small groups); API tests through FastAPI `TestClient`
  covering every endpoint, validation error and not-found case. A performance test asserts
  SC-005 (20 members, 1,000 expenses, < 1 s for balances + settle-up). Run with
  `uv run pytest`.
- **Rationale**: Constitution I (every behavior tested, single command) and the Money
  Handling Constraints (uneven splits + conservation invariants asserted).

## 7. Identifiers and errors

- **Decision**: UUID4 strings for group, member and expense IDs. Errors use one JSON shape:
  `{"error": {"code": "...", "message": "...", "field": "..."}}` with 404 `not_found`,
  409 `duplicate_member_name`, 422 `validation_error`. FastAPI's default validation response
  is replaced by this shape.
- **Rationale**: FR-012/FR-013 require clear messages naming the field and distinct
  not-found errors.
