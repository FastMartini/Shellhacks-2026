# Contributing

How the four of us work in this repo during ShellHacks 2026. Keep it fast, but keep `main` runnable: that's what we demo from.

## Key times (ET)

| When | What |
| --- | --- |
| Sat 6:00 PM | Checkpoint: vault test run, scanner fires on real bars, demo trades scripted |
| Sat 10:30 PM | Checkpoint: must-have loop works end to end (connect → demo dollars → buy → sell → log → total P/L) |
| Sun 9:00 AM | Feature freeze: bug fixes and rehearsal only |
| Sun 10:30 AM | Submit on Devpost |
| Sun 11:00 AM | Code freeze |

## Before you start

1. Read [`docs/BUILD_SPEC.md`](docs/BUILD_SPEC.md). It's the source of truth for scope, API contracts and the SQLite schema. The live, team-editable version is linked at the top of that file; if the two differ, the live doc wins.
2. Stay inside the priority tiers in the spec. When time runs short, cut from the bottom. Never cut the must-have loop.
3. Set up your machine with the steps in the [README](README.md#run-it-locally).
4. Pick your next task from [`docs/TODO.md`](docs/TODO.md), the running to-do list. Items are grouped by checkpoint and tier, with an owner on each.

## Branches

Branch off `main` (or off a teammate's open branch if you depend on it, and say so in the PR):

| Prefix | For | Example |
| --- | --- | --- |
| `feature/` | New behavior | `feature/trade-ticket` |
| `fix/` | Bug fixes | `fix/quote-expiry` |
| `chore/` | Setup, tooling, moving files | `chore/mints-script` |
| `docs/` | Docs only | `docs/readme-contributing` |

Keep branches small and short-lived. Rebase on or merge `main` before opening a PR so it merges cleanly.

## Where your code goes

The backend is one FastAPI app, with one router file per owner:

| Area | Owner | Files |
| --- | --- | --- |
| Replay clock, prices | Khalil | `backend/app/replay.py`, `prices.py`, `routers/replay.py` |
| Ledger, stats | Khalil | `backend/app/ledger.py`, `stats.py`, `routers/portfolio.py` |
| Alerts, scanner | Diego | `backend/app/routers/alerts.py` (+ scanner module and rules config) |
| Vault, replay data loader | Matthew | `backend/app/routers/vault.py` (+ vault and loader modules) |
| Frontend | Diego, Justin | `frontend/` |

Rules that keep the pieces fitting together:

- **Use the shared schema.** Write bars, news and alerts into the tables in `backend/app/db.py` through `db.get()`. Don't create a separate database or ORM models.
- **Get prices from `prices.price_at` / `volume_since`**, never from your own query or an HTTP call to our own server.
- **The vault writes trades with `ledger.record(...)`** and returns `stats.transaction(ledger.rows(wallet), row_id)` from `/trade/submit`.
- **Money:** SQLite stores integer base units (1 token = 1,000,000 units); the API returns USD rounded to 2 decimals and quantities to 6.
- **Time:** use the replay clock's `sim_time` (ISO 8601 with the Eastern offset), not wall-clock time.
- **Errors:** return HTTP 4xx with `{"error": "<code>", "message": "<plain words>"}` by raising `ApiError`.

## Changing a contract

If an endpoint's request or response shape, or the schema, has to change:

1. Update **both** copies of the spec: `docs/BUILD_SPEC.md` and the live doc.
2. Say so in the PR description.
3. Tell whoever consumes it (usually Diego for the frontend) in the team chat.

## Commits

- Short, imperative subject lines: "Add stats.transaction lookup", "Fix quote expiry check".
- One logical change per commit where you can.
- **No AI attribution:** no `Co-Authored-By` trailers for AI tools, and no "Generated with …" lines in commits, PRs, comments or docs.

## Never commit

- `.env` files or API keys (Alpaca, Finnhub, Helius). Commit `.env.example` with placeholder values instead.
- Solana keypairs: the vault and demo wallet keys control the mints. `mints.json` holds only public addresses and **is** committed.
- `*.db` files, `venv/`, `node_modules/`, `__pycache__/`. The root `.gitignore` already covers these; check `git status` before you commit.

## Pull requests

1. Run the checks for what you touched:
   - Backend: `cd backend && ./venv/bin/pytest -q`
   - Frontend: `cd frontend && npm run lint && npm run build`
2. Open a PR into `main` with:
   - **What** changed and why
   - **How you tested it**
   - **Follow-ups**, if anything is stubbed or waiting on someone else
   - The matching [`docs/TODO.md`](docs/TODO.md) change: check off what you finished (add the PR number) and add any follow-ups as new items
3. Request a review from the owner of any code you touched. Tag them if it blocks them.
4. Merge once it's approved and checks pass. Near a checkpoint, a quick "looks good" from anyone is enough; don't block on reviews.
5. Delete the branch after merging.

## Ground rules

- **Fresh code only.** high-momentum-scanner and quantsim are for reference; don't copy from them.
- **Ship stubs first.** Every endpoint starts as a stub returning fake data in exactly the contract's shape, so the frontend never waits on the backend.
- **Stuck for more than 20 minutes?** Say so in the team chat. The critical path runs through the vault and the replay data, so everyone helps there first.
