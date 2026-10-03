---
title: Expense Splitting API
labels: [ready-for-agent]
---

## Problem Statement

When a group of people share costs (a trip, a flat, a dinner), working out who owes whom quickly gets messy. Different people pay for different things, and not every expense involves everyone. Splitting by hand produces fractions of a cent that don't add up, so totals drift. Even when everyone knows their net position, it's not obvious how to square up with as few transfers as possible. The group needs a single source of truth that records who paid for what, shows each person's exact net position, and suggests the fewest transfers to settle.

## Solution

A web API, with no authentication, where anyone can create a Group with a Currency and add Members by name. Any caller can record an Expense: a Payer, an Amount in whole minor units, a description, and the Participants it is split equally between. Each Expense is split into whole-minor-unit Shares that add up exactly to its Amount. Leftover minor units (the Remainder) go one at a time to Participants in the order they joined the Group. The API reports every Member's Balance, which always add up to exactly zero across the Group. It proposes a Settle-up: the true minimum number of Suggested Transfers when the group is small enough, and a greedy fallback otherwise. Members can record Payments to reduce what they owe, delete mistaken Expenses and Payments, and leave the Group once their Balance reaches zero.

## User Stories

### Groups

1. As a person organising shared costs, I want to create a Group with a name and a Currency, so that all of our Expenses are tracked in one place and in one currency.
2. As a Group creator, I want to add the initial Members by name when creating the Group, so that I can start recording Expenses straight away.
3. As a Group creator, I want an unsupported or malformed Currency code to be rejected, so that Amounts are never ambiguous.
4. As a Member, I want to fetch a Group and see its name, Currency and current Members, so that I know who I can split Expenses with.
5. As a client, I want a clear "not found" response for a Group that doesn't exist, so that I can tell a bad link from a server failure.

### Members

6. As a Member, I want to add a new Member to an existing Group by name, so that people who join later can share Expenses.
7. As a Member, I want Member names to be unique within a Group, ignoring case, so that "alice" and "Alice" can't be confused.
8. As a Member, I want an empty name or a name over 50 characters to be rejected, so that the member list stays readable.
9. As a Member who has settled up, I want to leave the Group, so that I'm no longer listed in Balances or Settle-up.
10. As a Member, I want leaving to be refused while my Balance isn't zero, so that nobody can walk away from a debt or forfeit what they're owed.
11. As a Member, I want a Departed Member to stay visible on past Expenses and Payments, so that history stays accurate.
12. As a Member, I want a Departed Member's name to stay reserved, so that a newcomer with the same name is never mistaken for them.
13. As a client, I want removing a Member who doesn't belong to this Group to return "not found", so that Groups can't interfere with each other.

### Expenses

14. As a Member, I want to record an Expense with a Payer, Amount, description and Participants, so that the Group knows who paid for what and who benefited.
15. As a Member, I want to record an Expense on someone else's behalf, so that one person can keep the books for everyone.
16. As a Payer, I want to record an Expense that I'm not a Participant of (for example, buying tickets for two friends), so that I'm not charged a Share of something I didn't use.
17. As a Member, I want an Expense to be split equally among its Participants in whole minor units, so that every Share is an amount someone could actually pay.
18. As a Member, I want each Expense's Shares to add up exactly to its Amount, so that no money appears or disappears.
19. As a Member, I want any Remainder to go one minor unit at a time to Participants in the order they joined the Group, so that splits are predictable and don't depend on how the request was written.
20. As a Member, I want to see each recorded Expense with its computed Shares, so that I can check what I was charged.
21. As a Member, I want to list all of the Group's Expenses, so that I can review the history.
22. As a Member, I want a zero, negative or non-integer Amount to be rejected, so that no Expense is ever ambiguous or nonsensical.
23. As a Member, I want an empty description, or one longer than 200 characters, to be rejected, so that Expenses stay identifiable.
24. As a Member, I want an Expense with no Participants to be rejected, so that every Expense is owed by someone.
25. As a Member, I want an Expense that lists the same Participant twice to be rejected, so that nobody is accidentally charged double.
26. As a Member, I want an Expense whose Payer or Participants aren't current Members of this Group to be rejected, so that strangers and Departed Members can't be charged.
27. As a Member, I want to delete an Expense that was recorded by mistake, so that Balances reflect reality. Changing an Expense means deleting it and recording it again.
28. As a Member, I want deleting an Expense to be refused if it would leave a Departed Member with a non-zero Balance, so that people who left settled stay settled.

### Payments

