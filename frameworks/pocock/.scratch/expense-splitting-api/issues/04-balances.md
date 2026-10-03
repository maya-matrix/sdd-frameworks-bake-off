# 04: Balances

**What to build:** A caller can see each current Member's Balance in a Group. Balance = paid − Shares owed. Payments are added in ticket 05. A positive Balance means the Member is owed money.

**Blocked by:** 03 (Record and list Expenses with Shares)

**Status:** done

- [x] `GET /groups/{id}/balances` returns `[{member_id, name, balance}]` for every current Member, in join order, including Members at zero.
- [x] Example: A pays 1000 split between A, B and C. A's Balance is +666, B's is −333 and C's is −333.
- [x] A Payer who isn't a Participant is credited with the full Amount.
- [x] Hypothesis/integration property: after any random sequence of Expenses, the Balances add up to exactly zero.
- [x] A new Group with no Expenses shows every Member at 0. An unknown Group returns 404.
