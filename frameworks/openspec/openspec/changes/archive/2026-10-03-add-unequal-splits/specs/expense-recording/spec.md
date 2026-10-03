# Spec Delta

## MODIFIED Requirements

### Requirement: Record an expense
The system SHALL allow a client to record an expense via `POST /groups/{groupId}/expenses` with `payerId`, `amount`, `description`, an optional `splitType` (`"equal"`, `"exact"` or `"percentage"`; default `"equal"`), and either `splitBetween` (a list of member ids, for `"equal"`) or `splits` (a list of per-member entries, for `"exact"` and `"percentage"`). On success it SHALL respond `201` with the expense's `id`, the submitted fields, its `splitType`, and each participant's computed `share`.

#### Scenario: Record an evenly divisible expense
- **WHEN** group members are Alice, Bob and Carol, and a client records `{"payerId": <Alice>, "amount": "30.00", "description": "Dinner", "splitBetween": [<Alice>, <Bob>, <Carol>]}`
- **THEN** the response status is `201`
- **AND** each of Alice, Bob and Carol has a `share` of `"10.00"`
- **AND** the returned `splitType` is `"equal"`

#### Scenario: Explicit equal split type
- **WHEN** a client records the same expense with `"splitType": "equal"` added
- **THEN** the response status is `201` and the shares are identical to recording it without `splitType`

#### Scenario: Payer not among participants
- **WHEN** Alice pays `"20.00"` split between Bob and Carol only
- **THEN** the response status is `201` and Bob and Carol each have a `share` of `"10.00"` and Alice has no share

#### Scenario: Unknown split type
- **WHEN** a client records an expense with `"splitType": "shares"`
- **THEN** the response status is `400` and no expense is recorded

#### Scenario: Unknown group
- **WHEN** a client records an expense for a group id that does not exist
- **THEN** the response status is `404`

### Requirement: Expense validation
The system SHALL reject an expense with status `400` and record nothing when: the amount is zero, negative, or above `1000000000.00`; the description is missing or blank after trimming; the payer or any participant is not a member of the group; or the participant list for the chosen split type is invalid. For `"equal"`, `splitBetween` SHALL be present, non-empty and free of duplicate ids, and `splits` SHALL be absent. For `"exact"` and `"percentage"`, `splits` SHALL be present, non-empty and free of duplicate `memberId`s, and `splitBetween` SHALL be absent.

#### Scenario: Zero amount
- **WHEN** a client records an expense with `"amount": "0.00"`
- **THEN** the response status is `400`

#### Scenario: Payer not a member
- **WHEN** a client records an expense whose `payerId` is not a member of the group
- **THEN** the response status is `400` and no expense is recorded

#### Scenario: Participant not a member
- **WHEN** `splitBetween` contains an id that is not a member of the group (including a member of a different group)
- **THEN** the response status is `400` and no expense is recorded

#### Scenario: Empty split list
- **WHEN** a client records an expense with `"splitBetween": []`
- **THEN** the response status is `400`

#### Scenario: Duplicate participants
- **WHEN** `splitBetween` lists the same member id twice
- **THEN** the response status is `400`

#### Scenario: Missing splits for an unequal split type
- **WHEN** a client records an expense with `"splitType": "exact"` and no `splits` (or `"splits": []`)
- **THEN** the response status is `400` and no expense is recorded

#### Scenario: Mixing splitBetween and splits
- **WHEN** a client records an expense that provides both `splitBetween` and `splits`, whatever its `splitType`
- **THEN** the response status is `400` and no expense is recorded

#### Scenario: Duplicate member in splits
- **WHEN** a `"percentage"` expense lists the same `memberId` twice in `splits`
- **THEN** the response status is `400`

#### Scenario: Non-member in splits
- **WHEN** an `"exact"` expense's `splits` contains a `memberId` that is not a member of the group
- **THEN** the response status is `400` and no expense is recorded

### Requirement: List expenses
The system SHALL return all expenses of a group via `GET /groups/{groupId}/expenses`, in the order they were recorded, each including its `id`, `payerId`, `amount`, `description`, `splitType`, `splitBetween`, shares, and creation timestamp, plus the normalized `splits` for `"exact"` and `"percentage"` expenses. It SHALL respond `404` for an unknown group.

#### Scenario: List recorded expenses
- **WHEN** two expenses have been recorded in a group and a client sends `GET /groups/{groupId}/expenses`
- **THEN** the response status is `200` and both expenses are returned in recording order

#### Scenario: Mixed split types listed
- **WHEN** an equal expense and a percentage expense have been recorded
- **THEN** each listed expense carries its own `splitType`, and only the percentage expense includes `splits`

#### Scenario: No expenses
- **WHEN** a group has no expenses
- **THEN** `GET /groups/{groupId}/expenses` returns `200` with an empty list

## ADDED Requirements

### Requirement: Exact-amount split
For `"splitType": "exact"`, each `splits` entry SHALL be `{ "memberId", "amount" }` where `amount` is a non-negative money string (same format rules as the expense amount; zero allowed). Each participant's share SHALL equal its given amount, and the given amounts SHALL sum exactly to the expense amount; otherwise the system SHALL respond `400` and record nothing.

