# Spec Delta

## Purpose

Shows where each member of a group stands financially and suggests the fewest money transfers needed to bring everyone back to zero.

## ADDED Requirements

### Requirement: Net balances per member
The system SHALL return, via `GET /groups/{groupId}/balances`, every member of the group with their net `balance`: the total they paid minus the total of their shares across all expenses. A positive balance means the member is owed money; a negative balance means they owe money. Members with no activity SHALL appear with `"0.00"`. It SHALL respond `404` for an unknown group.

#### Scenario: Single expense
- **WHEN** Alice pays `"30.00"` split equally between Alice, Bob and Carol
- **THEN** the balances are Alice `"20.00"`, Bob `"-10.00"`, Carol `"-10.00"`

#### Scenario: Multiple expenses accumulate
- **WHEN** Alice pays `"30.00"` split between Alice, Bob and Carol, and Bob pays `"12.00"` split between Alice and Bob
- **THEN** the balances are Alice `"14.00"`, Bob `"-4.00"`, Carol `"-10.00"`

#### Scenario: Member without activity
- **WHEN** Dave is a member but has not paid or participated in any expense
- **THEN** Dave's balance is `"0.00"`

#### Scenario: Unknown group
- **WHEN** a client requests balances for a group id that does not exist
- **THEN** the response status is `404`

### Requirement: Balances are exact and sum to zero
The system SHALL compute balances exactly in minor units, and the sum of all members' balances in a group SHALL always be exactly zero, regardless of how many uneven splits have been recorded.

#### Scenario: Repeated uneven splits
- **WHEN** Alice pays `"10.00"` split between Alice, Bob and Carol, three times
- **THEN** the balances are exact (Alice `"19.98"`, Bob `"-9.99"`, Carol `"-9.99"`) and sum to exactly `"0.00"`

### Requirement: Settle-up plan clears all debts
The system SHALL return, via `GET /groups/{groupId}/settle-up`, a list of `transfers`, each with `from` (member id), `to` (member id), and a positive `amount`. Applying all transfers (adding each amount to the sender's balance and subtracting it from the recipient's) SHALL bring every member's balance to exactly zero. It SHALL respond `404` for an unknown group.

#### Scenario: Simple debt
- **WHEN** Alice pays `"30.00"` split between Alice, Bob and Carol
- **THEN** the settle-up plan contains exactly two transfers: Bob → Alice `"10.00"` and Carol → Alice `"10.00"`

#### Scenario: Already settled
- **WHEN** all balances in the group are zero (including a group with no expenses)
- **THEN** the settle-up plan has an empty `transfers` list

#### Scenario: Transfers zero out balances
- **WHEN** any sequence of expenses has been recorded and the settle-up plan is applied to the reported balances
- **THEN** every resulting balance is exactly `"0.00"`

### Requirement: Settle-up uses the minimum number of transfers
The system SHALL return a plan with the fewest possible transfers whenever at most 20 members have a non-zero balance, and SHALL report `"optimal": true`. Above that size it SHALL return a valid plan with at most (number of non-zero members − 1) transfers and report `"optimal": false`. No transfer SHALL go from a member to themself, and no member SHALL both send and receive.

#### Scenario: Pairs that cancel out are settled directly
- **WHEN** balances are A `"+5.00"`, B `"+7.00"`, C `"-5.00"`, D `"-7.00"`
- **THEN** the plan has exactly 2 transfers (C → A `"5.00"`, D → B `"7.00"`) rather than 3
- **AND** `optimal` is `true`

#### Scenario: Chain of debts collapses
- **WHEN** A owes B `"10.00"` (via an expense B paid for A only) and B owes C `"10.00"` (via an expense C paid for B only)
- **THEN** the plan has exactly 1 transfer: A → C `"10.00"`

#### Scenario: Deterministic output
- **WHEN** the settle-up endpoint is called twice with no expenses recorded in between
- **THEN** both responses contain the same transfers in the same order
