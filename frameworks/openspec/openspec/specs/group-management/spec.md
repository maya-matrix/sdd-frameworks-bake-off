# group-management Specification

## Purpose

Lets people form a group for sharing costs and manage who belongs to it, so expenses and balances can be scoped to that group.

## Requirements

### Requirement: Create a group
The system SHALL allow a client to create a group via `POST /groups` with a non-empty `name` and an optional list of initial member names. On success it SHALL respond `201` with the group's server-generated `id`, `name`, and `members` (each with server-generated `id` and `name`), in the order the members were added.

#### Scenario: Create group with initial members
- **WHEN** a client sends `POST /groups` with `{"name": "Trip", "members": ["Alice", "Bob"]}`
- **THEN** the response status is `201`
- **AND** the body contains a group `id`, `name` `"Trip"`, and two members `Alice` and `Bob`, each with a distinct `id`

#### Scenario: Create group without members
- **WHEN** a client sends `POST /groups` with `{"name": "Flat"}`
- **THEN** the response status is `201` and `members` is an empty list

#### Scenario: Missing or blank group name
- **WHEN** a client sends `POST /groups` with no `name` or a name that is empty after trimming whitespace
- **THEN** the response status is `400` with a validation error

### Requirement: Add a member to a group
The system SHALL allow a client to add a member via `POST /groups/{groupId}/members` with a non-empty `name`. On success it SHALL respond `201` with the new member's `id` and `name`.

#### Scenario: Add member
- **WHEN** a client sends `POST /groups/{groupId}/members` with `{"name": "Carol"}` for an existing group
- **THEN** the response status is `201` with Carol's new member `id`
- **AND** a subsequent `GET /groups/{groupId}` lists Carol as a member

#### Scenario: Add member to unknown group
- **WHEN** a client sends `POST /groups/{groupId}/members` for a group id that does not exist
- **THEN** the response status is `404`

### Requirement: Member names are unique within a group
The system SHALL reject a member name that matches an existing member of the same group, compared after trimming whitespace and ignoring case. This applies both to initial members at group creation and to added members.

#### Scenario: Duplicate member name
- **WHEN** a group already has member `Alice` and a client adds a member named ` alice `
- **THEN** the response status is `409` and the group's members are unchanged

#### Scenario: Duplicate in initial member list
- **WHEN** a client sends `POST /groups` with `{"name": "Trip", "members": ["Bob", "BOB"]}`
- **THEN** the response status is `409` and no group is created

### Requirement: Read a group
The system SHALL return a group's `id`, `name`, and `members` via `GET /groups/{groupId}`, and SHALL respond `404` for an unknown group id.

#### Scenario: Get existing group
- **WHEN** a client sends `GET /groups/{groupId}` for an existing group
- **THEN** the response status is `200` with the group's id, name and members

#### Scenario: Get unknown group
- **WHEN** a client sends `GET /groups/{groupId}` for an id that does not exist
- **THEN** the response status is `404`

### Requirement: Consistent error responses
The system SHALL return every error as a JSON body of the form `{"error": {"code": <string>, "message": <string>}}`, using status `400` for malformed or invalid input, `404` for unknown resources, and `409` for conflicts.

#### Scenario: Malformed JSON body
- **WHEN** a client sends `POST /groups` with a body that is not valid JSON
- **THEN** the response status is `400` and the body has an `error` object with a `code` and `message`