29. As a Member who owes money, I want to record a Payment I made to another Member, so that our Balances reflect the money that has changed hands.
30. As a Member, I want a Payment to myself to be rejected, so that Balances can't be inflated with meaningless records.
31. As a Member, I want a Payment with a non-positive Amount to be rejected, so that records stay meaningful.
32. As a Member, I want to be allowed to overpay, so that the books still reflect what actually happened. The Balances simply flip.
33. As a Member, I want a Payment involving a Departed Member or a non-Member to be rejected, so that only current Members move money.
34. As a Member, I want to list all of the Group's Payments, so that I can see who has paid whom.
35. As a Member, I want to delete a Payment recorded by mistake, so that Balances are corrected.
36. As a Member, I want deleting a Payment to be refused if it would leave a Departed Member with a non-zero Balance, so that people who left settled stay settled.

### Balances

37. As a Member, I want to see every current Member's Balance, so that I know who is owed and who owes.
38. As a Member, I want a positive Balance to mean "owed money" and a negative one to mean "owes money", so that the sign is never ambiguous.
39. As a Member, I want Members with a zero Balance to be listed too, so that I can see that they are settled.
40. As a Member, I want the Balances to always add up to exactly zero, so that I can trust there are no rounding errors.
41. As a Member, I want Balances to reflect every Expense and Payment, including deletions, so that they're always up to date.

### Settle-up

42. As a Member, I want a Settle-up listing Suggested Transfers (from, to, Amount) that would bring every Balance to zero, so that we know exactly how to square up.
43. As a Member, I want the Settle-up to use the fewest possible transfers, so that we spend as little effort as possible settling.
44. As a Member of a very large Group, I want Settle-up to still return quickly, even if not provably minimal, and to tell me whether the result is optimal, so that I know what I'm getting.
45. As a Member, I want an empty Settle-up when everyone is settled, so that I know there's nothing to do.
46. As a Member, I want the Settle-up for the same Balances to always be the same, so that the advice doesn't change every time I refresh.
47. As a Member, I want each Suggested Transfer to be a positive whole number of minor units, so that it can actually be paid.
48. As a Member, I want Departed Members left out of Settle-up, so that people who have left aren't asked to transfer anything.
49. As a Member, I want recording the Suggested Transfers as Payments to bring every Balance to exactly zero, so that following the advice really does settle the Group.

## Implementation Decisions

- **Stack**: Python with FastAPI and Pydantic for the HTTP layer, pytest (plus Hypothesis for property tests) for testing, and `uv` for project and dependency management. Persistence is SQLite through the standard-library `sqlite3` module with hand-written SQL. There is no ORM.
- **No authentication.** Members belong to one Group and are not global users. Any caller may act on any Group.
- **Money representation (ADR 0002)**: All Amounts are integers in the Currency's minor units, both on the wire and in storage. Floats and decimal strings are never used for money. A Group's Currency is an ISO 4217 code fixed at creation. Only currencies with 2 decimal places are accepted (a fixed allow-list such as EUR, USD, GBP, CHF and similar).
- **Splitting rule (ADR 0002)**: An Expense of Amount A with n Participants gives each Participant ⌊A/n⌋. The Remainder (A mod n) is handed out one minor unit each to the first Participants when they are ordered by when they joined the Group. Shares are calculated from the stored Expense; persisting them is optional, but the API must always return the same Shares for a given Expense.
- **Balance definition**: For each Member, Balance = (sum of Amounts of Expenses they paid) − (sum of their Shares) + (sum of Payments they sent) − (sum of Payments they received). Positive means they are owed money. Every Group's Balances add up to exactly zero, by construction.
- **Settle-up (ADR 0001)**:
  - Settle-up is a pure function: it takes a mapping of Member to non-zero Balance and returns a list of Suggested Transfers plus an `optimal` flag.
  - Up to 16 non-zero Balances, it computes the true minimum number of transfers: it splits the Balances into as many zero-sum subgroups as possible using a dynamic-programming search over subsets, then settles each subgroup with k−1 transfers.
  - Above 16 non-zero Balances, it uses the greedy algorithm (match the largest debtor with the largest creditor) and sets `optimal` to false.
  - The output is deterministic: ties are broken by a stable ordering of Members, such as join order. Transfers are listed in a stable order.
- **Module shape**:
  - A pure **money/splitting** module that computes Shares.
  - A pure **settle-up** module (the test seam described below).
  - A **repository** module that wraps all SQL.
  - A **service** layer that applies the domain rules (membership checks, departure rules, Departed-Member protection on deletes).
  - A thin **HTTP** layer that maps the service to routes and errors to status codes.
  - The app is built by a factory that takes the database location, so tests can inject a temporary database.
- **Schema (conceptual)**:
  - groups (id, name, currency, created_at)
  - members (id, group_id, name, join order, departed_at nullable, created_at). The name is unique per group, ignoring case, including Departed Members.
  - expenses (id, group_id, payer_id, amount, description, created_at)
  - expense_participants (expense_id, member_id)
  - payments (id, group_id, from_id, to_id, amount, created_at)
  - IDs are UUIDs. Timestamps are set by the server.
