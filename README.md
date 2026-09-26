# ShellHacks 2026: tokenized US stocks on Solana

People outside the US, starting with Argentina, Ukraine and Nigeria, can't easily buy US stocks. This app lets them trade tokenized US stocks on Solana, with a momentum scanner that flags stocks moving on real news and a trade log that shows whether their trading works.

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

| Piece | Owner | State |
| --- | --- | --- |
| Replay clock + prices (`/replay/*`, `/prices`) | Khalil | Working; falls back to placeholder prices until replay bars are loaded |
| Trade log + stats (`/transactions`, `/portfolio`) | Khalil | Working, computed from the ledger |
| Replay data loader (Alpaca bars, Finnhub news) | Matthew | In progress |
| Vault (`/faucet`, `/trade/quote`, `/trade/submit`) | Matthew | Stubs returning fake data in the contract's shape |
| Scanner + `/alerts` | Diego | Stub |
| Frontend | Diego, Justin | Skeleton |
| Mints, vault keypair, `mints.json` | Justin | In progress |

## Run it locally

You need **Python 3.11+** and **Node 20.19+ or 22.12+** (Vite 8 requires one of these).

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload   # http://localhost:8000, API docs at /docs
```

Run a **single worker** (the default above); the replay clock lives in memory. The SQLite file is created at `backend/shellhacks.db` on first start (override with `DB_PATH`).

API keys (Alpaca, Finnhub, Helius) go in `backend/.env`, which is git-ignored. Get them from the team channel; never commit them.

Run the tests:

```bash
cd backend
./venv/bin/pytest -q
```

### Frontend

```bash
cd frontend
cp .env.example .env            # VITE_API_URL=http://localhost:8000
npm install
npm run dev                     # http://localhost:5173
```

### Phantom

Turn on **Testnet Mode** in Phantom (Settings → Developer Settings) so it talks to devnet. Phantom may show our test tokens as "Unknown token"; that's expected.

## Repo layout

```
backend/
  app/
    main.py          FastAPI app, CORS, routers
    config.py        replay date, symbols, units, paths
    db.py            shared SQLite schema
    replay.py        in-memory replay clock
    prices.py        price_at / volume_since (the only source of prices)
    ledger.py        record() and reads of the ledger table
    stats.py         average-cost trade log and portfolio stats
    routers/         one file per owner: replay, alerts, vault, portfolio
  tests/
frontend/            React + Vite app
docs/                build spec, decisions, project notes
```

## Team

- **Khalil Peguero**: backend, trade log and stats, pitch
- **Diego Martinez**: scanner, React frontend
- **Matthew**: vault, replay data
- **Justin Cardenas**: setup scripts, Devpost, slides

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how we branch, review and merge.

## External code

Built fresh for ShellHacks 2026. These two earlier projects were used as reference only; no code was copied:

- [high-momentum-scanner](https://github.com/FastMartini/high-momentum-scanner)
- [quantsim](https://github.com/Kpeguero16/quantsim)

## License

See [`LICENSE`](LICENSE).
