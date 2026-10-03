# 08: Member departure

**What to build:** A Member whose Balance is exactly zero can leave the Group and becomes a Departed Member. The Member is marked as departed but never deleted. A Departed Member:
- still appears in past Expenses and Payments;
- disappears from the Group's Member list, Balances and Settle-up;
- can't be used in new Expenses or Payments.

Their name stays reserved and they can't rejoin. Deletes that would leave a Departed Member with a non-zero Balance are refused.

**Blocked by:** 05 (Payments), 07 (Delete Expenses and Payments)

**Status:** done

- [x] `DELETE /groups/{id}/members/{member_id}` returns 204 when the Member's Balance is 0, and 409 otherwise.
- [x] 404 for an unknown Member, a Member of another Group, or a Member who has already left.
- [x] After leaving, the Member is missing from `GET /groups/{id}`, the Balances and the Settle-up, but still appears in past Expenses (as Payer or Participant) and past Payments.
- [x] Using a Departed Member as Payer, Participant, sender or recipient in a new Expense or Payment returns 422.
- [x] Adding a new Member with a Departed Member's name (ignoring case) returns 409.
- [x] Deleting an Expense or Payment that would leave any Departed Member with a non-zero Balance returns 409, and nothing changes.
- [x] Deletes that don't affect any Departed Member still succeed.
