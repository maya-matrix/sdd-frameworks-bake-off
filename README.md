# SDD Frameworks Bake-off

Each spec-driven development (SDD) framework got the same prompt and built the same app: an expense-splitting web API. The baseline is a plain agent session with no framework.

> Build a web API for splitting expenses. Users create groups and add members. Any member can record an expense with a payer, amount, description, and the members it's split equally between. Provide an endpoint showing each member's net balance in the group, and a settle-up endpoint suggesting the minimum transfers to clear all debts. Money calculations must be exact, with no rounding errors. Include automated tests.

Each framework folder has the generated project, a `PROMPTS.md` with the exact setup and commands used, and the asciinema recording(s) of the session.

## Comparison

All numbers are for Round 1 (build the API from the prompt above).

### Workflow and output

| Framework | Folder | Workflow | Spec artifacts produced | Stack the agent chose | Storage |
|---|---|---|---|---|---|
| **Baseline** (no framework) | [`baseline`](frameworks/baseline) | Single prompt | None | Node.js 20, no dependencies, `node:test` | In-memory |
| **Spec Kit** | [`speckit`](frameworks/speckit) | `/speckit-constitution` → `specify` → `plan` → `tasks` → `implement` → `converge` | Constitution, `specs/001-…/` (spec, research, data model, plan, tasks, contracts, checklists) | Python, FastAPI, Hypothesis | In-memory |
| **OpenSpec** | [`openspec`](frameworks/openspec) | `/opsx:propose` → `apply` → `archive` | `openspec/specs/` (3 capabilities), archived change proposals | TypeScript, Fastify, Vitest | In-memory |
| **OpenSPDD** | [`openspdd`](frameworks/openspdd) | `/spdd-analysis` → `spdd-generate` (REASONS canvas in between) | `spdd/analysis/`, `spdd/prompt/` (REASONS canvas) | TypeScript, Fastify, Vitest | In-memory |
| **Superpowers** | [`superpowers`](frameworks/superpowers) | Plain prompt; brainstorm → approve design → approve plan → execute | `docs/superpowers/specs/`, `docs/superpowers/plans/` | Python, FastAPI, SQLAlchemy | SQLite |
| **Addy Osmani agent-skills** | [`addy`](frameworks/addy) | `/spec-driven-development` → `/agent-skills:build auto` → `/agent-skills:review` | `SPEC.md`, `tasks/plan.md`, `tasks/todo.md` | Python, FastAPI, mypy strict, ruff | SQLite |
| **Matt Pocock skills** | [`pocock`](frameworks/pocock) | `/grill-with-docs` (Q&A) → `/to-spec` → `/to-tickets` → `/implement` | `CONTEXT.md` glossary, `docs/specs/`, `docs/adr/` (2 ADRs) | Python, FastAPI, mypy | SQLite |

### Effort and size

| Framework | Questions asked¹ | Approval checkpoints² | Context tokens at end³ | Messages tokens³ | Recording | Source LOC⁴ | Test LOC⁴ | Test cases⁵ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Baseline** | 0 | 0 | 73k | 47.1k | 4m 53s | 423 (329) | 422 (351) | 24 |
| **Spec Kit** | 0 | 0 | 184.9k | 159k | 15m 39s | 629 (466) | 990 (744) | 83 |
| **OpenSpec** | 0 (+1 process) | 0 | 138.4k | 112.5k | 11m 54s | 684 (564) | 1035 (911) | 75 |
| **OpenSPDD** | 0 | 0 | 144.4k | 118.5k | 11m 14s | 806 (660) | 626 (548) | 39 |
| **Superpowers** | 3 | 3 | 163.7k⁶ | 137.1k | 22m 13s | 584 (441) | 598 (453) | 55 |
| **Addy Osmani agent-skills** | 6 (+1 process) | 3 | 209.9k | 183.7k | 28m 28s | 780 (618) | 1059 (700) | 93 |
| **Matt Pocock skills** | 19 | 3 | 163.1k⁶ | 137.2k | 30m 21s | 777 (626) | 976 (661) | 74 |

1. **Questions asked:** design or requirements questions the agent asked before or while building, counted from the recordings.
   - Pocock asked 18 numbered questions while grilling (Q1–Q18), plus 1 during `/to-spec`.
   - Addy asked 5 while writing the spec (auth, storage, settle-up, leftover cents, stack), plus 1 follow-up about JSON field naming.
   - Superpowers asked 3: stack, storage and settle-up algorithm.
   - "Process" questions are about tooling, not the app. OpenSpec asked whether to sync delta specs before archiving. Addy asked how to handle git commits.
   - Spec Kit, OpenSPDD and Baseline asked nothing. You only type the next command.
2. **Approval checkpoints:** points where the agent stopped and waited for a go-ahead.
   - Superpowers: design, written spec, execution mode.
   - Addy: spec, plan, which review findings to fix.
   - Pocock: ticket breakdown, start implementing, which review findings to fix.
3. **Tokens:** read from the `/context` command run at the end of each recording, on `claude-opus-5-5` with a 1M context window. This is the size of the main conversation, not total billed usage. About 26k of it is fixed overhead (system prompt, tools, skills). "Messages" is the part that comes from the session itself.
4. **LOC:** physical lines in git-tracked `.py`/`.ts`/`.js` files under `src/` or `app/` (source) and `tests/` or `test/` (tests). The number in brackets leaves out blank lines and comments. OpenSpec is measured at its Round 1 commit (`721b7de`). With Round 2 (unequal splits) it is 922 (755) source and 1527 (1362) test.
5. **Test cases:** a grep for `def test_` / `it(` / `test(`. Parametrised and property-based tests count once, so this is a rough measure. OpenSpec has 103 after Round 2.
6. These sessions also ran review subagents, whose tokens are not in `/context`. Superpowers ran 1 final branch reviewer, which showed about 39k output tokens. Pocock ran 2 background standards reviewers.

