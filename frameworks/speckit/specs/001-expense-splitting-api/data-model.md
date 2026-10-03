# Data Model: Expense Splitting API

All money values are stored as integer cents (`int`). They are rendered at the API boundary
as two-decimal strings (see [research.md](research.md) §2). IDs are UUID4 strings.

## Group

| Field      | Type            | Rules                                              |
|------------|-----------------|----------------------------------------------------|
| id         | UUID            | Generated on create                                |
| name       | string          | Required; trimmed; 1–100 chars                     |
| members    | list[Member]    | Insertion order preserved; max 20 (spec assumption) |
| expenses   | list[Expense]   | Insertion order preserved                          |
| created_at | UTC timestamp   | Generated on create                                |

## Member

| Field    | Type   | Rules                                                              |
|----------|--------|--------------------------------------------------------------------|
| id       | UUID   | Generated on create                                                |
| group_id | UUID   | Owning group; a member belongs to exactly one group                |
| name     | string | Required; trimmed; 1–100 chars; unique per group, case-insensitive (FR-003) |

Adding a 21st member is rejected (422, field `name`, message states the 20-member limit).

## Expense

| Field        | Type          | Rules                                                          |
|--------------|---------------|----------------------------------------------------------------|
| id           | UUID          | Generated on create                                            |
| group_id     | UUID          | Owning group                                                   |
| description  | string        | Required; trimmed; 1–200 chars                                 |
| amount_cents | int           | 1 ≤ amount ≤ 100,000,000,000 (€1,000,000,000.00)               |
| payer_id     | UUID          | Must be a member of the group                                  |
| shares       | list[Share]   | One per participant, in request order; computed on create      |
| created_at   | UTC timestamp | Generated on create                                            |

**Share**: `{member_id: UUID, amount_cents: int}`.

Validation (FR-004, FR-012; all-or-nothing — nothing stored on failure):
- `participant_ids` non-empty; no duplicates; every ID a member of this group.
- `payer_id` a member of this group (payer need not be a participant).

Split rule (FR-005): `base, r = divmod(amount_cents, n)`; participant at index `i` owes
`base + (1 if i < r else 0)`. Invariant: `sum(shares) == amount_cents`.

Expenses are immutable once recorded (no edit/delete in this version).

## Balance (derived, not stored)

For each member `m` in the group:
`balance(m) = Σ amount_cents of expenses paid by m − Σ share amounts owed by m`.

Invariant: `Σ balance(m) == 0` for every group. Every member appears, including members with
no expenses (balance 0). Order: member insertion order.

## Transfer (derived, not stored)

| Field          | Type | Rules                              |
|----------------|------|------------------------------------|
| from_member_id | UUID | Member with negative balance (pays) |
| to_member_id   | UUID | Member with positive balance (receives) |
| amount_cents   | int  | > 0                                 |

Invariants (FR-008, FR-009): applying all transfers (`from += amount`, `to −= amount`) makes
every balance exactly 0; the count equals the minimum possible (`k − p`, research §4).
Requesting a settle-up never mutates state (FR-010).

## State transitions

None. Groups and members are created; expenses are appended. Balances and transfers are
pure functions of the current expense list.
