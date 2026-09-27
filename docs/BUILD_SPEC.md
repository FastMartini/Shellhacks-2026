# ShellHacks 2026 Build Spec

Sep 26, 2026 · @Khalil Peguero

Live doc: https://claude.ai/code/artifact/3854c60f-284b-46e2-8c67-0fd57b3845b7

We let people outside the US — starting with Argentina, Ukraine and Nigeria — buy tokenized US stocks on Solana, with a momentum scanner and a trade log that shows whether their trading works. Code freeze: Sunday Sept 27, 11:00 AM EDT. Judging: Sunday 1–5 PM, live 3-minute demo.

## Product and scope

The demo follows Sofía in Argentina: she moves pesos into digital dollars to escape inflation, buys her first tokenized stock, and grows into an active trader using the scanner and her stats.

- **Sponsor fit.** Blackstone: understand what you own and find opportunities. Solana (MLH Best Use of Solana): every trade is an on-chain swap that confirms in about a second for a fee of a fraction of a cent.
- **Opt into both challenges on Devpost before 11 AM Sunday**, or the project isn't judged for either.
- **Build rule.** Fresh code only. high-momentum-scanner and quantsim are reference, not copied. List them under external code on Devpost.
- **Money.** Demo on Solana devnet with mock stock tokens and a mock dollar token called **dUSD** ("demo dollars"), never named USDC. US residents can't buy real xStocks, so production would route through Jupiter to real xStocks.
- **Claims we can defend.** xStocks are tracker certificates: they follow the stock's price but aren't legal share ownership. Argentina, Ukraine and Nigeria are examples of where demand is; don't claim issuer eligibility for them, which we haven't verified.

**Priority tiers** (cut from the bottom):

| Tier | Features |
| --- | --- |
| Must | Phantom connect, demo-dollars button, buy/sell through the vault, transaction log, total profit/loss |
| Should | Friday replay scanner feed, click an alert to pre-fill the trade ticket, demo reset |
| Nice | Account-value chart, per-stock Alpaca trading charts, average win vs. average loss, trade count |
| Stretch | Live Jupiter quote on a real xStock as price proof (needs a free API key from portal.jup.ag), eligible-country badge, token names and logos in Phantom |

**Out of scope:** AI features, backtesting on price history, short selling, email login, hosting online.

## Architecture

One FastAPI backend and one React app, running on one laptop, talking to Solana devnet through a Helius free-tier RPC. SQLite is the source of truth for prices, news, alerts, deposits and trades; the chain is only used to execute and verify trades.

| Piece | Owner | Tech | Job |
| --- | --- | --- | --- |
| Price service + replay clock | Khalil | Python / FastAPI | The only source of prices. Replay mode serves Friday's 1-minute bars; live mode is future work |
| Replay data loader | Matthew | Python, Alpaca free tier (`feed=sip`) | Downloads Friday Sept 25 1-minute bars, 20 prior daily bars, and Finnhub news for Sept 24–25 into SQLite, once, before the demo |
| Scanner service | Diego | Python | Reads bars from the replay clock and emits alerts; rules live in a config file |
| Vault | Matthew | Python, `solana` 0.40.x / `solders` | Builds unsigned swaps, co-signs after Phantom, submits, pays fees, mints/burns mock tokens |
| Trade log + stats | Khalil | Python / FastAPI, SQLite | Ledger of deposits and trades, average cost, portfolio stats |
| Front-end | Diego (Justin helps) | React + Vite, Solana wallet adapter | Scanner feed, per-stock price/volume charts, trade ticket, transaction log, stats + chart, replay controls |
| Setup | Justin | Python, `scripts/setup_devnet.py` | Created the dUSD mint, 19 stock mints, vault wallet, `mints.json` (done) |

**Flow:** replay clock → scanner → alert card → trade ticket → vault builds an unsigned swap → Sofía signs in Phantom → backend co-signs, submits and confirms → ledger → stats page.

**Defaults**

