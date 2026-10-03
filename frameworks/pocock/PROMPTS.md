## Setup
Terminal:

```bash
mkdir pocock && cd pocock && git init
```

Start your agent, then in chat:
```bash
/plugin install mattpocock-skills
```

Round 1 (chat):

```bash
/grill-with-docs Build a web API for splitting expenses. Users create groups and add members. Any member can record an expense with a payer, amount, description, and the members it's split equally between. Provide an endpoint showing each member's net balance in the group, and a settle-up endpoint suggesting the minimum transfers to clear all debts. Money calculations must be exact, with no rounding errors. Include automated tests.
```

Answer its questions until it stops asking, then:
```bash
/to-spec
/to-tickets
/implement
```

`/to-spec` and `/to-tickets` take no text, because they summarise the conversation so far.