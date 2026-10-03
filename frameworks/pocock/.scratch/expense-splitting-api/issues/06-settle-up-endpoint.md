# 06: Settle-up endpoint

**What to build:** A caller can ask for a Group's Settle-up: the fewest Suggested Transfers that would clear every Balance. It uses the algorithm from ticket 02 on the Group's current non-zero Balances, with Member join order as the stable ordering.

**Blocked by:** 02 (Settle-up algorithm), 05 (Payments)

**Status:** ready-for-agent

- [ ] `GET /groups/{id}/settle-up` returns `{transfers: [{from_id, to_id, amount}], optimal}`.
- [ ] A settled Group, or one with no Expenses, returns an empty `transfers` list with `optimal: true`.
- [ ] End to end: record several Expenses, take the Settle-up, record each Suggested Transfer as a Payment, and every Balance comes out at exactly 0.
- [ ] A scenario where greedy is not optimal, built from real Expenses, returns the minimum number of transfers.
- [ ] A Group with more than 16 Members holding non-zero Balances returns `optimal: false`, and its transfers still clear every Balance.
- [ ] The same state always gives identical output.
- [ ] An unknown Group returns 404.
