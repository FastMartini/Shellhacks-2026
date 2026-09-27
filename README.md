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
| Scanner + `/scanner` + `/alerts` | Diego | Monitors every supported stock each replay minute from the 7:00 AM replay start through 4:15 PM ET; news is released for the rest of the replay after momentum first passes. Alerts still require both momentum and RVOL. The real data produces AKAM and DDOG at 9:30 AM and MSFT at 9:41 AM |
| Frontend | Diego, Justin | Working: momentum monitor (all-stock signals, ten-minute news updates, line/candlestick Alpaca charts, replay controls, trade ticket through Phantom) and dashboard (account value, average win/loss, account-value chart, holdings, trade log) |
| Mints, vault keypair, `mints.json` | Justin | Done on devnet with `scripts/setup_devnet.py` (#9) |
| Demo seed (`seed_demo.py`) | Matthew | Working; pre-runs the non-live demo trades with the demo wallet |

## Run it locally

This section takes you from a fresh clone (or a fork) to making a trade in the browser. Run the steps in order. Each one ends with a check, so you know it worked before you move on. Commands are for macOS and Linux; Windows equivalents are noted where they differ.

There are two ways to set up, and they differ only in step 4:

- **Teammate:** you use the team's shared keys and devnet tokens. Get `backend/.env` values and `vault-keypair.json` from the team channel.
- **Fork (anyone else):** you make your own free accounts and your own devnet tokens. Nothing in this repo depends on the team's keys.

### 1. What you need

| Tool | Version | Check with |
| --- | --- | --- |
| Python | 3.11 or newer | `python3 --version` |
| Node.js | 20.19+ or 22.12+ (Vite 8 won't start on older versions) | `node -v` |
| Git | any | `git --version` |
| [Phantom](https://phantom.com/download) browser extension | latest | Chrome, Brave, Edge or Firefox |

Accounts and keys (all free; teammates get the values from the team channel instead):

| Key | Used for | Where to get it |
| --- | --- | --- |
| `ALPACA_API_KEY`, `ALPACA_API_SECRET` | Downloading Friday's minute bars, once | [app.alpaca.markets](https://app.alpaca.markets) → sign up → API keys. The free plan is enough. |
| `FINNHUB_API_KEY` | Downloading Friday's news, once | [finnhub.io/dashboard](https://finnhub.io/dashboard) |
| Helius devnet RPC URL | Every faucet call and trade | [dashboard.helius.dev](https://dashboard.helius.dev) → free plan → copy the **devnet** URL: `https://devnet.helius-rpc.com/?api-key=<key>`. Optional but strongly recommended: the public `https://api.devnet.solana.com` works but rate-limits, which makes trades slow or fail. |

The Alpaca and Finnhub keys are only used by the one-off data download in step 5. The running app never calls them.

### 2. Get the code

```bash
git clone https://github.com/FastMartini/Shellhacks-2026.git   # or your fork's URL
cd Shellhacks-2026
```

### 3. Backend: install and configure

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt     # Windows: venv\Scripts\pip install -r requirements.txt
cp .env.example .env                            # Windows: copy .env.example .env
```

Every backend command in this README calls `./venv/bin/...` directly, so you don't need to activate the venv. If you'd rather activate it (`source venv/bin/activate`, or `venv\Scripts\activate` on Windows), drop the `./venv/bin/` prefix.

Open `backend/.env` and fill it in:

```ini
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
FINNHUB_API_KEY=...
SOLANA_RPC_URL=https://devnet.helius-rpc.com/?api-key=...
```

- The host must be **`devnet`**.helius-rpc.com. Helius shows a mainnet URL first, and the same key works on both, so it's easy to copy the wrong one. Our tokens only exist on devnet, so with a mainnet URL the faucet and every trade fail.
- Don't leave `SOLANA_RPC_URL` blank. A blank value overrides the default. If you have no Helius key, keep the `.env.example` default.
- `.env` is git-ignored. Never commit it.

**Check:** `./venv/bin/pytest -q` should end with `passed` and no failures. The tests use a temporary database and don't touch the network, so they pass before any of the next steps.

### 4. Vault keypair and devnet tokens

The **vault** is a Solana keypair that the backend holds. It's the mint authority for `dUSD` (demo dollars) and for every stock token, and it pays every transaction fee, so users' wallets never need SOL. `backend/mints.json` lists the token addresses and is committed. The keypair at `backend/keys/vault-keypair.json` is secret and git-ignored.

**The keypair and `mints.json` must match.** If the vault isn't the mint authority for the tokens in `mints.json`, the "Get 1,000 demo dollars" button and every trade fail.

#### 4a. Teammate: use the shared vault

1. Save the `vault-keypair.json` from the team channel as `backend/keys/vault-keypair.json`. Create the `keys/` folder if it doesn't exist.
2. Keep the committed `mints.json` as it is.
3. **Don't run `scripts/setup_devnet.py`.** It would make a new keypair that doesn't control the committed tokens.

#### 4b. Fork: create your own vault and tokens

The committed `mints.json` points at the team's tokens, which your new vault can't mint. Remove it first: `setup_devnet` skips any token already listed there, so it would otherwise create nothing.

```bash
rm mints.json                                   # Windows: del mints.json
./venv/bin/python -m scripts.setup_devnet
```

This script:

1. Creates `keys/vault-keypair.json` and prints the vault address.
2. Airdrops 2 devnet SOL to the vault.
3. Creates `dUSD` and one token per stock, then writes their addresses to a new `mints.json`.

**If the airdrop fails** (devnet rate-limits airdrops), open [faucet.solana.com](https://faucet.solana.com), paste the printed vault address, choose devnet, request SOL, and run the script again. It's safe to re-run: it only creates what's missing and resumes where it stopped.

Commit your new `mints.json` to your fork; it contains only public addresses. If other people work on your fork, send them `vault-keypair.json` privately, and they follow step 4a.

**Check (both paths):** print the vault address and look it up on the Solana explorer:

```bash
./venv/bin/python -c "from app import chain; print(chain.vault().pubkey())"
```

Open `https://explorer.solana.com/address/<that address>?cluster=devnet`. It should show a SOL balance above 0. Creating the tokens uses about 0.03 SOL. After that, each faucet call and trade costs a small fee, plus a one-time ~0.002 SOL the first time a wallet receives each token. If the balance runs low, top it up at faucet.solana.com.

### 5. Load the replay data (once)

The replay is Friday, Sept 25, 2026. This downloads that day's minute bars, the 20 prior daily bars and the company news for 19 symbols into `backend/shellhacks.db`:

```bash
./venv/bin/python -m app.load_replay
```

**Check:** it prints `Loaded … minute bars, … daily bars and … headlines for 19 symbols.` If it fails, nothing is written and the error names the cause, usually a missing or wrong key in `.env`. Fix it and run the command again; re-running is always safe.

Without this step the app still starts, but it shows placeholder prices, empty charts and no scanner alerts.

### 6. Start the backend

```bash
./venv/bin/uvicorn app.main:app --reload
```

Leave it running in its own terminal.

**Check:** http://localhost:8000/docs shows the API docs, and `curl localhost:8000/replay/state` returns something like `{"mode":"replay","sim_time":"2026-09-25T07:00:00-04:00","speed":30,"running":false}`.

- Run **one worker** (the default). The replay clock and open trade quotes are kept in memory, so more than one worker breaks them.
- **Restart uvicorn after editing `.env` or re-running `load_replay`.** `--reload` only watches `.py` files, and the scanner computes alerts at startup. A restart also resets the replay clock to 7:00 AM.
- The database is created at `backend/shellhacks.db`. Set `DB_PATH` in `.env` to put it somewhere else.

### 7. Frontend: install, configure and start

In a second terminal:

```bash
cd frontend
cp .env.example .env                            # Windows: copy .env.example .env
npm install
npm run dev
```

Set `frontend/.env` to:

```ini
VITE_API_URL=http://localhost:8000
VITE_SOLANA_RPC_URL=https://devnet.helius-rpc.com/?api-key=...   # the same URL as SOLANA_RPC_URL
```

Vite reads `.env` only when it starts, so restart `npm run dev` after editing it.

**Check:** open http://localhost:5173. The terminal must say `Local: http://localhost:5173/`. If it shows **5174** or another port, something else was already using 5173. The backend only accepts requests from port 5173, so every API call would fail. Stop the other process (see [Stopping and restarting](#stopping-and-restarting)) and start Vite again.

### 8. Set up Phantom and make a first trade

1. Install Phantom and create a wallet, or import one. The wallet needs no SOL.
2. Turn on **Testnet Mode**: Settings → Developer Settings → Testnet Mode, then pick **Solana Devnet**.
3. In the app, click **Select Wallet** (top right), choose Phantom and approve. Your wallet address is your account; there's no signup.
4. Open **Dashboard** and click **Get 1,000 demo dollars**. After a few seconds it confirms, and your total account value shows $1,000.
5. Open **Scanner** and click **Start replay** so prices move. Pick a stock, enter a dUSD amount and click **Buy <symbol>**. Phantom opens to sign. It shows a red "Failed to simulate" warning; click **Confirm (unsafe)**. Phantom can't simulate our devnet test tokens, and the trade still lands.
6. Switch the ticket to **Sell** and sell some or all of it the same way, then open **Dashboard** to see the trade log, win/loss stats and total P/L.

Phantom may list our tokens as "Unknown token". That's expected for devnet test tokens.

### Stopping and restarting

Stop either server with **Ctrl+C** in its terminal. If a terminal was closed and a server is still running in the background, find and stop it by port:

```bash
lsof -nP -iTCP:8000 -iTCP:5173 -sTCP:LISTEN     # shows the PID holding each port
kill <PID>
```

On Windows: `netstat -ano | findstr ":8000 :5173"`, then `taskkill /PID <PID> /F`.

To restart everything, stop both servers and then run step 6 and step 7's `npm run dev` again. Setup steps 3–5 only need to be redone if you change keys or want fresh data.

### Resetting a wallet

Each wallet can use the faucet **once**. After that, the button is disabled and reads "$1,000 in demo dollars added". To start that wallet over, with an empty trade log, the faucet available again and the clock back at 7:00 AM, reset it with the backend running:

```bash
curl -X POST localhost:8000/demo/reset -H 'Content-Type: application/json' -d '{"wallet":"<wallet address>"}'
```

Then reload the page. The reset clears the wallet's rows in the local database only. Tokens already minted on devnet stay in the wallet, so Phantom's balances can run ahead of the app's; the app's numbers come from the database. `scripts.seed_demo` (see [Demo prep](#demo-prep)) resets and also burns leftover tokens.

Each machine has its own `shellhacks.db`, so a wallet funded on one teammate's machine is still unfunded on another.

### Troubleshooting

**"Get 1,000 demo dollars" doesn't work**

| What you see | Cause | Fix |
| --- | --- | --- |
| Button reads "Connect wallet first" or stays greyed out | The wallet isn't connected, or its portfolio hasn't loaded yet | Connect in Phantom and wait a second. If it stays grey, check that the backend is running (step 6). |
| Button reads "$1,000 in demo dollars added" and is disabled | This wallet already used the faucet in this machine's database | [Reset the wallet](#resetting-a-wallet), or connect a different wallet |
| "No vault keypair: get keys/vault-keypair.json…" | `backend/keys/vault-keypair.json` is missing | Step 4a (teammate) or 4b (fork) |
| "Devnet rejected the transaction: …" | The keypair doesn't match `mints.json` (for example after running `setup_devnet` with the team's `mints.json`), the RPC URL points at mainnet, or the vault is out of SOL | Teammate: restore the shared keypair and run `git checkout backend/mints.json`. Fork: redo step 4b. Check that the URL host is `devnet.helius-rpc.com`, and check the vault's balance (step 4's check). Restart uvicorn after any change. |
| "Couldn't reach Solana devnet; try again" | Bad RPC URL, a rate limit on the public RPC, or devnet is slow | Use a Helius devnet URL in `backend/.env`, restart uvicorn and try again |
| "The faucet transaction expired before it landed; try again" | Devnet was congested | Click again. Nothing was minted, so you won't be funded twice. |
| "Failed to fetch" or nothing happens | The backend isn't running, `VITE_API_URL` is wrong, or Vite isn't on port 5173 (CORS) | Steps 6 and 7. Look at the browser console (F12) for the exact error. |

**Trades**

| What you see | Cause | Fix |
| --- | --- | --- |
| Phantom's red "Failed to simulate" warning | Phantom can't simulate our devnet test tokens | Click **Confirm (unsafe)**. The trade still lands. |
| Phantom errors on the wrong network, or balances don't appear | Testnet Mode is off | Step 8.2 |
| Quote expired | A quote is valid for 30 seconds | Submit again; the app re-quotes |
| "Lost touch with Solana devnet mid-trade…" | Devnet stopped answering after the trade was sent | Submit again. The backend checks whether the first one landed before it sends anything, so it never trades twice. |
| Buy button reads "Get demo dollars first" | The wallet has no dUSD in the app's ledger | Use the faucet first |

**Data and servers**

| What you see | Cause | Fix |
| --- | --- | --- |
| Flat placeholder prices, empty charts, no alerts | Replay data isn't loaded | Step 5, then restart uvicorn |
| New alerts missing after `load_replay` | The scanner only runs at startup | Restart uvicorn |
| `.env` change has no effect | Neither server reloads `.env` | Restart uvicorn or `npm run dev` |
| `Address already in use` on 8000, or Vite on 5174 | An old server is still running | [Stopping and restarting](#stopping-and-restarting) |
| `load_replay` fails with HTTP 401 or 403 | Wrong or missing Alpaca or Finnhub key | Fix `backend/.env` and run it again |
| Vite fails with a Node version error | Node is older than 20.19 | Install Node 22 LTS, delete `frontend/node_modules`, run `npm install` again |
| `ModuleNotFoundError` in the backend | Packages were installed outside the venv, or the venv was made with a different Python | Recreate it: `rm -rf venv`, then step 3 |

### Making your own changes

- **Checks before you commit:** backend `cd backend && ./venv/bin/pytest -q`; frontend `cd frontend && npm run lint && npm run build`.
- **Where things live:** see [Repo layout](#repo-layout) below. Settings are in `backend/app/config.py`: the replay date, the symbol list, scanner thresholds and the allowed frontend origins. The faucet amount is `FAUCET_USD` in `backend/app/routers/vault.py`.
- **Adding a stock:** add it to `SYMBOLS` (and `NEWS_IDENTITY_TERMS`) in `config.py`. Then run `./venv/bin/python -m scripts.setup_devnet`, which creates only the new token. It needs the same vault keypair that created the existing tokens. Then run `./venv/bin/python -m app.load_replay` and restart uvicorn.
- **Replaying a different day:** change `REPLAY_DATE` in `config.py`, run `load_replay` again and restart uvicorn. The Sept 25 run times in the demo script and the scanner results in the Status table won't apply to another day.
- **Running the frontend on another port or host:** add that origin to `FRONTEND_ORIGINS` in `config.py`, or the backend will block its requests.
- **API shapes and the database schema** are defined in [`docs/BUILD_SPEC.md`](docs/BUILD_SPEC.md). If you change one, update the spec in the same change.
- How the team branches, reviews and merges is in [`CONTRIBUTING.md`](CONTRIBUTING.md).

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
