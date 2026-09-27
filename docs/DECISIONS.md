# Decisions, research and open items

Companion to `BUILD_SPEC.md` (what we're building). This file records **why**, what we researched, and what's still unverified. Last updated Sun Sept 27, 2026. Both Saturday checkpoints passed: the 6:00 PM one (vault test run, scanner on real bars) and the 10:30 PM one (the must-have loop, end to end on devnet). Rows 18–23 were decided during the build.

## Decision log

Settled with the team in a question-by-question review (Sept 25–26). Later decisions override earlier ones.

| # | Topic | Decision | Why / notes |
| --- | --- | --- | --- |
| 1 | Sponsor challenges | Blackstone ("Reimagining the Investor Experience") + MLH Best Use of Solana | One project may enter several challenges; must opt into each on Devpost |
| 2 | What we trade | **Tokenized US stocks on Solana** (option B), not memecoins or on-chain journal only | Gives people outside the US access to US stocks; team sees it as the innovation |
| 3 | Issuer / stock list | **xStocks**, 19 hand-picked names | Ondo doesn't list AKAM, DDOG or ZS, which were Friday's movers |
| 4 | Audience | International users locked out of US markets. Demo persona: **Sofía in Argentina** (hyperinflation). Ukraine and Nigeria mentioned in the pitch | **China and Cuba dropped**: Cuba is under comprehensive US (OFAC) sanctions; Ondo excludes China incl. Hong Kong, Cuba, and occupied Ukrainian regions |
| 5 | User | Both first-time investors and active traders; demo shows Sofía growing from saver to trader | No separate "saver" screen; the pesos → dollars value is told in the pitch |
| 6 | Scanner rules | Large-cap version: RVOL ≥ 2, up ≥ 3%, news catalyst; price and float filters dropped | Large caps rarely hit RVOL 5 or +10% |
| 7 | Backtesting | **Dropped.** Replaced by per-trade and portfolio stats | Simpler; the trade log validates the strategy |
| 8 | Stats | Total P/L ($, %), average win vs. average loss, number of trades, account-value chart (Robinhood-style) | Average cost method, so buys and sells are logged separately |
| 9 | Trades | **Long only**; each buy and sell is its own transaction; P/L via average cost | Short selling would need collateral tracking |
| 10 | AI | **None** | Not needed at MVP level |
| 11 | Execution | Devnet vault with mock tokens; one transaction per swap; vault pays fees; mint/burn so no inventory | **US residents (the team) can't buy real xStocks.** Nobody knows Rust, so no Anchor program |
| 12 | Login | Phantom wallet only | The vault needs the wallet anyway |
| 13 | Codebase | **Fresh build**, Python FastAPI + React | Hackathon rules forbid reusing existing project code; the two reference repos are reference only |
| 14 | Scanner hours | US market hours only, with **Friday Sept 25 replayed** for the demo | Market is closed the whole build window and during judging |
| 15 | Hosting | One laptop, Helius devnet RPC, phone hotspot as backup | Judging is in person |
| 16 | Owners | Khalil: backend, price service, ledger/stats, pitch. Diego: scanner rules + service, React front-end, pitch. Matthew: vault (Solana Python SDK), data loader + replay. Justin (beginner): setup scripts/mints, stock list checks, peso data, Devpost, slides | Team chose to keep this split even after the review flagged Matthew as the critical path |
| 17 | Demo | 3 minutes, order in `BUILD_SPEC.md`; speakers Justin → Khalil → Diego → Khalil → Justin | |
| 18 | Phantom's warning | Keep one transaction with the vault paying; click "Confirm (unsafe)" on stage and explain it | Phantom shows a red "Failed to simulate" warning on every layout we tried (Sept 26 test run, below). Sofía paying her own fee doesn't remove it |
| 19 | Seeded demo trades | `seed_demo.py` pre-runs MSTR (win, +$5.46), AKAM (loss, −$12.42) and an open NVDA position, all before the 9:30 AM open. The live trade is MSFT or DDOG | On the real bars AKAM fades off its Anthropic-news gap, so it can't be the live win. The seeded log ends at −$7.07 total P/L (dry run) |
| 20 | Faucet | Each wallet gets $1,000 once (409 `already_funded` until `/demo/reset`); on stage Khalil points at the seeded deposit instead of clicking (#20) | A second deposit dwarfed the live trade on the account-value chart and halved total P/L % |
| 21 | Retried submits | The backend never trades a quote twice: a repeat returns the same row, waits (`submit_in_progress`), or checks the signature it already sent. The ticket resubmits the same quote for up to 2 minutes after `chain_unavailable`, `submit_in_progress` or a dropped connection, and re-quotes only on `quote_expired` or `tx_failed` (#17, #21, #22) | A lost reply or a devnet hiccup mid-trade must not lose or double a trade. 2 minutes outlasts the quote's blockhash, after which the backend can say for sure whether the trade landed |
| 22 | SQLite access | One connection per thread, WAL mode (#19) | A shared connection made `/portfolio` and `/transactions` return 500 under the UI's 2-second polling |
| 23 | Scanner charts and hours | Chart all 19 supported stocks from Alpaca minute bars; scan 4:00 AM–4:15 PM ET, with visible pre-market/regular/post-market labels | Token prices should remain grounded in their underlying stocks, and pre-market moves matter to momentum traders. The replay still starts at 9:25 AM so seeded demo trades remain visible |

## Independent review (Sept 26) — all applied to the spec

1. **Signing order:** Phantom must sign first; the backend co-signs with `partial_sign` in `/trade/submit`. Signing the other way can trigger Phantom's red "malicious dApp" warning.
2. **AKAM timing:** the Anthropic deal was announced Thursday after the close, so Friday likely gapped up at the open and faded. Script demo trades against the real minute bars; only use news published before each alert.
3. **Data feed:** Alpaca `feed=sip`, not IEX (IEX pre-market starts at 8 AM, and its data is sparse).
4. **Accounting:** the SQLite ledger (deposits and trades) is the source of truth; the chain only executes and verifies.
5. Added: SQLite schema, CORS, single uvicorn worker, `/demo/reset`, `seed_demo.py`, rounding rules, dUSD naming, softened claims ("about a second", tracker certificates, no eligibility claims).

## Research findings

**ShellHacks 2026** ([Devpost](https://shellhacks-2026.devpost.com/), [Hacker Guide](https://conscious-caper-fec.notion.site/ebd//Hacker-Guide-2fb42bb969488004965ee136c468bc12))
- FIU Graham Center, Sept 25–27. Submissions close **Sun Sept 27, 11:00 AM EDT**.
- Judging Sun 1:00–5:00 PM, in person: 3-minute demo, finalists get 3–5 minutes. No video required.
- Devpost needs a GitHub repo link, at least one Discord tag, all teammates as collaborators, challenge opt-ins, and any external code documented. Teams of up to 4.
- Blackstone prize: ~$1,400 total (probably $350 each). MLH Solana prize: a Ledger Nano S Plus each. No Solana mainnet/devnet requirement published.

**Tokenized stocks on Solana**
- xStocks (Backed): Swiss tracker certificates. They give price exposure, not legal share ownership, and exclude US persons. Available through Kraken, Jupiter and others.
- Ondo Global Markets: 260+ stocks/ETFs, the largest issuer on Solana. Excludes the US, UK, EEA, China incl. HK, Cuba, Russia, occupied Ukrainian regions, and others ([eligibility](https://docs.ondo.finance/ondo-global-markets/eligibility)).
- All 15 baseline tickers are on both issuers. AKAM, DDOG and ZS are xStocks-only.
- Real xStocks are Token-2022 tokens with the Scaled UI Amount extension. Our mocks are classic SPL tokens, which is fine to say in the demo.

**Friday Sept 25, 2026 market** (daily data, then checked on the minute bars)
- S&P 500 +0.51%, Nasdaq +0.48%: a quiet day.
- Movers: AKAM +3.2% close after ~+16% intraday (Anthropic $11.6B deal); MSFT +3.7% (Copilot overhaul, Stifel upgrade); DDOG +4.4% (Wedbush initiation); TSLA −1.5%, ~5% off its high (Optimus report); ZS −10.1%, META −3.3%, INTC −3.5%.
- On the minute bars the scanner fires 3 alerts: AKAM at 9:30 AM ($126.80, +14.85%, RVOL 85.8), DDOG at 9:30 AM ($266.97, +3.91%, RVOL 14.7) and MSFT at 9:41 AM ($512.91, +3.01%, RVOL 6.0). AKAM gapped up and faded, as expected.

**Tools and limits**
- Alpaca free tier: SIP history is free if the query ends ≥ 15 minutes ago; 200 requests/min.
- Finnhub free tier: 1 year of company news.
- Helius free tier: about 10 requests/second.
- Devnet faucet: 2 requests every 8 hours.
- `solana` 0.40.3 has `burn`, `mint_to`, `create_idempotent_associated_token_account`; `solders` has `partial_sign`.
- Jupiter's `lite-api` was deprecated Jan 31, 2026; the stretch Jupiter quote needs a key from portal.jup.ag.

## Still unverified — check first

- [x] Friday minute bars produce 3 alerts with the agreed rules: AKAM and DDOG at 9:30 AM, MSFT at 9:41 AM. The seeded trades are scripted (row 19); the live trade's buy and sell minutes (MSFT or DDOG) are still to pick.
- [x] Phantom signs a vault-fee-payer transaction without a warning (the 6 PM checkpoint test run). **No: it shows a red "Failed to simulate the results of this request" and "You don't have enough SOL", then blocks behind "Confirm (unsafe)".** Tested Sept 26 with `backend/scripts/phantom_check.py`. The same warning appears when she pays the fee, and even on a plain burn she signs alone with 0.05 SOL, so it is Phantom's simulator on our devnet tokens, not the layout. Devnet's own `simulateTransaction` passes all three and each lands when confirmed. Decision: keep one transaction with the vault paying; say it in the demo. Also found: Phantom adds its own compute-budget instructions unless the transaction sets them, which broke the quote match, so `chain.swap_message` sets them.
- [x] Phantom devnet display: mints show as "Unknown Token" with a "null" symbol; the fee is shown.
- [ ] Whether xStocks is available in Argentina, Ukraine and Nigeria (don't claim it until checked)
- [ ] SpaceX appears on xStocks per the team, but it has no replayable market data; keep it off the list

## Reference repos (not to be copied)

- [high-momentum-scanner](https://github.com/FastMartini/high-momentum-scanner) (Python): original five filters (RVOL ≥ 5, $2–$20, +10%, float < 20M, news in 24 h), Robinhood + Finnhub providers, generic-headline filter, SQLite storage, dashboard.
- [quantsim](https://github.com/Kpeguero16/quantsim) (Go + React): paper trading, backtester (MA/RSI/MACD), portfolio metrics (Sharpe, drawdown, win rate, profit factor), insights service.
