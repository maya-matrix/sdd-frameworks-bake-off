<!--
Sync Impact Report
- Version change: (unversioned template) → 1.0.0
- Modified principles: n/a (initial ratification)
- Added principles:
  - I. Every Behavior Is Tested (NON-NEGOTIABLE)
  - II. Exact Money Arithmetic (NON-NEGOTIABLE)
- Added sections: Money Handling Constraints, Quality Gates, Governance
- Removed sections: template slots for principles 3–5 (user supplied two principles;
  no others were inferred to avoid inventing governance)
- Templates: not modified (read the constitution at runtime; out of scope for this command)
- Follow-up TODOs: none
-->

# SplitIt Constitution

## Core Principles

### I. Every Behavior Is Tested (NON-NEGOTIABLE)

- Every user-observable behavior (each endpoint, each business rule, each validation and
  error response) MUST be covered by at least one automated test.
- Tests MUST run without manual steps via a single documented command and MUST pass before
  a change is considered done.
- A bug fix MUST include a test that fails without the fix and passes with it.
- Behavior without a test is treated as unspecified; it MUST NOT be relied upon or shipped.

**Rationale**: Automated tests are the only durable proof that behavior matches the spec and
stays that way as features are added.

### II. Exact Money Arithmetic (NON-NEGOTIABLE)

- Monetary amounts MUST be represented exactly: integer minor units (e.g. cents) or an
  arbitrary-precision decimal type. Binary floating point (`float`, `double`, JS `number`
  for fractional values) MUST NOT be used to store or compute money.
- Any operation that divides money (splits, percentages) MUST allocate every minor unit:
  the parts MUST sum exactly to the original amount, with remainders distributed by a
  deterministic, documented rule.
- Derived totals MUST be conserved: within a group, all net balances MUST sum to exactly
  zero, and suggested settlements MUST clear all balances exactly.
- Money crossing the API boundary MUST use a lossless format (e.g. decimal string or integer
  minor units) and MUST be validated; amounts with more precision than the currency allows
  MUST be rejected rather than silently rounded.

**Rationale**: Users trust an expense-splitting tool only if every cent is accounted for;
a single lost or invented cent is a correctness bug, not a cosmetic one.

## Money Handling Constraints

- Every money-related behavior covered by Principle I MUST include tests for uneven splits
  (e.g. 10.00 split three ways) and MUST assert the conservation invariants of Principle II.
- Rounding, where unavoidable, MUST happen only at an explicitly named allocation step,
  never implicitly through type conversion or formatting.

## Quality Gates

- Specs MUST state the expected behavior precisely enough to be written as tests.
- Plans MUST name the money representation and the remainder-allocation rule.
- A feature is complete only when all tests pass and every behavior in its spec maps to at
  least one test.

## Governance

- This constitution supersedes conflicting practices, specs, plans, and tasks. Any conflict
  MUST be resolved in favor of the constitution or by amending it.
- Amendments MUST be made through `/speckit-constitution`, documented in the Sync Impact
  Report, and versioned with semantic versioning: MAJOR for removing or redefining a
  principle, MINOR for adding a principle or materially expanding guidance, PATCH for
  clarifications and wording.
- Every plan MUST include a Constitution Check against both principles, and every review
  MUST verify compliance before a change is accepted.

**Version**: 1.0.0 | **Ratified**: 2026-10-03 | **Last Amended**: 2026-10-03
