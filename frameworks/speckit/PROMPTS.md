## Setup

Installation:

```bash
uv tool install specify-cli
specify init . --integration claude
cd splitit-speckit
```
## AI Instructions
Then start your agent in this folder.

Round 1:
```bash
/speckit-constitution Every behavior has automated tests. Money calculations must be exact.
/speckit-specify Build a web API for splitting expenses. Users create groups and add members. Any member can record an expense with a payer, amount, description, and the members it's split equally between. Provide an endpoint showing each member's net balance in the group, and a settle-up endpoint suggesting the minimum transfers to clear all debts. Money calculations must be exact, with no rounding errors. Include automated tests.
/speckit-plan
/speckit-tasks
/speckit-implement
/speckit-converge
```

/speckit-plan is normally where you'd name a tech stack. Leave it empty and let the agent propose one. Repeat /speckit-implement and /speckit-converge until it reports Converged.

Round 2:
```bash
/speckit-specify Add unequal splits: an expense can be split by exact amounts or by percentages, in addition to equal splits. Exact amounts must sum to the expense total; percentages must sum to 100. Existing equal-split behavior and the response format of the balances endpoint must not change.
/speckit-clarify
/speckit-plan
/speckit-tasks
/speckit-analyze
/speckit-implement
/speckit-converge
```

Round 3
Terminal, in the project folder:

```bash
specify extension add bug
```

Then chat (keep the quotes around the prompt):
```bash
/speckit-bug-assess "Before Round 3, plant the bug by hand in every project. Edit the equal-split code so any leftover cents are dropped instead of distributed, so €10.00 split three ways becomes 3.33 + 3.33 + 3.33. Then start a fresh agent session." slug=split-rounding
/speckit-bug-fix slug=split-rounding
/speckit-bug-test slug=split-rounding
```

Some agents spell the commands /speckit.specify and so on instead of /speckit-specify.