#### Scenario: Exact amounts that sum to the total
- **WHEN** Alice pays `"10.00"` with `"splitType": "exact"` and splits Alice `"6.00"`, Bob `"2.50"`, Carol `"1.50"`
- **THEN** the response status is `201` and the shares are Alice `"6.00"`, Bob `"2.50"`, Carol `"1.50"`

#### Scenario: Exact amounts below the total
- **WHEN** Alice pays `"10.00"` with exact splits Alice `"6.00"` and Bob `"3.99"`
- **THEN** the response status is `400` and no expense is recorded

#### Scenario: Exact amounts above the total
- **WHEN** Alice pays `"10.00"` with exact splits Alice `"6.00"` and Bob `"4.01"`
- **THEN** the response status is `400`

#### Scenario: Exact amount given as a JSON number
- **WHEN** an exact split entry has `"amount": 5` (a number, not a string)
- **THEN** the response status is `400`

#### Scenario: Exact amount with too many fraction digits
- **WHEN** an exact split entry has `"amount": "5.005"`
- **THEN** the response status is `400`

#### Scenario: Zero exact share
- **WHEN** Alice pays `"10.00"` with exact splits Alice `"10.00"` and Bob `"0"`
- **THEN** the response status is `201` and Bob's share is `"0.00"`

### Requirement: Percentage split
For `"splitType": "percentage"`, each `splits` entry SHALL be `{ "memberId", "percentage" }` where `percentage` is a JSON string matching `\d+(\.\d{1,2})?` between `0` and `100` inclusive. The percentages SHALL sum exactly to `100`, compared exactly with no floating-point rounding; otherwise the system SHALL respond `400` and record nothing.

#### Scenario: Percentages that sum to 100
- **WHEN** Alice pays `"200.00"` with `"splitType": "percentage"` and splits Alice `"50"`, Bob `"30"`, Carol `"20"`
- **THEN** the response status is `201` and the shares are Alice `"100.00"`, Bob `"60.00"`, Carol `"40.00"`

#### Scenario: Fractional percentages that sum to 100
- **WHEN** percentages are Alice `"33.33"`, Bob `"33.33"`, Carol `"33.34"`
- **THEN** the expense is accepted

#### Scenario: Percentages below 100
- **WHEN** percentages are Alice `"50"` and Bob `"49.99"`
- **THEN** the response status is `400` and no expense is recorded

#### Scenario: Percentages above 100
- **WHEN** percentages are Alice `"60"` and Bob `"40.01"`
- **THEN** the response status is `400`

#### Scenario: Percentage out of range
- **WHEN** a percentage entry is `"100.01"` or `"-5"`
- **THEN** the response status is `400`

#### Scenario: Percentage given as a JSON number
- **WHEN** a percentage entry is `50` (a number, not a string)
- **THEN** the response status is `400`

#### Scenario: Percentage with too many fraction digits
- **WHEN** a percentage entry is `"33.333"`
- **THEN** the response status is `400`

### Requirement: Percentage shares use exact largest-remainder allocation
The system SHALL compute each percentage share in whole minor units as the expense amount times the percentage, rounded down, and SHALL then give the leftover minor units one each to the participants with the largest discarded fractions, breaking ties by the group's member order (the order members were added). Shares SHALL always sum exactly to the expense amount and SHALL NOT depend on the order of `splits` in the request.

#### Scenario: Leftover cent goes to the largest remainder
- **WHEN** Alice, Bob and Carol (added in that order) share a `"10.00"` expense by percentages Alice `"33.33"`, Bob `"33.33"`, Carol `"33.34"`
- **THEN** Alice's share is `"3.33"`, Bob's is `"3.33"` and Carol's is `"3.34"`
- **AND** the shares sum to exactly `"10.00"`

#### Scenario: Ties broken by member order
- **WHEN** Alice and Bob (added in that order) share a `"0.01"` expense at `"50"` percent each
- **THEN** Alice's share is `"0.01"` and Bob's share is `"0.00"`

#### Scenario: Allocation independent of request order
- **WHEN** the same `"0.01"` expense is recorded with `splits` listing Bob before Alice
- **THEN** Alice's share is still `"0.01"` and Bob's is `"0.00"`

#### Scenario: Remainder tie among several participants
- **WHEN** a `"0.02"` expense is split between Alice, Bob and Carol (added in that order) at `"25"`, `"25"` and `"50"` percent
- **THEN** Alice's share is `"0.01"`, Bob's is `"0.00"` and Carol's is `"0.01"` (Alice and Bob tie on remainder, so the earlier member wins)

### Requirement: Unequal split details in expense responses
For `"exact"` and `"percentage"` expenses, the system SHALL return `splits` with the submitted per-member values normalized to exactly two fraction digits (e.g. `"60"` → `"60.00"`), and SHALL return `splitBetween` as the participant ids in the order they were listed in `splits`. Equal-split expenses SHALL NOT include `splits`.

#### Scenario: Percentage expense response
- **WHEN** a percentage expense is recorded with splits Alice `"60"` and Bob `"40"`
- **THEN** the response contains `"splitType": "percentage"`, `splits` of Alice `"60.00"` and Bob `"40.00"`, and `"splitBetween": [<Alice>, <Bob>]`

#### Scenario: Equal expense response unchanged
- **WHEN** an equal expense is recorded with `splitBetween`
- **THEN** the response contains every field it contained before this change with the same values, plus `"splitType": "equal"`, and no `splits` field
