# SPDD Analysis: Splitit — Group Expense Splitting Web API

## Original Business Requirement

Build a web API for splitting expenses. Users create groups and add members. Any member can record an expense with a payer, amount, description, and the members it's split equally between. Provide an endpoint showing each member's net balance in the group, and a settle-up endpoint suggesting the minimum transfers to clear all debts. Money calculations must be exact, with no rounding errors. Include automated tests.

## Domain Concept Identification

### Existing Concepts (from codebase)
- None. The project is greenfield: the repository has no commits and contains only this requirement, SPDD command definitions, and a terminal recording — no build file, source code, schema, or prior SPDD prompts/analyses. All concepts below are new, and there are no existing conventions to inherit.

### New Concepts Required
- **Group**: the container and consistency boundary for shared expenses — owns its members, its expenses, and therefore all balances and settlement suggestions. Balances never cross group boundaries.
- **Member**: a participant within a group — can be a payer, a participant in a split, and the subject of a balance. Identity is group-scoped unless a global User concept is introduced (see ambiguities).
- **User** (optional / to be decided): a person who "creates groups". The requirement says "users create groups and add members", which may imply a global identity distinct from group membership. Recommended to model minimally (or collapse into Member) since no authentication is required.
- **Expense**: a record that one member (payer) paid an amount on behalf of a set of members (participants), with a description. Immutable fact from which balances are derived.
- **Share (Split allocation)**: the portion of an expense owed by each participant. Derived from the expense via equal splitting; must sum exactly to the expense amount.
- **Money**: a value object representing an exact monetary amount in a single currency. Central to the "no rounding errors" requirement.
- **Net Balance**: per-member derived value — total paid minus total owed within the group. Positive = owed money (creditor), negative = owes money (debtor). Computed, not stored.
- **Transfer (Settlement Suggestion)**: a suggested payment "from debtor → to creditor, amount". Computed on demand from balances; not persisted.

### Conceptual Relationships
- Group 1 —— * Member; Group 1 —— * Expense.
- Expense * —— 1 Member (payer); Expense * —— * Member (participants), realized through Shares.
- Net Balance is a pure function of a group's Expenses (and Shares).
- Settlement Suggestions are a pure function of Net Balances.
- Lifecycle: Group must exist before Members; Members must exist before they can appear in an Expense. Balances and Transfers have no lifecycle of their own — always derived.

### Key Business Rules
- **Exact money**: all amounts are represented in integer minor units (e.g., cents) or an exact decimal type; never binary floating point. Governs Money, Expense, Share, Balance, Transfer.
- **Split conservation**: the sum of an expense's shares equals the expense amount exactly. When the amount is not evenly divisible, leftover minor units are distributed deterministically (e.g., one extra cent to the first *k* participants in a stable order). Governs Expense, Share.
- **Zero-sum balances**: the sum of all net balances in a group is exactly zero at all times. Governs Net Balance.
- **Settlement completeness**: applying all suggested transfers brings every member's balance to exactly zero. Governs Transfer.
- **Membership integrity**: payer and all participants of an expense must be members of the same group. Governs Expense, Member, Group.
- **Positive amounts**: expense amount must be strictly positive, and expressed with no more precision than the currency's minor unit (e.g., ≤ 2 decimal places). Governs Expense, Money.
- **Non-empty split**: an expense must be split among at least one participant; duplicate participants are not allowed. Governs Expense.
- **Payer need not be a participant** (implicit): a member may pay for others without consuming a share. Governs Expense.
- **Recorder is a member** (implicit, from "any member can record"): the recording actor must belong to the group — only enforceable if a caller identity exists. Governs Expense, Member.
- **Single currency per group** (implicit): the requirement never mentions currency; mixing currencies would make balances meaningless. Governs Group, Money.

## Strategic Approach

### Solution Direction
- Build a small, layered HTTP JSON API: **HTTP routing/validation layer → application service layer → pure domain layer (money, splitting, balance, settlement algorithms) → repository/persistence layer**.
- Keep all money arithmetic and algorithms in **pure, framework-free domain functions** so they can be exhaustively unit-tested (including property-based tests for invariants), with a thinner set of API-level integration tests over the endpoints.
- Data flow: create group → add members → record expenses (persisted as facts with their computed shares) → balances computed on read by aggregating shares and payments → settle-up computed on read from balances.
- Resource-oriented REST surface nested under groups (groups, members, expenses, balances, settlements).