- **API contract**:
  - `POST /groups` with `{name, currency, members?: [name]}` → 201 with the group and its members.
  - `GET /groups/{id}` → the group and its current (non-departed) members.
  - `POST /groups/{id}/members` with `{name}` → 201 with the member.
  - `DELETE /groups/{id}/members/{member_id}` → 204. Returns 409 if the member's Balance is non-zero.
  - `POST /groups/{id}/expenses` with `{payer_id, amount, description, participant_ids}` → 201 with the expense and its Shares.
  - `GET /groups/{id}/expenses` → a list of expenses, each with its Shares.
  - `DELETE /groups/{id}/expenses/{expense_id}` → 204. Returns 409 if it would leave a Departed Member with a non-zero Balance.
  - `POST /groups/{id}/payments` with `{from_id, to_id, amount}` → 201.
  - `GET /groups/{id}/payments` → a list of payments.
  - `DELETE /groups/{id}/payments/{payment_id}` → 204. The same 409 rule applies as for Expenses.
  - `GET /groups/{id}/balances` → `[{member_id, name, balance}]` for every current Member, including those at zero.
  - `GET /groups/{id}/settle-up` → `{transfers: [{from_id, to_id, amount}], optimal: bool}`.
- **Error mapping**:
  - 404 for an unknown Group, or a Member, Expense or Payment that is unknown or belongs to another Group, when it appears in the URL.
  - 422 for invalid input. This includes unknown, departed or other-group Member IDs in a request body, duplicate Participant IDs, a Payment to oneself, and bad Amounts, descriptions, names or Currencies.
  - 409 for a duplicate Member name, leaving with a non-zero Balance, and deletes that would unsettle a Departed Member.
- **Departed Members**: Leaving sets a departure marker; the Member is never deleted. Departed Members appear in Expense and Payment history. They are excluded from the Group's Member list, Balances and Settle-up, and can't be used in new Expenses or Payments. Departed Members can't rejoin and their names can't be reused.
- **Immutability**: Expenses and Payments can't be edited. They can only be permanently deleted.

## Testing Decisions

- **What a good test is**: it exercises externally observable behaviour through a public seam (HTTP responses, or the settle-up function's inputs and outputs). It never asserts on SQL, internal tables or private helpers, so the internals can be refactored freely.
- **Seam 1, the HTTP API (primary)**: Almost all tests call the FastAPI app in-process with FastAPI's test client, each against a fresh temporary SQLite database supplied by a fixture through the app factory. These tests cover:
  - Group and Member creation, and validation of names and Currencies.
  - Expense validation and Share computation, including how Remainders are allocated (for example, 1000 split 3 ways gives 334/333/333 to the earliest-joined Participants, whatever order the request lists them in).
  - A Payer who is not a Participant.
  - Payments, including overpayment.
  - Balances: the sign convention, zero-balance Members listed, and the sum always equal to zero after any sequence of operations.
  - Deletion of Expenses and Payments.
  - Departure rules and the 409 cases.
  - Isolation between Groups (404s).
  - Settle-up end to end, including that recording the Suggested Transfers as Payments brings every Balance to zero.
  - The over-16 greedy fallback, which reports `optimal: false`.
- **Seam 2, the pure settle-up function (secondary)**: Hypothesis property tests over random integer Balance sets that add up to zero check that:
  - (a) applying the transfers brings every Balance to exactly zero;
  - (b) every transfer is a positive integer between distinct Members;
  - (c) up to 16 non-zero Balances, the number of transfers equals the minimum found by an independent brute-force reference on small inputs, and `optimal` is true;
  - (d) above 16, `optimal` is false and there are at most n−1 transfers;
  - (e) the output is deterministic.

  Hand-written examples cover known cases where greedy is not optimal (for example, Balances that split into two independent zero-sum pairs).
- **Prior art**: none. The repo is greenfield, so these tests set the pattern.

## Out of Scope

- Authentication, authorisation, user accounts, and Members belonging to more than one Group.
- Unequal splits (percentages, fixed Amounts, weights) and itemised Expenses.
- Multiple currencies within a Group, currency conversion, and currencies with 0 or 3 decimal places.
- Editing Expenses or Payments, soft deletes and undo.
- Listing or deleting Groups, and renaming Groups or Members.
- A Departed Member rejoining, and reusing a Departed Member's name.
- Pagination, filtering, search and sorting options.
- Notifications, recurring Expenses, receipts and attachments.
- Any frontend.

## Further Notes

- Domain vocabulary follows `CONTEXT.md`: Group, Member, Departed Member, Currency, Amount, Expense, Payer, Participant, Share, Remainder, Payment, Balance, Settle-up, Suggested Transfer. Code and API naming should use these terms.
- ADR 0001 (exact minimum Settle-up with greedy fallback) and ADR 0002 (integer minor units with a join-order Remainder rule) are binding for this work.
- The 16-member threshold for exact Settle-up is a tunable constant. It is part of the documented behaviour because it determines the `optimal` flag.