- The React app (Vite on `:5173`) calls one FastAPI server on `localhost:8000`. Enable CORS for `http://localhost:5173`.
- Run uvicorn with a **single worker**: the replay clock lives in memory.
- All routes live in one server, split by router file per owner.
- **Shared SQLite schema** (agree in the first hour):
    - `bars(symbol, ts, open, high, low, close, volume)`: 1-minute, Friday 4:00 AM–8:00 PM ET
    - `daily_bars(symbol, date, close, volume)`: 20 prior sessions
    - `news(symbol, published_at, headline, url)`
    - `alerts(id, symbol, ts, price, change_pct, rvol, rules_passed, headline, url)`
    - `ledger(id, wallet, ts, kind, symbol, qty_units, price, usd_units, signature)`: `kind` is `deposit`, `buy` or `sell`; amounts in integer base units (1 token = 1,000,000 units)

## Interface contracts

Agree on these shapes in the first hour. Every endpoint ships first as a stub returning fake data in exactly this shape, so the front-end never waits on the backend.

**Conventions**

- The API returns money in USD rounded to 2 decimals and quantities to 6 decimals. SQLite stores both as integer base units (1 token = 1,000,000 units) so nothing drifts.
- `sim_time` = the replay clock's time, ISO 8601 with the Eastern offset, e.g. `2026-09-25T09:47:00-04:00`. Trades are stamped with `sim_time` so the chart lines up with the replay.
- `wallet` = the Phantom public key (base58). It is the user's account; there is no other login.
- Errors: HTTP 4xx with `{"error": "<code>", "message": "<plain words>"}`. The vault also returns 502 and 503, in the same shape, when devnet or its keypair is unavailable (section 3).

### 1. Price service and replay clock (Khalil)

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/replay/state` | `{mode, sim_time, speed, running}` |
| POST | `/replay/control` | body `{action: "start" \| "pause" \| "seek", speed?, to?}` → state |
| POST | `/replay/next-alert` | seeks to the next alert's time and pauses → state |
| GET | `/prices` | `[{symbol, price, prev_close, change_pct, sim_time}]` for all 19 |
| GET | `/prices/{symbol}` | one of the above |
| GET | `/prices/{symbol}/history` | Alpaca minute bars reached by the replay clock: `[{time, open, high, low, close, volume}]` |
| GET | `/scanner` | all 19 stock rows for the current replay minute: price change, RVOL, two live signal states, and sticky news-release state after the stock first reaches 2/2 |

Python code inside the backend calls these instead of HTTP:

- `price_at(symbol, sim_time) -> float`: close of the last bar at or before `sim_time`. Before the first bar of the day it returns the previous session's close; after the last bar it returns the last close.
- `volume_since(symbol, start, sim_time) -> int`: summed bar volume, for the relative-volume rule.

The clock starts **paused at 7:00 AM** and stops itself at 4:15 PM. Alpaca bars remain available from the 4:00 AM pre-market open so signal calculations preserve the full session context. Seeking backwards is for rehearsal only, after `/demo/reset`.

### 2. Alerts (Diego)

`GET /alerts` → alerts whose `time <= sim_time`, newest first:

```json
{"id": "AKAM-0931", "symbol": "AKAM", "time": "2026-09-25T09:31:00-04:00",
 "price": 120.00, "change_pct": 8.7, "rvol": 6.8,
 "rules_passed": ["change", "rvol"],
 "headline": "<a headline published before 9:31>", "headline_url": "https://..."}
```

- The scanner runs over the whole replay day at startup, stores every alert in SQLite, and `/alerts` reveals only the ones the clock has passed.
- `/scanner` always returns every monitored stock at the replay clock's current minute. Values change only when the minute changes, even though the UI polls more frequently.
- An alert requires the two market signals: price at least 3% above the previous close and RVOL at least 2× its session-adjusted average. Company news is context, not a third signal; after both signals first pass, its release state persists even if live momentum or RVOL later falls.
- **At most one alert per stock per day.**
- **No look-ahead:** the news rule and the headline only use news with `published_at` at or before the alert time.

### 3. Vault (Matthew)

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/faucet` | `{wallet}` | `{signature, usd_amount: 1000}`, and a `deposit` ledger row. Once per wallet until `/demo/reset` |
| POST | `/trade/quote` | `{wallet, symbol, side: "buy" \| "sell", usd_amount?, qty?, sell_all?}` | `{quote_id, symbol, side, price, qty, usd_amount, sim_time, expires_in_s: 30, tx_base64}` |
| POST | `/trade/submit` | `{quote_id, signed_tx_base64}` | the transaction row from section 4 |
| POST | `/demo/reset` | `{wallet}` | clears that wallet's ledger rows and resets the clock to 7:00 AM, paused |

