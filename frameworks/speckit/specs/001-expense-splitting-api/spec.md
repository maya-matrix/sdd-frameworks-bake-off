# Feature Specification: Expense Splitting API

**Feature Branch**: `001-expense-splitting-api`

**Created**: 2026-10-03

**Status**: Draft

**Input**: User description: "Build a web API for splitting expenses. Users create groups and add members. Any member can record an expense with a payer, amount, description, and the members it's split equally between. Provide an endpoint showing each member's net balance in the group, and a settle-up endpoint suggesting the minimum transfers to clear all debts. Money calculations must be exact, with no rounding errors. Include automated tests."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create a group and add members (Priority: P1)

A user creates a group (e.g. "Lisbon trip") and adds the people who share costs in it.

**Why this priority**: Every other capability needs a group with members. On its own it gives
users a shared place to track a set of people.

**Independent Test**: Create a group, add three members, retrieve the group and confirm its
name and all three members are returned.

**Acceptance Scenarios**:

1. **Given** no groups exist, **When** a user creates a group named "Lisbon trip", **Then** the
   group is created with a unique identifier, that name, and no members.
2. **Given** a group exists, **When** members "Ana", "Ben" and "Cleo" are added, **Then**
   retrieving the group lists all three members, each with a unique identifier.
3. **Given** a group already has a member named "Ana", **When** another member named "Ana" is
   added, **Then** the request is rejected with an error explaining the name is taken.
4. **Given** a request to create a group or member with an empty name, **When** it is
   submitted, **Then** it is rejected with a validation error.

---

### User Story 2 - Record an expense split equally (Priority: P1)

A member records an expense: who paid, how much, what it was for, and which members share it.
The amount is split equally between those members, exact to the cent.

**Why this priority**: Recording expenses is the core purpose of the product.

**Independent Test**: In a group with Ana, Ben and Cleo, record "Dinner", €30.00 paid by Ana,
split between all three; retrieve the group's expenses and confirm the expense and each
member's share of €10.00.

**Acceptance Scenarios**:

1. **Given** a group with Ana, Ben and Cleo, **When** Ana records "Dinner" for €30.00 split
   between all three, **Then** the expense is stored and each member's share is €10.00.
2. **Given** the same group, **When** Ana records "Taxi" for €10.00 split between all three,
   **Then** the shares are €3.34, €3.33 and €3.33 and they sum to exactly €10.00.
3. **Given** the same group, **When** Ben records "Museum" for €20.00 paid by Ben and split
   only between Ana and Cleo, **Then** the expense is accepted (the payer need not share it).
4. **Given** an expense whose payer or a participant is not a member of the group, **When**
   it is submitted, **Then** it is rejected with an error naming the unknown member.
5. **Given** an expense with an amount of zero, a negative amount, more than two decimal
   places, an empty description, or no participants, **When** it is submitted, **Then** it is
   rejected with a validation error and nothing is stored.

---

### User Story 3 - View net balances (Priority: P1)

A member views how much each person in the group is owed (positive) or owes (negative)
across all recorded expenses.

**Why this priority**: Knowing who owes whom is the main reason to record expenses.

**Independent Test**: Record a known set of expenses, request balances, and compare each
member's net balance to hand-calculated values; confirm the balances sum to exactly zero.

**Acceptance Scenarios**:

1. **Given** Ana paid €30.00 split between Ana, Ben and Cleo, **When** balances are
   requested, **Then** Ana is +€20.00, Ben is −€10.00 and Cleo is −€10.00.
2. **Given** Ana paid €10.00 split between Ana, Ben and Cleo, **When** balances are
   requested, **Then** the balances sum to exactly €0.00 (no cent is lost or created).
3. **Given** a group with members but no expenses, **When** balances are requested, **Then**
   every member is listed with a balance of €0.00.

---

### User Story 4 - Settle up with the fewest transfers (Priority: P2)

A member asks how the group can settle all debts and receives a list of transfers
("Ben pays Ana €10.00") that clears every balance using the fewest transfers possible.

**Why this priority**: It turns balances into concrete actions, but balances alone already
deliver value.

**Independent Test**: Record expenses producing known balances, request the settle-up
suggestion, apply the suggested transfers to the balances by hand, and confirm every balance
becomes exactly zero with the minimum number of transfers.

**Acceptance Scenarios**:

1. **Given** balances Ana +€20.00, Ben −€10.00, Cleo −€10.00, **When** settle-up is
   requested, **Then** the result is two transfers: Ben pays Ana €10.00 and Cleo pays Ana
   €10.00.
2. **Given** balances A +€5.00, B −€5.00, C +€7.00, D −€7.00, **When** settle-up is requested,
   **Then** exactly two transfers are suggested (B pays A €5.00, D pays C €7.00).
