# ShellHacks 2026: tokenized US stocks on Solana

People outside the US can't easily buy US stocks. This app lets them trade tokenized US stocks on Solana, with a momentum scanner that flags stocks moving on real news and a trade log that shows whether their trading works.

For the demo, the market is **Friday Sept 25, 2026, replayed minute by minute**, and every trade is a real Solana **devnet** transaction using our own test tokens: `dUSD` ("demo dollars") and one mock token per stock (e.g. `AKAMx-demo`). US residents can't buy real xStocks, so production would route through Jupiter to real xStocks. xStocks track a stock's price; they aren't legal share ownership.

Entered in **Blackstone** and **MLH Best Use of Solana**.

## How it works

```
replay clock → scanner → alert card → trade ticket → vault builds an unsigned swap
  → user signs in Phantom → backend co-signs, submits, confirms → ledger → stats page
```

- **Backend:** one FastAPI server (`backend/`) on `localhost:8000`. SQLite is the source of truth for prices, news, alerts, deposits and trades; the chain is only used to execute and verify trades.
- **Frontend:** React + Vite (`frontend/`) on `localhost:5173`, with Phantom as the wallet. The wallet's public key is the account; there's no signup.

The full design (scope, API contracts, SQLite schema, scanner rules, vault flow, stats math, demo script) is in [`docs/BUILD_SPEC.md`](docs/BUILD_SPEC.md). The reasoning behind it is in [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Status

The must-have loop works end to end on devnet with Phantom (connect → demo dollars → buy → sell → log → total P/L); it passed the 10:30 PM checkpoint on Saturday. What's left is in [`docs/TODO.md`](docs/TODO.md).

| Piece | Owner | State |
| --- | --- | --- |
| Replay clock + prices (`/replay/*`, `/prices`) | Khalil | Working; serves quotes and chart history from Alpaca bars, with placeholder quotes until replay bars are loaded |
| Trade log + stats (`/transactions`, `/portfolio`) | Khalil | Working, computed from the ledger |
| Replay data loader (Alpaca bars, Finnhub news) | Matthew | Working; loads 19 symbols atomically into SQLite |
| Vault (`/faucet`, `/trade/quote`, `/trade/submit`, `/demo/reset`) | Matthew | Working on devnet. The faucet funds each wallet once; a retried submit never trades twice |
| Scanner + `/scanner` + `/alerts` | Diego | Monitors every supported stock each replay minute from the 7:00 AM replay start through 4:15 PM ET; news is released permanently for the replay after momentum and RVOL first pass. The real data produces AKAM and DDOG at 9:30 AM and MSFT at 9:41 AM |
| Frontend | Diego, Justin | Working: scanner (all-stock signal monitor, gated news links, Alpaca price/volume charts, replay controls, trade ticket through Phantom) and dashboard (account value, stats, account-value chart, holdings, trade log). Average win vs. average loss isn't shown yet |
| Mints, vault keypair, `mints.json` | Justin | Done on devnet with `scripts/setup_devnet.py` (#9) |
| Demo seed (`seed_demo.py`) | Matthew | Working; pre-runs the non-live demo trades with the demo wallet |

## Run it locally

You need **Python 3.11+** and **Node 20.19+ or 22.12+** (Vite 8 requires one of these).

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in the keys
python -m app.load_replay       # Friday's bars and news into SQLite, once
uvicorn app.main:app --reload   # http://localhost:8000, API docs at /docs
```

Before the first run:

- **Keys:** API keys (Alpaca, Finnhub) and the Helius devnet URL go in `backend/.env`, which is git-ignored. Get them from the team channel; never commit them.
- **Vault keypair:** put the shared `vault-keypair.json` from the team channel at `backend/keys/vault-keypair.json` (git-ignored). It's the mint authority for every token in `mints.json`. Don't run `scripts/setup_devnet.py` unless you're starting over with new mints.

Run a **single worker** (the default above); the replay clock and open quotes live in memory. The SQLite file is created at `backend/shellhacks.db` on first start (override with `DB_PATH`). The scanner computes alerts at startup, so restart uvicorn after `load_replay`.

Run the tests:

```bash
cd backend
./venv/bin/pytest -q
```

### Frontend

```bash
cd frontend
cp .env.example .env            # VITE_API_URL, and VITE_SOLANA_RPC_URL (the same Helius URL as the backend)
npm install
npm run dev                     # http://localhost:5173
```

### Phantom

Turn on **Testnet Mode** in Phantom (Settings → Developer Settings) so it talks to devnet. Phantom may show our test tokens as "Unknown token"; that's expected. It also shows a red "Failed to simulate" warning on every trade: click "Confirm (unsafe)". It can't simulate our devnet test tokens, and the trade still lands.

### Demo prep

From `backend/`, with the API running:

```bash
./venv/bin/python -m scripts.demo_wallet --phantom   # the demo wallet; import the printed key into Phantom
./venv/bin/python -m scripts.seed_demo               # reset, burn leftovers, pre-run the non-live trades
```

`seed_demo.py` leaves the replay paused at 7:00 AM, ready to show how early news gives pre-market traders an edge before the live trade. `--dry-run` prices the script from SQLite without touching the chain. The full run sheet is the demo script in [`docs/BUILD_SPEC.md`](docs/BUILD_SPEC.md#demo-script).

## Repo layout

```
backend/
  app/
    main.py          FastAPI app, CORS, routers
    config.py        replay date, symbols, scanner thresholds, units, paths
    db.py            shared SQLite schema
    replay.py        in-memory replay clock
    prices.py        price_at / volume_since (the only source of prices)
    scanner.py       momentum rules over the replay day
    load_replay.py   one-off Alpaca + Finnhub download into SQLite
    chain.py         devnet side of the vault: swap transactions, send and confirm
    ledger.py        record() and reads of the ledger table
    stats.py         average-cost trade log and portfolio stats
    routers/         one file per owner: replay, alerts, vault, portfolio
  scripts/           setup_devnet, demo_wallet, seed_demo, plus the vault test run and Phantom check
  tests/
  mints.json         devnet mint addresses (public, committed)
  keys/              vault and demo wallet keypairs (git-ignored)
frontend/
  src/App.tsx        scanner, trade ticket, dashboard
  src/api/           API client, types, trade submit with retries
  src/components/    account-value chart, stat cards, transaction table
docs/                build spec, decisions, to-do list, project notes
```

## Team

- **Khalil Peguero**: backend, trade log and stats, pitch
- **Diego Martinez**: scanner, React frontend
- **Matthew**: vault, replay data
- **Justin Cardenas**: setup scripts, Devpost, slides

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how we branch, review and merge.

## License

See [`LICENSE`](LICENSE).