- **Signing order:** `tx_base64` is an **unsigned legacy transaction** with the vault as fee payer. Phantom signs first (`signTransaction`), the front-end serializes with `requireAllSignatures: false` and posts it to `/trade/submit`.
- `/trade/submit` checks the message bytes match the quote, adds the vault's signature with `partial_sign`, sends it, waits for `confirmed` (until the quote's blockhash expires, so up to ~90 s), writes the ledger row, and returns it. One call, so a page reload can't lose a trade.
- An expired quote returns `409 quote_expired`; the ticket re-quotes.
- **Retrying a submit never trades twice.** While a quote's submit is running, another returns `409 submit_in_progress`; once it has finished, the same quote returns the same row. After `502 chain_unavailable` the trade may have landed, so submit the same `quote_id` again rather than re-quoting: the backend checks whether it went through.
- **Rounding:** buys burn exactly `usd_amount` and round `qty` down to 6 decimals. `sell_all: true` burns the exact on-chain balance.

**Errors** (the ticket shows `message`):

| Status | Code | When | Ticket |
| --- | --- | --- | --- |
| 400 | `invalid_wallet`, `invalid_amount`, `invalid_transaction`, `tx_mismatch`, `not_signed` | A bad request | Show the message |
| 404 | `unknown_symbol` | Not one of the 19 stocks | Show the message |
| 409 | `insufficient_funds`, `insufficient_shares` | The wallet can't cover the quote | Show the message |
| 409 | `quote_expired` | The quote is over 30 s old, or its trade never landed | Re-quote |
| 409 | `tx_failed` | Devnet rejected the transaction, or it failed on-chain; nothing changed | Re-quote |
| 409 | `submit_in_progress` | The same quote is already being submitted | Wait for that submit |
| 409 | `already_funded` | `/faucet` for a wallet that already has its deposit, or whose faucet is still running | Show the message |
| 502 | `chain_unavailable` | Couldn't reach devnet. On `/trade/submit` the trade may have landed | Submit the same quote again; elsewhere, retry |
| 503 | `vault_not_configured` | No vault keypair on this machine | Setup problem, not the user's |

### 4. Trade log and portfolio (Khalil)

`record(wallet, kind, symbol, qty_units, price, usd_units, sim_time, signature)` is a Python function the vault calls, not an endpoint. Cash, deposits and positions are all computed from the ledger; `/portfolio` makes no chain calls, so polling it every 2 seconds is safe.

`GET /transactions?wallet=` → rows, newest first:

```json
{"id": 3, "sim_time": "2026-09-25T09:45:00-04:00", "symbol": "AKAM", "side": "sell",
 "qty": 2.5, "price": 124.50, "usd_amount": 311.25,
 "cash_before": 700.00, "cash_after": 1011.25,
 "realized_pl": 11.25, "realized_pl_pct": 3.75, "outcome": "win",
 "opened_at": "2026-09-25T09:31:00-04:00", "held_min": 14,
 "signature": "...", "explorer_url": "https://explorer.solana.com/tx/...?cluster=devnet"}
```

On a buy, `realized_pl`, `realized_pl_pct`, `outcome`, `opened_at` and `held_min` are `null`.

`GET /portfolio?wallet=` →

```json
{"cash": 604.85,
 "holdings": [{"symbol": "MSFT", "qty": 0.791922, "avg_cost": 505.10, "price": 516.17,
               "market_value": 408.77, "unrealized_pl": 8.77}],
 "total_value": 1013.62, "deposited": 1000.00,
 "stats": {"total_pl": 13.62, "total_pl_pct": 1.36, "avg_win": 11.25, "avg_loss": -6.40,
           "trade_count": 5, "win_count": 1, "loss_count": 1},
 "equity_curve": [{"t": "2026-09-25T09:30:00-04:00", "value": 1000.00}]}
```