### Cost and time

| Framework | Cost | vs Baseline | API time | Wall time | Lines added / removed⁷ | Output tokens⁸ | Cache read⁸ | Cache write⁸ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Baseline** | $1.12 | 1.0× | 3m 59s | 5m 33s | 954 / 0 | 28.5k | 741.4k | 49.8k |
| **Spec Kit** | $4.30 | 3.8× | 12m 43s | 15m 9s | 1711 / 112 | 83.4k | 6.8m | 159.1k |
| **OpenSpec** | $3.05 | 2.7× | 8m 57s | 11m 12s | 2281 / 2 | 61.4k | 4.6m | 113.3k |
| **OpenSPDD** | $2.60 | 2.3× | 8m 16s | 11m 13s | 2119 / 7 | 60.0k | 2.3m | 118.3k |
| **Superpowers** | $5.06 | 4.5× | 14m 30s | 20m 51s | 1846 / 0 | 94.9k | 8.2m | 203.4k |
| **Addy Osmani agent-skills** | $6.55 | 5.8× | 18m 30s | 28m 22s | 1129 / 89 | 116.1k | 12.8m | 219.9k |
| **Matt Pocock skills** | $5.86 | 5.2× | 15m 52s | 30m 21s | 971 / 0 | 97.8k | 10.6m | 255.5k |

Read from Claude Code's session summary at the end of each Round 1 session (raw output in [`COSTS.MD`](COSTS.MD)). Token columns are for `claude-opus-5-5`, which accounts for almost all of the cost. Some sessions also made a tiny `claude-haiku-4-5` call costing about $0.001.

7. **Lines added / removed:** Claude Code's count of every line the agent wrote, including specs, plans and docs. That's why it is higher than the LOC columns above, which only count source and test code.
8. **Token columns:** unlike the context and messages tokens above, which are a snapshot of the conversation at the end, these are totals across every API call in the session.
   - **Output:** everything the model generated (text, tool calls, thinking). Output is the most expensive kind of token.
   - **Cache read:** the agent re-sends the whole conversation on every turn, and the part it already sent comes from the prompt cache at about a tenth of the input price. It grows with the number of turns × conversation size. Addy ended with about 3× Baseline's context but read about 17× as many cached tokens.
   - **Cache write:** new content (replies, tool results) stored in the cache the first time it appears. It costs a little more than normal input.

OpenSpec Round 2 (unequal splits, [`openspec-2.cast`](frameworks/openspec/openspec-2.cast)) was a fresh session. It asked 2 design questions (how to round percentage splits, request shape) and 1 process question. It ended at 139.1k context tokens, 113.2k of them messages, and took 8m 58s.

### Common ground

All seven projects got the core money rules right in the same way:

- Amounts travel as decimal **strings** (`"10.00"`), and JSON numbers are rejected.
- Internally, all arithmetic uses integer cents.
- Leftover cents from an equal split go to the first participants. €10.00 split three ways is 3.34 / 3.33 / 3.33.
- Balances always sum to exactly zero.
- Settle-up is solved exactly (subset DP) for small groups and falls back to a greedy plan above about 16–20 non-zero balances.

### Notable differences

- **Scope added beyond the prompt:**
  - Baseline added users and `X-User-Id` caller identity.
  - Pocock added payments, deleting expenses and member departure.
  - Addy and Superpowers added a group currency.
  - OpenSpec added percentage and exact-amount splits in Round 2.
- **Cost:** every framework cost 2.3–5.8× the baseline. OpenSPDD ($2.60) and OpenSpec ($3.05) were the cheapest. The three that stop for questions and approvals (Superpowers, Pocock, Addy) were the most expensive, at $5–6.50, and also took the longest wall time.
- **Persistence:** Addy, Pocock and Superpowers chose SQLite. The others keep data in memory.
- **Human involvement:** Pocock (`/grill-with-docs`) and Superpowers (brainstorming) ask the most questions up front. OpenSpec and Spec Kit expect you to review the generated artifacts between steps.

## Recordings

### Baseline
[![asciicast](https://asciinema.org/a/PuK3kanHhE91ttFd.svg)](https://asciinema.org/a/PuK3kanHhE91ttFd)

### Spec Kit

[![asciicast](https://asciinema.org/a/IEsEMWjsGPCA4ACN.svg)](https://asciinema.org/a/IEsEMWjsGPCA4ACN)

### OpenSpec

Round 1: build the API

[![asciicast](https://asciinema.org/a/vuy0HzrkZurEpMRA.svg)](https://asciinema.org/a/vuy0HzrkZurEpMRA)
### OpenSPDD

[![asciicast](https://asciinema.org/a/sjU8hH0q7QO2K4mK.svg)](https://asciinema.org/a/sjU8hH0q7QO2K4mK)

### Superpowers

[![asciicast](https://asciinema.org/a/HG6DW8VuuCFOirPF.svg)](https://asciinema.org/a/HG6DW8VuuCFOirPF)

### Addy Osmani agent-skills

[![asciicast](https://asciinema.org/a/YfzUNcaemmJlsyQD.svg)](https://asciinema.org/a/YfzUNcaemmJlsyQD)

### Matt Pocock skills

[![asciicast](https://asciinema.org/a/V63pEEmpHOdKYUNl.svg)](https://asciinema.org/a/V63pEEmpHOdKYUNl)
