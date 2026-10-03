# Proposal

## Why

People who share costs (trips, flats, dinners) need a simple way to record who paid for what and to work out who owes whom without spreadsheets. The project has no code yet; this change establishes a greenfield HTTP API that tracks shared expenses per group and computes exact balances and a minimal settle-up plan.

## What Changes

- New HTTP JSON API service (greenfield; no existing code is modified).
- Create groups and add members to a group.
- Record an expense in a group with a payer, a positive amount, a description, and the subset of group members it is split equally between. Payer and all participants must be members of the group.
- Expense amounts are handled as integer minor units (e.g. cents). Equal splits that do not divide evenly assign the leftover minor units deterministically, so every expense's shares always sum to exactly the expense amount and balances always sum to exactly zero.
- Endpoint returning each member's net balance in a group (positive = is owed, negative = owes).
- Settle-up endpoint returning a list of suggested transfers (from, to, amount) that clears all balances using the minimum number of transfers.
- Automated unit and HTTP-level tests covering money arithmetic, balances, settle-up minimality, and validation errors.

**Assumptions** (no constraints were given; recorded here and in design.md):
- Single currency per deployment; amounts are exchanged in the API as decimal strings with at most two fraction digits (e.g. `"12.34"`) to avoid float precision issues on the wire.
- No authentication: "any member can record" is enforced as "the payer and all split participants must be members of the group". Identity/auth is out of scope.
- In-memory storage; data does not survive restarts. Persistence is out of scope.
- Out of scope: editing/deleting expenses, removing members, unequal/percentage splits, recording settlement payments, multi-currency.

## Capabilities

### New Capabilities
- `group-management`: Creating groups, adding members, and reading group details.
- `expense-recording`: Recording equal-split expenses in a group, validation rules, exact share allocation, and listing expenses.
- `balance-settlement`: Computing each member's exact net balance in a group and producing a minimum-transfer settle-up plan.

### Modified Capabilities
<!-- None: there are no existing specs. -->

## Impact

- New source tree (TypeScript on Node.js), HTTP server, in-memory repository, and test suite.
- New runtime and dev dependencies (HTTP framework, test runner); see design.md.
- New public REST API surface under `/groups`.