The placeholders add up: deposit $1,000; AKAM $300 buy then sell (+$11.25); TSLA $200 buy then sell (−$6.40); MSFT $400 buy, still held (+$8.77 unrealized). Prices are illustrative until the real bars are in.

## Scanner

The scanner uses real Alpaca bars from 4:00 AM through 4:15 PM ET for complete session calculations; the visible replay starts at 7:00 AM to shorten the demo. On Friday Sept 25, 2026 it still fires 3 alerts: AKAM and DDOG at 9:30 AM, MSFT at 9:41 AM. The thresholds live in `backend/app/config.py`.

| Rule | Reference scanner | This build |
| --- | --- | --- |
| Relative volume | ≥ 5 | ≥ 2: session volume ÷ (20-day average daily volume × share of a 390-minute baseline elapsed); volume resets at 9:30 AM and 4:00 PM so extended-hours volume does not inflate the next session |
| Price move | Up ≥ 10% | Up ≥ 3% from the previous close |
| News catalyst | Within 24 h | Not an alert gate. After both market signals pass, reveal filtered Finnhub company news published in the prior 24 hours |
| Price range | $2–$20 | Dropped (tokens are fractional) |
| Float | < 20M shares | Dropped. Optional replacement: breaks above the pre-market high |

Both market signals must pass for an alert. Long only. One alert per stock per day. Once released, a stock's news stays released for the rest of the forward replay even when its live signal count falls below 2/2. If no qualifying company article exists, the signal remains valid and the UI shows that news is pending instead of inventing a link.

**Stock list (19, all on xStocks):** AAPL, AMD, AMZN, COIN, GOOGL, HOOD, META, MSFT, MSTR, NFLX, NVDA, PLTR, QQQ, SPY, TSLA, plus Friday's movers AKAM, DDOG, INTC, ZS. Mock mints on devnet use the same tickers with a `-demo` suffix (e.g. `AKAMx-demo`). There are 20 total mints because `dUSD` is the twentieth; it is cash, not a stock, and is not scanned.

**Friday's story.** Built from daily data and news timestamps, then checked on the minute bars: AKAM gapped up and faded.

| Stock | Friday | News and timing |
| --- | --- | --- |
| AKAM | Closed +3.2% after trading as much as ~16% higher | Anthropic deal came out **Thursday after the close** (up to 17% after hours). Friday likely gapped up at the open and faded, so the alert fires around 9:30 and a quick win must be checked against real prices |
| MSFT | +3.7% | Copilot overhaul, Stifel upgrade |
| DDOG | +4.4% | Wedbush initiated at Outperform |
| TSLA | Early gain, then ~5% drop from the high | Optimus robot-hand report |

**Demo trades are scripted against the real bars.** `seed_demo.py` pre-runs the non-live ones before the open: MSTR bought at 6:03 and sold at 7:22 (+$5.46), AKAM bought at 6:05 and sold at 8:30 (−$12.42), NVDA bought at 9:10 and held. AKAM only fades, so the live trade is whichever of MSFT or DDOG rises cleanly after its alert; its buy and sell minutes are still to pick.

**Replay data:** Alpaca free tier, 1-minute bars with **`feed=sip`** (the full market; free as long as the query ends at least 15 minutes ago), Friday 4:00 AM–8:00 PM ET, plus 20 prior days of daily bars for the volume baseline. Download once into SQLite; carry the last price forward over any empty minute.

**Scanner chart:** selecting an alert or tracked symbol opens its underlying stock's Alpaca SIP price/volume chart and labels the corresponding `x-demo` token. The chart supports 1-hour, 4-hour and full-session views, never shows bars ahead of the replay clock, and distinguishes pre-market, regular and post-market sessions.

**Replay controls:** starts paused at 7:00 AM; start/pause; speed picker (1×, 10×, 30×, 60×; default 30×); "jump to next alert", which pauses there; "Reset timer" back to 7:00 AM while the wallet has no deposits; the clock stops at 4:15 PM.

## Vault

Every trade is one devnet transaction with both sides in it. **Sofía signs first in Phantom**, then the backend adds the vault's signature, pays the fee and submits, so both sides succeed or fail together. The vault holds the mint authority for dUSD and all 19 stock mints, so it never runs out of inventory.

