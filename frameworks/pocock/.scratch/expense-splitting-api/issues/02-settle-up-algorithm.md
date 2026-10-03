# 02: Settle-up algorithm (pure function)

**What to build:** A pure function that takes a mapping of Member to non-zero integer Balance (adding up to zero). It returns the Suggested Transfers (from, to, Amount) that bring every Balance to zero, plus an `optimal` flag, following ADR 0001.
- Up to 16 non-zero Balances: compute the true minimum number of transfers. Partition the Balances into the largest possible number of zero-sum subgroups using a dynamic-programming search over subsets, then settle each subgroup of size k with k−1 transfers. Set `optimal` to true.
- Above 16: use the greedy algorithm (match the largest debtor with the largest creditor) and set `optimal` to false.

The output must be deterministic for the same input. Break ties by a caller-supplied stable Member ordering, such as join order.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] With an empty input or all-zero Balances, it returns no transfers and `optimal` is true.
- [ ] Hypothesis property: applying the returned transfers brings every Balance to exactly zero.
- [ ] Hypothesis property: every transfer is a positive integer Amount between two distinct Members.
- [ ] Hypothesis property: for up to about 8 non-zero Balances, the number of transfers equals the minimum found by an independent brute-force reference written in the test suite.
- [ ] Hypothesis property: above 16 non-zero Balances, `optimal` is false and there are at most n−1 transfers.
- [ ] Hypothesis property: calling it twice on the same input gives identical output.
- [ ] A hand-written case where greedy is not optimal returns the true minimum (e.g. Balances {A:+5, B:+3, C:−5, D:−3} → 2 transfers).
- [ ] A 16-Balance input completes quickly enough for a test suite (well under a second).