3. **Given** all balances are zero, **When** settle-up is requested, **Then** the result is
   an empty list of transfers.
4. **Given** any set of balances, **When** the suggested transfers are applied, **Then**
   every member's balance becomes exactly €0.00 and every transfer amount is positive.

---

### Edge Cases

- An amount that does not divide evenly (e.g. €0.01 split between three members): one member
  owes €0.01, the others €0.00, and the shares sum exactly to the amount.
- The same member listed twice as a participant: the request is rejected.
- The payer is the only participant: the expense is accepted and changes no balances.
- Requests for a group, member or expense that does not exist return a "not found" error.
- Amounts given with a currency precision beyond two decimals (e.g. 10.005) are rejected,
  never rounded.
- Amounts given in a lossy numeric form that cannot be represented exactly are rejected.
- Very large amounts (up to at least €1,000,000,000.00 per expense) are handled without loss
  of precision.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow creating a group with a non-empty name and return a unique
  group identifier.
- **FR-002**: System MUST allow retrieving a group with its name and members.
- **FR-003**: System MUST allow adding a member with a non-empty name to a group; member
  names MUST be unique within a group (case-insensitive) and each member gets a unique
  identifier.
- **FR-004**: System MUST allow recording an expense in a group with a payer, a positive
  amount, a non-empty description, and one or more distinct participants, all of whom
  (including the payer) MUST be members of that group.
- **FR-005**: System MUST split each expense equally between its participants, exact to the
  cent: each share is the amount divided by the number of participants, rounded down to the
  cent, and the leftover cents are given one each to participants in the order they were
  listed in the request. Shares MUST always sum to exactly the expense amount.
- **FR-006**: System MUST allow listing a group's expenses, including payer, amount,
  description, participants and each participant's share.
- **FR-007**: System MUST report each member's net balance in a group, defined as the total
  that member paid minus the total of that member's shares. Every member MUST appear, and
  the balances MUST sum to exactly zero.
- **FR-008**: System MUST provide a settle-up suggestion: a list of transfers (from member,
  to member, positive amount) that, when applied, brings every member's balance to exactly
  zero.
- **FR-009**: The settle-up suggestion MUST use the minimum possible number of transfers for
  the group's current balances.
- **FR-010**: The settle-up suggestion MUST be read-only: requesting it MUST NOT change any
  balance or record any payment.
- **FR-011**: System MUST accept and return money amounts in an exact textual decimal form
  with exactly two decimal places (e.g. "10.00"), and MUST reject amounts with more than two
  decimal places rather than rounding them.
- **FR-012**: System MUST reject invalid requests with a clear error message identifying the
  problem field, and MUST NOT store any part of a rejected request.
- **FR-013**: System MUST return a distinct "not found" error for unknown groups and
  members.
- **FR-014**: Every behavior in FR-001 to FR-013 MUST be covered by automated tests that run
  with a single command, including uneven-split cases and the zero-sum checks.

### Key Entities

- **Group**: A named set of people sharing costs. Has members and expenses.
- **Member**: A person in exactly one group, identified by a unique identifier and a name
  unique within the group.
- **Expense**: A cost recorded in a group: payer (a member), amount, description,
  participants (members sharing it, in listed order), and the computed share for each.
- **Balance**: A derived value per member: total paid minus total owed. Not stored.
- **Transfer**: A derived settle-up suggestion: debtor, creditor, and positive amount.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every recorded expense, participant shares sum to exactly the expense
  amount in 100% of cases, including amounts that do not divide evenly.
- **SC-002**: For every group, member balances sum to exactly zero in 100% of cases.
- **SC-003**: For every group, applying the settle-up transfers leaves every balance at
  exactly zero, and no other set of transfers clearing the same balances is shorter.
- **SC-004**: A user can create a group, add members, record an expense and see balances in
  four requests or fewer.
- **SC-005**: Balance and settle-up results for a group of 20 members with 1,000 expenses are
  returned in under one second.
- **SC-006**: Every functional requirement is verified by at least one automated test, and
  the full test suite passes.

## Assumptions

- Each group uses a single currency with two decimal places (shown as euros in examples);
  multi-currency support and currency conversion are out of scope.
- No user accounts or authentication: anyone with access to the API can act on any group.
  "Any member can record an expense" means the payer is any member of the group.
- Groups have at most 20 members, which keeps an exact minimum-transfer calculation
  practical.
- Removing members, editing or deleting expenses, and recording actual settlement payments
  are out of scope for this version.
- Data must persist across requests while the service is running; durable storage choice is
  left to planning.