**Buy** (one legacy transaction, vault is fee payer):

1. Create Sofía's token account for the stock mint if missing (idempotent; the vault pays about 0.002 SOL of rent, visible on the explorer).
2. Burn `usd_amount` of her dUSD (she signs as owner).
3. Mint `qty` of the stock token to her (vault signs as mint authority).

**Sell** is the mirror: burn her stock tokens, mint dUSD to her.

**Faucet:** the vault mints 1,000 dUSD to her wallet and records a `deposit` ledger row. No signature from her, no SOL needed. Each wallet gets it once (until `/demo/reset`): `seed_demo.py` already deposits for the demo wallet, and a second $1,000 would dwarf the live trade on the account-value chart and halve total P/L %.

**Quote → sign → submit**

1. `/trade/quote` prices with `price_at(symbol, sim_time)`, builds an **unsigned** legacy transaction with a fresh blockhash and the vault as fee payer, and stores its message bytes under `quote_id`.
2. The front-end deserializes it, calls the wallet adapter's `signTransaction` (Phantom signs first), serializes with `requireAllSignatures: false`, and posts it to `/trade/submit`.
3. `/trade/submit` checks the message bytes match the quote, adds the vault's signature with `partial_sign`, sends it, waits for `confirmed`, records the ledger row and returns it.

A blockhash expires in about a minute, so quotes expire after 30 seconds and the ticket re-quotes.

**Phantom on devnet** shows the mock tokens as "Unknown token" with a "null" symbol, but it does show the fee (tested Sept 26). Either add token names and logos (Metaplex metadata, a stretch item) or say it in the demo: "these are our test tokens."

**Test run by 6 PM Saturday (Matthew):** one hard-coded buy of 1 `AKAMx-demo` through this exact path (Phantom signs first, backend co-signs and submits) on devnet. Done Sept 26: the buy lands, but Phantom shows a red "Failed to simulate the results of this request" warning. It also says "You don't have enough SOL" and makes her click "Confirm (unsafe)". The same warning appears when Sofía pays her own fee and on a plain burn she signs alone, so that fallback doesn't help. Devnet's own simulation passes all three. Decision: keep one transaction with the vault paying, and explain the warning in the demo.

**Demo wallet and seed data (Matthew):** `scripts/demo_wallet.py` makes the demo wallet (a `solana-keygen`-format key in `backend/keys/`), and `--phantom` prints the key to import into Phantom, so `seed_demo.py` pre-runs the scripted non-live trades with the same key. `seed_demo.py` calls `/demo/reset` and burns her leftover test tokens itself, so rerun it before each rehearsal; `demo_wallet.py --new` makes a fresh keypair.

**Setup checklist (Justin, by 4:45 PM Saturday):**

- [x] Vault keypair, funded with devnet SOL **first thing**; faucet.solana.com allows 2 requests every 8 hours
- [x] dUSD mint + 19 stock mints with `scripts/setup_devnet.py`, 6 decimals, vault as mint authority
- [x] Mint addresses written to one `mints.json` everyone imports
- [ ] Helius free-tier devnet RPC key in `.env` (about 10 requests per second)
- [ ] Phantom with **Testnet Mode** on (Settings → Developer Settings) and the demo wallet imported

## Stats

Everything is computed from the SQLite ledger: every deposit, buy and sell is its own row, and profit and loss use average cost, the same method Robinhood shows.

**Per stock**

- **On a buy:** new average cost = (shares held × old average + shares bought × price) ÷ (shares held + shares bought).
- **On a sell:** realized P/L = (price − average cost) × shares sold. P/L % = (price ÷ average cost − 1) × 100. The average cost doesn't change; it resets when the position reaches zero.
- **Outcome:** a sell with positive P/L is a win, negative is a loss. Buys have no outcome.
- **Held for:** sell rows carry `opened_at` (when the position last went from zero to non-zero) and `held_min`, so the log can show duration.

**Portfolio**

