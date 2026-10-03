# Spec Delta

## Purpose

Lets members of a group record shared expenses — who paid, how much, for what, and which members share the cost equally — with exact money handling.

## ADDED Requirements

### Requirement: Record an expense
The system SHALL allow a client to record an expense via `POST /groups/{groupId}/expenses` with `payerId`, `amount`, `description`, and `splitBetween` (a list of member ids). On success it SHALL respond `201` with the expense's `id`, the submitted fields, and each participant's computed `share`.

#### Scenario: Record an evenly divisible expense
- **WHEN** group members are Alice, Bob and Carol, and a client records `{"payerId": <Alice>, "amount": "30.00", "description": "Dinner", "splitBetween": [<Alice>, <Bob>, <Carol>]}`
- **THEN** the response status is `201`
- **AND** each of Alice, Bob and Carol has a `share` of `"10.00"`

#### Scenario: Payer not among participants
- **WHEN** Alice pays `"20.00"` split between Bob and Carol only
- **THEN** the response status is `201` and Bob and Carol each have a `share` of `"10.00"` and Alice has no share

#### Scenario: Unknown group
- **WHEN** a client records an expense for a group id that does not exist
- **THEN** the response status is `404`

### Requirement: Money amounts are exact decimal strings
The system SHALL accept and return all money amounts as JSON strings matching `-?\d+(\.\d{1,2})?` (input amounts must not be negative), and SHALL perform all money arithmetic exactly in integer minor units (hundredths) with no floating-point rounding. Responses SHALL always format amounts with exactly two fraction digits.

#### Scenario: Amount given as a JSON number
- **WHEN** a client records an expense with `"amount": 12.5` (a number, not a string)
- **THEN** the response status is `400`

#### Scenario: Too many fraction digits
- **WHEN** a client records an expense with `"amount": "10.005"`
- **THEN** the response status is `400`

#### Scenario: Normalized output format
- **WHEN** a client records an expense with `"amount": "7.5"`
- **THEN** the returned `amount` is `"7.50"`

#### Scenario: Floating-point-prone values stay exact
- **WHEN** Alice records `"0.10"` and then `"0.20"`, both split between Alice and Bob
- **THEN** Bob's net balance is exactly `"-0.15"` and Alice's is exactly `"0.15"`

### Requirement: Expense validation
The system SHALL reject an expense with status `400` and record nothing when: the amount is zero, negative, or above `1000000000.00`; the description is missing or blank after trimming; `splitBetween` is missing or empty or contains duplicate ids; or the payer or any participant is not a member of the group.

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

### Requirement: Equal split with exact remainder allocation
The system SHALL split an expense into shares that differ by at most one minor unit and sum exactly to the expense amount. When the amount does not divide evenly, the leftover minor units SHALL go one each to the first participants in the group's member order (the order members were added).

#### Scenario: Uneven split
- **WHEN** Alice, Bob and Carol (added in that order) share a `"10.00"` expense
- **THEN** Alice's share is `"3.34"`, Bob's is `"3.33"` and Carol's is `"3.33"`
- **AND** the shares sum to exactly `"10.00"`

#### Scenario: Remainder order independent of request order
- **WHEN** the same `"10.00"` expense is recorded with `splitBetween` listed as `[<Carol>, <Bob>, <Alice>]`
- **THEN** Alice's share is still `"3.34"` and Bob's and Carol's are `"3.33"`

#### Scenario: Amount smaller than participant count
- **WHEN** `"0.02"` is split between Alice, Bob and Carol
- **THEN** Alice's and Bob's shares are `"0.01"` and Carol's share is `"0.00"`

### Requirement: List expenses
The system SHALL return all expenses of a group via `GET /groups/{groupId}/expenses`, in the order they were recorded, each including its `id`, `payerId`, `amount`, `description`, `splitBetween`, shares, and creation timestamp. It SHALL respond `404` for an unknown group.

#### Scenario: List recorded expenses
- **WHEN** two expenses have been recorded in a group and a client sends `GET /groups/{groupId}/expenses`
- **THEN** the response status is `200` and both expenses are returned in recording order

#### Scenario: No expenses
- **WHEN** a group has no expenses
- **THEN** `GET /groups/{groupId}/expenses` returns `200` with an empty list
