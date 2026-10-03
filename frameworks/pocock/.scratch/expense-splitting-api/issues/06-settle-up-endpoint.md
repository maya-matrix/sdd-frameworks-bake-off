# 06: Settle-up endpoint

**What to build:** A caller can ask for a Group's Settle-up: the fewest Suggested Transfers that would clear every Balance. It uses the algorithm from ticket 02 on the Group's current non-zero Balances, with Member join order as the stable ordering.

**Blocked by:** 02 (Settle-up algorithm), 05 (Payments)

**Status:** done

- [x] `GET /groups/{id}/settle-up` returns `{transfers: [{from_id, to_id, amount}], optimal}`.
- [x] A settled Group, or one with no Expenses, returns an empty `transfers` list with `optimal: true`.
- [x] End to end: record several Expenses, take the Settle-up, record each Suggested Transfer as a Payment, and every Balance comes out at exactly 0.
- [x] A scenario where greedy is not optimal, built from real Expenses, returns the minimum number of transfers.
- [x] A Group with more than 16 Members holding non-zero Balances returns `optimal: false`, and its transfers still clear every Balance.
- [x] The same state always gives identical output.
- [x] An unknown Group returns 404.
