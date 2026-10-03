# 01: Walking skeleton: Groups and Members

**What to build:** Set up the project: `uv`, FastAPI, pytest and Hypothesis, an app factory that takes the SQLite database location, the schema from the spec (`docs/specs/0001-expense-splitting-api.md`), and a pytest fixture that gives each test a fresh temporary database through the factory. With that in place, a caller can:
- create a Group with a name, a Currency and an optional list of initial Member names;
- fetch the Group with its current Members;
- add a Member to it.

Use the vocabulary in `CONTEXT.md`.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] `POST /groups` with `{name, currency, members?}` returns 201 with the Group (UUID id, name, currency, created_at) and its Members (id, name).
- [x] The Currency must be an ISO 4217 code on the 2-decimal allow-list (e.g. EUR, USD, GBP, CHF). Anything else returns 422.
- [x] `GET /groups/{id}` returns the Group and its current Members in join order. An unknown id returns 404.
- [x] `POST /groups/{id}/members` with `{name}` returns 201 with the Member. An unknown Group returns 404.
- [x] Member names must be 1–50 characters (otherwise 422) and unique within the Group, ignoring case (409 if taken). The uniqueness rule also applies among the initial Members passed to `POST /groups`.
- [x] Join order is recorded for each Member, ready for the Remainder rule in later tickets.
- [x] All tests go through the HTTP test client against a temporary database. No test touches SQL directly.
