# 03: Record and list Expenses with Shares

**What to build:** Any caller can record an Expense in a Group: a Payer, an Amount in integer minor units, a description, and the Participants it's split equally between. They can also list the Group's Expenses. Each Expense comes back with its computed Shares, following ADR 0002:
- Each Participant gets ⌊Amount/n⌋.
- The Remainder goes one minor unit each to the earliest-joined Participants.

**Blocked by:** 01 (Walking skeleton: Groups and Members)

**Status:** done

- [x] `POST /groups/{id}/expenses` with `{payer_id, amount, description, participant_ids}` returns 201 with the Expense (id, payer_id, amount, description, created_at) and its Shares (member_id, amount).
- [x] 1000 split between 3 Participants gives 334/333/333. The 334 goes to the earliest-joined Participant, whatever order `participant_ids` is in.
- [x] Each Expense's Shares always add up exactly to its Amount. Add a Hypothesis test over random Amounts and Participant counts.
- [x] The Payer can be left out of the Participants. They then get no Share.
- [x] 422 for:
  - an Amount that is not a positive integer;
  - a description that is empty or longer than 200 characters;
  - an empty `participant_ids`;
  - duplicate Participant IDs;
  - a Payer or Participant that isn't a Member of this Group.
- [x] An unknown Group returns 404.
- [x] `GET /groups/{id}/expenses` lists the Group's Expenses, each with its Shares, and the same Shares as when the Expense was created.
