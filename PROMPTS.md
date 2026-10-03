
## PROMPT 1 (build from scratch)
```
Build a web API for splitting expenses. Users create groups and add members. Any member can record an expense with a payer, amount, description, and the members it's split equally between. Provide an endpoint showing each member's net balance in the group, and a settle-up endpoint suggesting the minimum transfers to clear all debts. Money calculations must be exact, with no rounding errors. Include automated tests.
```

## PROMPT 2 (add a feature)
```
Add unequal splits: an expense can be split by exact amounts or by percentages, in addition to equal splits. Exact amounts must sum to the expense total; percentages must sum to 100. Existing equal-split behavior and the response format of the balances endpoint must not change.
```

## PROMPT 3 (bug report)
Before Round 3, plant the bug by hand in every project. Edit the equal-split code so any leftover cents are dropped instead of distributed, so €10.00 split three ways becomes 3.33 + 3.33 + 3.33. Then start a fresh agent session.
```
After splitting €10.00 between three people, the group's balances don't add up to zero. One cent goes missing.
```

