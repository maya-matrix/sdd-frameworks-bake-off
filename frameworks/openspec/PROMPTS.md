# OpenSpec 

## Setup

Installation:

```bash
npm install -g @fission-ai/openspec@latest
openspec init
```

## AI Instructions
Then start your agent in this folder.

Round 1:
```bash
/opsx:propose Build a web API for splitting expenses. Users create groups and add members. Any member can record an expense with a payer, amount, description, and the members it's split equally between. Provide an endpoint showing each member's net balance in the group, and a settle-up endpoint suggesting the minimum transfers to clear all debts. Money calculations must be exact, with no rounding errors. Include automated tests.
```

Review the generated proposal files, then:
```bash
/opsx:apply
/opsx:archive
/context
```
Round 2:
```bash
/opsx:propose Add unequal splits: an expense can be split by exact amounts or by percentages, in addition to equal splits. Exact amounts must sum to the expense total; percentages must sum to 100. Existing equal-split behavior and the response format of the balances endpoint must not change.
/opsx:apply
/opsx:archive
```

Round 3:
```bash
/opsx:propose After splitting €10.00 between three people, the group's balances don't add up to zero. One cent goes missing.
/opsx:apply
/opsx:archive
```