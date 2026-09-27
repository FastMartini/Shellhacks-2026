# Running to-do list

What's left before the Sunday 10:30 AM submission, in the order it has to happen. Scope and contracts live in [`BUILD_SPEC.md`](BUILD_SPEC.md); this file only tracks who is doing what next.

Last updated: Sat Sept 26, 11:25 PM ET. **The 10:30 PM checkpoint passed at 10:35 PM**: the must-have loop works end to end on devnet (connect → demo dollars → buy → sell → log → total P/L), so Nice-tier work can start. Next deadline: 9:00 AM Sunday feature freeze.

**How to use it**

- Check off your item in the same PR that finishes it, and add the PR number: `- [x] ... (#14)`.
- Found new work? Add it under the right heading, with an owner. Nobody owns it yet? Write **Anyone**.
- Cutting something? Move it to **Cut** with one line on why. Never cut the must-have loop.
- Finished items move to **Done** at the bottom, newest first.

## Now: 10:30 PM checkpoint (must-have loop)

All done; see Done (#19, #21).

## Should tier (after the loop works)

- [ ] **Justin** · Create a free Helius devnet key (https://dashboard.helius.dev) and share the URL in the team channel. Everyone puts it in `backend/.env` as `SOLANA_RPC_URL` and in `frontend/.env` as `VITE_SOLANA_RPC_URL`, replacing the rate-limited public RPC before the demo. `backend/.env.example` shows the format (#21).
- [ ] **Diego, Matthew** · Pick the live demo trade: stock, buy minute and sell minute, checked against the real bars. `seed_demo.py` already uses AKAM as the loss, so per the spec the live trade is MSFT or DDOG. Write it into the spec's demo script (both copies).
- [ ] **Diego** · Demo reset button in the UI that calls `/demo/reset`. Today's "Reset timer" only moves the clock and is disabled after a deposit. Optional if `seed_demo.py` covers every rehearsal. If built, it must also burn her leftover test tokens, as `seed_demo.py` does: `/demo/reset` only clears the ledger, so resetting and then clicking the faucet would leave 2,000 dUSD on-chain against 1,000 in the ledger, and `sell_all` would sell shares left from before the reset. (#20 review)

## Nice tier (only after the 10:30 PM checkpoint passes)

- [ ] **Diego, Justin** · Show average win vs. average loss on the dashboard. `/portfolio` already returns `stats.avg_win` and `stats.avg_loss`; the UI shows only win and loss counts. Khalil's 1:40 demo line needs these.
- [ ] **Khalil** · `/portfolio` rounds `cash` to the cent, but sells leave sub-cent units, so typing the full displayed cash can fail with "That costs $X but the wallet has $X". Floor spendable cash in `stats.portfolio`. (#16 review)
- [ ] **Diego** · Portfolio load errors use the market "Backend unavailable" banner, which the market poll clears every 2 s, and its Retry reloads only market data. Give the portfolio its own error state, or have Retry reload both. (#16 review)

## Demo, pitch and submission (Sunday)

- [ ] **Justin** · Slides: peso vs. dollar (0:00), what's next (2:20).
- [ ] **Justin** · Devpost draft: description, the two reference repos listed as external code, all 4 collaborators, repo link, Discord tag.
- [ ] **Justin** · Opt into **Blackstone** and **MLH Best Use of Solana** on Devpost. Without this we aren't judged for either.
- [ ] **Matthew** · Pre-demo run sheet: vault has devnet SOL, `seed_demo.py` (it runs `/demo/reset` and burns leftovers itself), demo wallet connected in Phantom, replay paused at 9:25 AM.
- [ ] **Everyone** · 9:00 AM feature freeze: bug fixes only. Rehearse 3 times with a reset between runs and record a backup screen video.
- [ ] **Justin** · Submit on Devpost by **10:30 AM** (code freeze 11:00 AM).

## Docs and housekeeping

- [ ] **Matthew** · `backend`, `dev`, `matthew-wallet` and `solana-testing` are gone. Still on GitHub: `docs/todo-list` and `feature/vault-functions` (both fully merged) and `revert-13-feature/vault-functions` (only a revert of #13, never merged). Delete them once you've confirmed nothing on them is needed.

## Open questions

- `seed_demo.py` seeds MSTR (win), AKAM (loss) and NVDA (held), all between 6:03 and 9:10 AM, before any alert fires. MSTR and NVDA never alert. Is that the story we want on the stats page, or should the seeded trades follow alerts?
- "Reset timer" rewinds the replay clock that every wallet shares, and it only checks that the connected wallet has no deposits. If a judge connects a fresh wallet and resets, the demo wallet's next trades are stamped before its earlier ones and the stats replay them out of order (a losing round trip can show as a win). Hide the button during judging, or have the backend refuse to seek back past any ledger row? (#16 review)
- The seeded log ends at −$7.07 total P/L (dry run). Does the live trade's gain turn that positive?
- Is xStocks available in Argentina, Ukraine and Nigeria? Unverified, so don't claim it in the pitch or on Devpost.
- Quote checks read only on-chain balances, but the ledger is the source of truth. After a bare `/demo/reset`, `sell_all` sells leftover shares as a fake win, and a buy can take ledger cash negative. Check the ledger too, or make "reset means rerun `seed_demo.py`" the rule? (#13 review) Related: `/faucet` answers 502 "try again" when its mint may have landed, so a retry can mint another $1,000 with only the second in the ledger. (#17 review) Also: if devnet stays unreachable for over 2 minutes mid-submit, the ticket gives up, and a trade that landed has no ledger row. (#21 review)

## Cut

- Stretch tier (live Jupiter quote, eligible-country badge, token names and logos in Phantom): out per the spec's timeline. Say "these are our test tokens" instead.

## Done

| When (ET) | What | PR |
| --- | --- | --- |
| Sat 11:25 PM | Docs match the build: README status, setup and demo prep; CONTRIBUTING file map; `DECISIONS.md` rows 18–22 and the alerts on the real bars; spec (both copies) setup checklist ticked, scanner results, seeded demo trades, demo-script prep and live trade (MSFT or DDOG) | #22 |
| Sat 11:14 PM | Trade ticket resubmits the same quote for up to 2 minutes, past the blockhash's life, instead of 3 tries, and after a dropped connection to the backend too. Gives up with "check Phantom", not "submit again" (#21 review) | #22 |
| Sat 11:04 PM | `/faucet` funds each wallet once (409 `already_funded` until `/demo/reset`); the button then reads "demo dollars added" and Khalil points at the seeded deposit on stage | #20 |
| Sat 10:45 PM | Trade ticket resubmits the same quote on `502 chain_unavailable` / `409 submit_in_progress` and re-quotes on `quote_expired` or `tx_failed`; `backend/.env.example` has `SOLANA_RPC_URL` and `VAULT_KEYPAIR` | #21 |
| Sat 10:35 PM | 10:30 PM checkpoint passed: Khalil ran the loop on devnet with Phantom (connect → demo dollars → buy → sell → log with explorer link → total P/L), backend on #19's branch, 1,165 requests all 200 | #21 |
| Sat 10:25 PM | One SQLite connection per thread plus WAL: `/portfolio` and `/transactions` no longer 500 under polling (load test: 50 of 900 before, 0 after) | #19 |
| Sat 9:34 PM | Vault error codes in the spec (both copies); a lost reply or dropped connection mid-trade no longer loses or doubles a trade | #17 |
| Sat 9:08 PM | Frontend wired to the vault: Get demo dollars, quote → Phantom signs → submit | #16 |
| Sat 8:44 PM | Real `/faucet`, `/trade/quote`, `/trade/submit`, `seed_demo.py` | #13 |
| Sat 8:27 PM | Scanner fires 3 alerts on the real bars (AKAM and DDOG at 9:30 AM, MSFT at 9:41 AM); dashboard, scanner feed, replay controls | #11 |
| Sat 8:02 PM | Vault test run lands on devnet (Phantom's warning is expected); devnet setup script, 20 mints in `mints.json` | #9 |
| Sat 6:46 PM | Replay data loader: Alpaca SIP minute bars, 20 daily baselines, Finnhub news | #8 |
| Sat 4:31 PM | README and CONTRIBUTING | #5 |
| Sat 4:20 PM | `stats.transaction` lookup for `/trade/submit`, must-have loop test | #4 |
| Sat 3:40 PM | Backend skeleton: replay clock, prices, ledger, stats, `/transactions`, `/portfolio` | #2 |
| Sat 3:32 PM | React + Vite frontend skeleton | #1 |
