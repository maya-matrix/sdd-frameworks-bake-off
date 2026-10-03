## Setup

Terminal:

```bash
mkdir superpowers && cd superpowers && git init

Superpowers uses git worktrees, so the folder needs to be a git repo. Then start your agent and, in  chat:

/plugin install superpowers@claude-plugins-official

All rounds (chat): there are no commands. Paste the prompt as a normal message:

Build a web API for splitting expenses. Users create groups and add members. Any member can record an expense with a payer, amount, description, and the members it's split equally between. Provide an endpoint showing each member's net balance in the group, and a settle-up endpoint suggesting the minimum transfers to clear all debts. Money calculations must be exact, with no rounding errors. Include automated tests.

Then answer its brainstorming questions and approve the design and plan when asked. When it asks how to execute, pick the same option every round, either subagent-driven or inline. Rounds 2 and 3 work the same way with PROMPT 2 and PROMPT 3.