- **Cash** = deposits − buys + sells, from the ledger. `cash_before` and `cash_after` on each row come from the same running total.
- **Total value** = cash + Σ shares × `price_at(symbol, sim_time)`.
- **Total P/L** = total value − total deposits. **P/L %** = total P/L ÷ deposits × 100.
- **Average win / average loss** = mean realized P/L of winning / losing sells.
- **Number of trades** = count of all buys and sells.
- **Account-value chart** = total value at every replay minute from the first deposit up to `sim_time`, replaying the ledger (at most ~390 points). No snapshot job, no chain reads.

**Transaction log columns:** date and time · side (buy or sell; long only) · stock · explorer link · shares · price · value · cash before · cash after · P/L $ · P/L % · outcome · held for.

## Owners and timeline

Coding starts **Saturday 2:45 PM**. That leaves about 11 real build hours before the 9 AM Sunday feature freeze, after 6 hours of sleep and about an hour of meals. Submit on Devpost by 10:30 AM Sunday, not 10:59.

**Scope consequence:** the Nice tier (chart, average win/loss, trade count) only starts after the 10:30 PM checkpoint passes. Stretch items are effectively out.

The critical path runs through Matthew: the bar download and the vault test both gate the 6 PM checkpoint. If either slips, Khalil pairs with him on the vault before touching stats.

