## Setup
Terminal:

```bash
mkdir addy && cd addy && git init
```

Start your agent, then in chat:
```bash
/plugin marketplace add addyosmani/agent-skills
/plugin install agent-skills@addy-agent-skills
```

Round 1 (chat):

```bash
/spec-driven-development Build a web API for splitting expenses. Users create groups and add members. Any member can record an expense with a payer, amount, description, and the members it's split equally between. Provide an endpoint showing each member's net balance in the group, and a settle-up endpoint suggesting the minimum transfers to clear all debts. Money calculations must be exact, with no rounding errors. Include automated tests.
/agent-skills:build auto
/agent-skills:review
```
