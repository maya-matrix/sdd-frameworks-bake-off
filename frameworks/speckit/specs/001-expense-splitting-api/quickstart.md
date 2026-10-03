# Quickstart: Expense Splitting API

Validation guide proving the feature works end to end. Endpoint and payload details are in
[contracts/openapi.yaml](contracts/openapi.yaml); rules are in [data-model.md](data-model.md).

## Prerequisites

- `uv` installed (Python 3.12 is fetched by `uv` if missing)
- Run all commands from the repository root

## Setup

```bash
uv sync
```

## Run the automated tests (Constitution I)

```bash
uv run pytest
```

Expected: all tests pass, including unit, property-based, API and performance tests.

## Run the service

```bash
uv run uvicorn splitit.main:app --reload
```

Interactive docs: http://127.0.0.1:8000/docs

## Manual validation scenario

1. Create a group → `201`, note `id` as `$G`:
   ```bash
   curl -s -X POST localhost:8000/groups -H 'content-type: application/json' \
     -d '{"name":"Lisbon trip"}'
   ```
2. Add members Ana, Ben, Cleo via `POST /groups/$G/members` → `201` each; note their IDs
   (`$ANA`, `$BEN`, `$CLEO`). Adding "ana" again → `409 duplicate_member_name`.
3. Record "Taxi", `"10.00"`, paid by Ana, participants `[$ANA, $BEN, $CLEO]` via
   `POST /groups/$G/expenses` → `201`; shares are `"3.34"`, `"3.33"`, `"3.33"`.
4. `GET /groups/$G/balances` → Ana `"6.66"`, Ben `"-3.33"`, Cleo `"-3.33"` (sum `0.00`).
5. `GET /groups/$G/settle-up` → two transfers: Ben → Ana `"3.33"`, Cleo → Ana `"3.33"`.
   Calling it again returns the same result and balances are unchanged.
6. Rejections (each `422 validation_error`, nothing stored):
   `"amount": "10.005"`, `"amount": 10.0` (JSON number), `"amount": "0.00"`,
   `"participant_ids": []`, duplicate participant IDs, empty description.
7. Unknown group ID or a payer/participant ID from another group → `404 not_found`.