| Time (ET) | Khalil | Diego | Matthew | Justin |
| --- | --- | --- | --- | --- |
| Sat 2:45–3:30 | **Everyone:** fund the vault with devnet SOL in the first 10 minutes; agree on this doc's contracts and SQLite schema; create the repo; stub every endpoint with fake data; share `.env` keys (Alpaca, Finnhub, Helius) | | | |
| Sat 3:30–6:00 | FastAPI skeleton with CORS, `price_at` + replay clock (stub by 4:30) | React + Vite scaffold, Phantom connect, scanner rules config | Download Friday SIP bars + news; vault test run (Phantom signs first) | Mints + vault keypair by 4:45, then wallet button and transaction table |
| **Sat 6:00 PM checkpoint** | Vault test run lands (Phantom's devnet warning is expected)? Scanner fires 3–6 alerts on the real bars? Demo trades scripted against real prices? If not, everyone helps fix that first | | | |
| Sat 6:00–6:30 | Dinner | | | |
| Sat 6:30–10:30 | Ledger, average cost, `/transactions`, `/portfolio` | Scanner service + `/alerts`; trade ticket screen | `/faucet`, `/trade/quote`, `/trade/submit` | Front-end help; peso-vs-dollar data for slides |
| **Sat 10:30 PM checkpoint** | Must-have loop works end to end, rough: connect → demo dollars → buy → sell → log → total P/L | | | |
| Sat 10:30 PM–1:00 AM | Ledger part of `/demo/reset`; then chart data and stats if the loop is solid | Scanner feed → pre-filled ticket, replay controls | `seed_demo.py`, `/demo/reset`, expired quotes and failed transactions | Devpost draft, slides |
| Sun 1:00–7:00 AM | Sleep (stagger if someone is mid-fix) | | | |
| Sun 7:00–9:00 | Bug fixes first; stats page and chart only if the must and should tiers are solid | | | |
| **Sun 9:00 AM** | **Feature freeze.** Rehearse the demo 3 times (reset between runs), record a backup screen video, finish Devpost | | | |
| Sun 10:30 | **Submit.** Opt into Blackstone and MLH Best Use of Solana, add all 4 collaborators, repo link, Discord tag | | | |
| Sun 1–5 PM | Judging at your assigned table (posted on Discord) | | | |

## Demo script

Three minutes, three speakers, **one live trade**. Before walking up: run `seed_demo.py`, which calls `/demo/reset`, burns leftover test tokens, puts the non-live trades in her log and leaves the replay paused at 7:00 AM. Then connect the demo wallet and show the pre-market news edge.

| Time | Speaker | On screen | Say |
| --- | --- | --- | --- |
| 0:00–0:20 | Justin | Slide: peso vs. dollar | Sofía in Argentina watched her savings lose value and can't open a US brokerage account |
| 0:20–0:40 | Khalil | Phantom connected; the button reads "$1,000.00 in demo dollars added" (the seeded 6:00 AM deposit, so no click) | Her pesos become digital dollars. The wallet is her account; no signup |
| 0:40–1:40 | Diego | Start the replay, jump to the scripted alert (MSFT or DDOG; AKAM is the seeded loss), buy, click "Confirm (unsafe)" on Phantom's red warning, jump ahead, sell the same way. Open Solana Explorer | The scanner flags momentum with a real catalyst. Phantom warns because it can't simulate our devnet test tokens; we pay the fee, so she needs no SOL. The trade confirmed in about a second, and the fee is a fraction of a cent |
| 1:40–2:20 | Khalil | Stats page with the seeded trades plus the live one, account-value chart | Her log shows what's working: total P/L, average win vs. average loss |
| 2:20–2:40 | Justin | Slide: what's next | Real xStocks through Jupiter, live mode, short selling, more countries |
| 2:40–3:00 | — | Buffer | Questions, or recovery if something breaks |

Say it plainly: *"This is Friday's market, replayed; on a trading day it runs live. Trades are on devnet with our own test tokens, because US residents can't buy xStocks. xStocks track the stock's price; they aren't legal share ownership."*

If the chart or average win/loss (Nice tier) didn't make it, Khalil shows the transaction log and total P/L instead.

## Risks and fallbacks

| Risk | Fallback |
| --- | --- |
| Vault test run fails by 6 PM | Khalil pairs with Matthew. If still stuck by 8 PM: two separate transfers instead of one, with a manual refund button |
| Phantom shows a red "Failed to simulate" warning (it did on every layout in the Sept 26 test) | Keep one transaction with the vault paying; Sofía paying her own fee doesn't remove it. Click "Confirm (unsafe)" and say the demo script's line about it |
| Phantom shows "Unknown token" | Add token metadata (stretch), or say "these are our test tokens" |
| Real bars don't support the AKAM story | Script the live trade on whichever stock rose cleanly after its alert |
| Devnet or RPC slow on stage | Helius key instead of the public RPC; phone hotspot; backup video |
| Vault runs out of devnet SOL | Fund it first thing; faucet allows 2 requests every 8 hours; ask Solana mentors for more |
| Rehearsals pile up trades | Rerun `seed_demo.py` (reset, burn leftovers, rebuild the log), or a fresh keypair with `demo_wallet.py --new` |
| Running out of time | Cut from the bottom of the priority tiers; never cut the must-have loop |

Only add a stock to the list if Alpaca has Friday minute bars for it; pre-IPO tokens like SpaceX have no market data to replay.

This spec was reviewed by an independent agent on Sept 26; the fixes are applied above.

## Sources

- [ShellHacks 2026 Devpost](https://shellhacks-2026.devpost.com/) and the [Hacker Guide](https://conscious-caper-fec.notion.site/ebd//Hacker-Guide-2fb42bb969488004965ee136c468bc12) (deadline, judging, multiple challenges)
- [xStocks products](https://xstocks.fi/us/products) (stock list) and [xStocks legal overview](https://docs.xstocks.fi/docs/product-legal-overview) (tracker certificates, US excluded)
- [Alpaca market data](https://docs.alpaca.markets/docs/about-market-data-api) and [Alpaca data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) (free SIP history older than 15 minutes)
- [Phantom transaction warnings](https://docs.phantom.com/developer-powertools/domain-and-transaction-warnings) (sign with Phantom first) and [Phantom sign and send](https://docs.phantom.com/sdks/browser-sdk/sign-and-send-transaction)
- [Solana fees](https://solana.com/docs/core/fees), [transaction confirmation](https://solana.com/developers/guides/advanced/confirmation), [devnet faucet](https://faucet.solana.com), [Helius plans](https://www.helius.dev/docs/billing/plans)
- [Finnhub company news](https://finnhub.io/docs/api/company-news)
- [Anthropic–Akamai deal](https://techcrunch.com/2026/09/25/anthropic-to-pay-akamai-11-6-billion-over-seven-years-in-cloud-deal/), [Microsoft move](https://www.fool.com/investing/2026/09/25/why-microsoft-stock-is-up-today/), [market recap Sept 25](https://finance.yahoo.com/markets/live/stock-market-today-friday-september-25-dow-sp-500-nasdaq-081738529.html)
- Reference code: [high-momentum-scanner](https://github.com/FastMartini/high-momentum-scanner), [quantsim](https://github.com/Kpeguero16/quantsim)
