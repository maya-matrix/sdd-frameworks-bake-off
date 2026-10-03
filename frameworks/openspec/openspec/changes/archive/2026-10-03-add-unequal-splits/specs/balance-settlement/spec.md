# Spec Delta

## MODIFIED Requirements

### Requirement: Net balances per member
The system SHALL return, via `GET /groups/{groupId}/balances`, every member of the group with their net `balance`: the total they paid minus the total of their shares across all expenses, whatever each expense's split type. A positive balance means the member is owed money; a negative balance means they owe money. Members with no activity SHALL appear with `"0.00"`. Each entry SHALL contain exactly `memberId`, `name` and `balance`. It SHALL respond `404` for an unknown group.

#### Scenario: Single expense
- **WHEN** Alice pays `"30.00"` split equally between Alice, Bob and Carol
- **THEN** the balances are Alice `"20.00"`, Bob `"-10.00"`, Carol `"-10.00"`

#### Scenario: Multiple expenses accumulate
- **WHEN** Alice pays `"30.00"` split between Alice, Bob and Carol, and Bob pays `"12.00"` split between Alice and Bob
- **THEN** the balances are Alice `"14.00"`, Bob `"-4.00"`, Carol `"-10.00"`

#### Scenario: Member without activity
- **WHEN** Dave is a member but has not paid or participated in any expense
- **THEN** Dave's balance is `"0.00"`

#### Scenario: Unequal splits reflected in balances
- **WHEN** Alice pays `"10.00"` split exactly as Alice `"6.00"`, Bob `"2.50"`, Carol `"1.50"`, and Bob pays `"10.00"` split by percentage as Alice `"33.33"`, Bob `"33.33"`, Carol `"33.34"`
- **THEN** the balances are Alice `"0.67"`, Bob `"4.17"`, Carol `"-4.84"`, and they sum to exactly `"0.00"`

#### Scenario: Response format unchanged
- **WHEN** a client requests balances for a group that has equal, exact and percentage expenses
- **THEN** the response is `{"balances": [...]}` with one entry per member in member order, each having exactly the fields `memberId`, `name` and `balance`

#### Scenario: Unknown group
- **WHEN** a client requests balances for a group id that does not exist
- **THEN** the response status is `404`