### Key Design Decisions
- **Tech stack**: Node.js 24 + TypeScript (modern, available locally, strong test tooling) vs. Go (available, strong typing, but more boilerplate for a small API) vs. Python 3.9 (outdated system interpreter). → Locally available toolchains are Node.js 24, Go, and Python 3.9 (no Java/.NET). **Recommend TypeScript on Node.js** with a lightweight HTTP framework and a mainstream test runner; to be confirmed.
- **Money representation**: integer minor units (simple, fast, exact; requires conversion at API boundary) vs. arbitrary-precision decimal library (natural input format, extra dependency) vs. floats (rejected — violates requirement). → **Recommend integer minor units internally** (with BigInt or safe-integer bounds check), with a clearly defined API wire format (see next decision).
- **API wire format for amounts**: decimal string (e.g., "12.34" — human-friendly, avoids JSON float parsing) vs. integer cents (unambiguous, less friendly) vs. JSON number (risk of float coercion). → **Recommend decimal string on input and output**, parsed strictly into minor units; reject anything with excess precision.
- **Remainder allocation in equal splits**: give extra cents to first participants in request order vs. a stable sort order (e.g., member id) vs. to the payer. → **Recommend deterministic order by participant order as submitted (or member id)**, documented and tested; exact choice fixed in REASONS Canvas.
- **Balances: stored vs. derived**: maintain running balances (fast reads, risk of drift) vs. compute from expenses on each request (always correct, O(expenses)). → **Recommend derived on read** — correctness over performance at this scale.
- **Settle-up algorithm**: true minimum number of transfers is NP-hard (reducible to partitioning balances into the maximum number of zero-sum subsets) vs. greedy largest-debtor-to-largest-creditor (≤ n−1 transfers, fast, not always minimal). → **Recommend an exact minimal algorithm for small groups** (exhaustive/DP over zero-sum subsets, feasible up to roughly 15–20 non-zero balances) **with greedy fallback beyond a size threshold**, OR explicitly accept greedy as "minimum" — requires stakeholder confirmation (see ambiguities). Output must be deterministic.
- **Persistence**: in-memory store (simplest, data lost on restart, ideal for tests) vs. embedded SQL database (durable, adds migrations) vs. external DB (overkill). → **Recommend a repository abstraction with an in-memory implementation** for the initial scope; durable storage is a swap-in if required.
- **Identity / authentication**: none (caller passes acting member id or nothing) vs. real auth. → **Recommend no authentication**; "any member can record" is enforced as "payer and participants must be group members", optionally with an explicit `recorded by` member reference.
- **User vs. Member**: global Users who join groups vs. group-scoped Members (names only). → **Recommend group-scoped Members** for minimal scope; a global User concept adds no value without auth.

### Alternatives Considered
- **Floating-point money with rounding at display**: rejected — directly violates "exact, with no rounding errors" and breaks zero-sum invariants.
- **Persisting balances / ledger entries per pair of members (debt graph)**: rejected — more state to keep consistent; balances are cheaply derivable.
- **Greedy-only settlement presented as optimal**: rejected as the silent default — it can produce more transfers than necessary (e.g., balances {+6, +4, +3, −7, −6}: largest-to-largest greedy emits 4 transfers, while the optimum is 3 — {+6→−6} and {+4, +3 → −7}), contradicting "minimum transfers".
- **Full CRUD (edit/delete expenses, remove members) in initial scope**: deferred — not requested; noted as a gap.

## Risk & Gap Analysis

