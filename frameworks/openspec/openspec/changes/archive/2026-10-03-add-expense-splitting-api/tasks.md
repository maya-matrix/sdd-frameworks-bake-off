# Tasks

## 1. Project setup

- [x] 1.1 Create `package.json` (Node 20+, `type: module`) with scripts `build`, `start`, `dev`, `test`, `typecheck`; add deps `fastify` and dev deps `typescript`, `tsx`, `vitest`, `fast-check`, `@types/node`; verify `npm install` succeeds
- [x] 1.2 Add strict `tsconfig.json` and `vitest.config.ts`, plus `.gitignore` (node_modules, dist); verify `npm run typecheck` and `npm test` (no tests yet, `passWithNoTests`) both exit 0
- [x] 1.3 Create the `src/` and `test/` layout from design D6; verify the directories exist

## 2. Money and split domain (exact arithmetic)

- [x] 2.1 Implement `src/domain/money.ts`: parse strings matching `^\d+(\.\d{1,2})?$` to `bigint` cents without using `Number`/`parseFloat`, and format `bigint` cents to two-decimal strings incl. negatives (`-15n` → `"-0.15"`); verify unit tests for `"7.5"`→`750n`, `"0.10"`, `"1000000000.00"`, rejections of `"10.005"`, `"-1"`, `"1e3"`, `""`, `" 1"`, and round-trip formatting
- [x] 2.2 Implement `src/domain/split.ts` equal split per design D3 (remainder cents to earliest participants in member order); verify unit tests for `10.00/3` → `3.34, 3.33, 3.33`, `0.02/3` → `0.01, 0.01, 0.00`, request-order independence, and a fast-check property that shares sum exactly to the amount and differ by ≤ 1 cent

## 3. Balances and settle-up domain

- [x] 3.1 Implement `src/domain/balances.ts` (paid − shares per member, insertion order, zero for inactive members); verify unit tests for the spec scenarios (single expense, accumulated expenses, inactive member, triple `10.00/3` → `19.98/-9.99/-9.99`) and a fast-check property that balances always sum to `0n`
- [x] 3.2 Implement `src/domain/settle.ts` greedy within-subset settlement (largest debtor ↔ largest creditor, ties by insertion order); verify unit tests that a zero-sum set of size s yields s − 1 transfers and debtors only send / creditors only receive
- [x] 3.3 Add the exact bitmask DP (design D5) for ≤ 20 non-zero balances with partition reconstruction, greedy fallback above 20 with `optimal: false`, and deterministic transfer ordering; verify unit tests: `+5,+7,−5,−7` → 2 transfers, chain A→B→C → 1 transfer, all-zero → empty, 21 non-zero members → `optimal: false` with ≤ n − 1 transfers, repeated calls give identical output
- [x] 3.4 Add property-based tests for settle-up: for random balance sets (≤ 10 members) applying transfers zeroes all balances, amounts are positive, no self-transfers, and the transfer count equals a brute-force minimum; verify `npm test` passes and a 20-member worst case completes in under 1 s

## 4. Storage and HTTP foundation

- [x] 4.1 Implement `src/store/memoryStore.ts` with a `Repository` interface for groups, members (with insertion index), and expenses (with stored shares and `createdAt`), plus domain error classes (`NotFoundError`, `ConflictError`, `ValidationError`); verify unit tests for create/get/add/list and case-insensitive trimmed name uniqueness
- [x] 4.2 Implement `src/http/app.ts` `buildApp(store)` with the error handler from design D7 mapping to `{"error": {"code", "message"}}` (400/404/409/500), and `src/server.ts` listening on `PORT` (default 3000); verify an `app.inject()` test that malformed JSON returns `400` with the error shape and an unknown route returns `404` with the error shape

## 5. Group management endpoints

- [x] 5.1 Implement `POST /groups`, `GET /groups/:groupId`, `POST /groups/:groupId/members` with JSON-schema validation; verify `test/http/groups.test.ts` covers every `group-management` spec scenario (create with/without members, blank name 400, add member 201 then visible in GET, unknown group 404, duplicate names 409 on add and on create with no group created)

## 6. Expense endpoints

- [x] 6.1 Implement `POST /groups/:groupId/expenses` (amount as string-with-pattern schema; validate payer/participants membership, non-empty and duplicate-free `splitBetween`, amount bounds and non-blank description before any mutation) and `GET /groups/:groupId/expenses`; verify `test/http/expenses.test.ts` covers every `expense-recording` spec scenario, including JSON-number amount 400, `"10.005"` 400, `"7.5"` → `"7.50"`, uneven-split shares, member from another group 400, and that rejected requests leave the expense list unchanged

## 7. Balance and settle-up endpoints

- [x] 7.1 Implement `GET /groups/:groupId/balances`; verify `test/http/balances.test.ts` covers every `balance-settlement` balance scenario, including `0.10 + 0.20` → exactly `"0.15"/"-0.15"`, inactive member `"0.00"`, sum-to-zero, and unknown group 404
- [x] 7.2 Implement `GET /groups/:groupId/settle-up` returning `{transfers: [{from, to, amount}], optimal}`; verify `test/http/settle-up.test.ts` covers every settle-up scenario (simple debt, already settled, pairs cancel → 2 transfers, chain → 1 transfer, determinism, unknown group 404) and that applying returned transfers to `/balances` output yields all zeros

## 8. Documentation and integration check

- [x] 8.1 Write `README.md` with setup, run and test commands, the endpoint list with example requests/responses, the money format, the remainder rule, the settle-up optimality threshold, and stated assumptions (in-memory, no auth); verify the documented `curl` walkthrough runs as written against `npm start`
- [x] 8.2 Run the full integration check: `npm run typecheck`, `npm test` and `npm run build` all exit 0, and a scripted end-to-end flow (create group → add members → record several uneven expenses → balances → settle-up) against the running server returns balances summing to `"0.00"` and transfers that clear them