### Requirement Ambiguities
- **"Minimum transfers"**: strictly minimal (NP-hard, exact for small groups) or "reasonably few" (greedy)? Needs explicit decision; impacts algorithm, performance limits, and tests.
- **Users vs. members**: is a "user" a global account distinct from group membership? Do members need any identity beyond a name? Are member names unique within a group?
- **Who records expenses**: must the API know the recording member (an actor), or is "any member can record" simply "no permission restrictions"?
- **Currency**: single implicit currency? Per-group currency? Which minor unit (2 decimals vs. 0 for JPY)?
- **Amount input format**: decimal string, integer cents, or JSON number?
- **Remainder rule**: who absorbs the extra cent(s) when a split doesn't divide evenly?
- **Settle-up semantics**: suggestion only (read-only), or can transfers be recorded as settlement payments that change balances? Requirement says "suggesting", implying read-only — but without recorded payments, balances can never actually be cleared in the system.
- **Persistence durability**: must data survive restarts?
- **Mutation scope**: can expenses be edited/deleted, and can members be removed or groups deleted?
- **Balance endpoint shape**: should it include members with zero balance, and in what order?

### Edge Cases
- **Indivisible split** (e.g., 10.00 among 3): shares must be 3.34/3.33/3.33 and sum exactly to 10.00.
- **Amount smaller than participant count** (e.g., 0.02 among 3): some shares are zero — allowed or rejected?
- **Payer not among participants**: payer's balance increases by full amount.
- **Payer is the only participant**: expense has no net effect on balances — allowed?
- **Duplicate participants** in the split list: reject or deduplicate.
- **Participant/payer from another group or nonexistent**: must be rejected with a clear error.
- **Zero, negative, or over-precise amounts** (e.g., "1.005"): reject.
- **Very large amounts / many expenses**: integer overflow risk if using bounded numbers; use BigInt or enforce a maximum.
- **Group with no expenses / all balances zero**: balances all zero; settle-up returns an empty list.
- **Two members with equal and opposite balances**: exactly one transfer.
- **Large groups** (> ~20 non-zero balances) with exact-minimum algorithm: exponential blow-up; needs a bound or fallback.
- **Non-existent group** on any endpoint: 404 behavior.
- **Duplicate member names** in a group: ambiguous display in balances/transfers.

### Technical Risks
- **Exact-minimum settlement complexity**: exponential worst case → mitigate with a group-size threshold and greedy fallback, or cap members per group; document behavior.
- **Float leakage at the JSON boundary**: JSON numbers parsed as IEEE-754 doubles → mitigate with string-encoded amounts and strict parsing/validation.
- **Integer overflow**: JavaScript numbers lose precision above 2^53 minor units → mitigate with BigInt or a validated maximum amount.
- **Non-deterministic outputs** (remainder allocation, transfer ordering) make tests flaky and responses confusing → mitigate with explicit stable ordering rules.
- **Concurrency**: concurrent expense recording against an in-memory store is safe in single-threaded Node, but a future durable store would need transactional writes per expense.
- **Greenfield setup cost**: no scaffolding, lint, or test harness exists; project bootstrap must be part of the first operations.

### Acceptance Criteria Coverage

The requirement contains no formal ACs; the following are derived one-to-one from its explicit statements.

| AC# | Description | Addressable? | Gaps/Notes |
|-----|-------------|--------------|------------|
| 1 | Users can create groups | Yes | "User" identity undefined; recommend no auth and group-scoped members |
| 2 | Users can add members to a group | Yes | Name uniqueness and member removal unspecified |
| 3 | Any member can record an expense with payer, amount, description, and participants | Yes | Recorder identity optional; payer/participants must be group members; amount format to be fixed |
| 4 | Expense is split equally between the selected members | Yes | Remainder-allocation rule must be decided; zero-share case to be decided |
| 5 | Endpoint shows each member's net balance in the group | Yes | Sign convention, ordering, and inclusion of zero balances to be fixed |
| 6 | Settle-up endpoint suggests the minimum transfers to clear all debts | Partial | Strict minimality is NP-hard; needs decision on exact vs. greedy and size limits; read-only vs. recordable settlements unclear |
| 7 | Money calculations are exact, with no rounding errors | Yes | Achieved via integer minor units and string wire format; single-currency assumption |
| 8 | Automated tests are included | Yes | Recommend unit + property-based tests for domain invariants and API integration tests; no test harness exists yet |
