# Running to-do list

What's left before Devpost closes at 11:00 AM Sunday, in the order it has to happen. Scope and contracts live in [`BUILD_SPEC.md`](BUILD_SPEC.md); this file only tracks who is doing what next.

Last updated: Sun Sept 27, 10:00 AM ET. **Devpost submissions close at 11:00 AM**, the same time as the code freeze; we aim to submit by 10:30 to leave a buffer. None of the Devpost items below is checked off, so confirm them first; missing the submission or the prize opt-in means we aren't judged. Since the 9:00 AM feature freeze, it's bug fixes only.

**How to use it**

- Check off your item in the same PR that finishes it, and add the PR number: `- [x] ... (#14)`.
- Found new work? Add it under the right heading, with an owner. Nobody owns it yet? Write **Anyone**.
- Cutting something? Move it to **Cut** with one line on why. Never cut the must-have loop.
- Finished items move to **Done** at the bottom, newest first.

## Now: 10:30 PM checkpoint (must-have loop)

All done; see Done (#19, #21).

## Should tier (after the loop works)

- [ ] **Diego, Matthew** · Pick the live demo trade: stock, buy minute and sell minute, checked against the real bars. `seed_demo.py` already uses AKAM as the loss, so per the spec the live trade is MSFT or DDOG. Write it into the spec's demo script (both copies).
- [ ] **Diego** · Demo reset button in the UI that calls `/demo/reset`. Today's "Reset timer" only moves the clock and is disabled after a deposit. Optional if `seed_demo.py` covers every rehearsal. If built, it must also burn her leftover test tokens, as `seed_demo.py` does: `/demo/reset` only clears the ledger, so resetting and then clicking the faucet would leave 2,000 dUSD on-chain against 1,000 in the ledger, and `sell_all` would sell shares left from before the reset. (#20 review)

## Nice tier (only after the 10:30 PM checkpoint passes)

- [ ] **Anyone** · Pick the hero arrow weight on a real screen. #23 ships Round 4a ("bold") from the Claude Design project; 4b ("heavy") is one word away: set `ARROW` to `ARROW_PRESETS.heavy` in `MomentumArrow.tsx`.
- [ ] **Khalil** · `/portfolio` rounds `cash` to the cent, but sells leave sub-cent units, so typing the full displayed cash can fail with "That costs $X but the wallet has $X". Floor spendable cash in `stats.portfolio`. (#16 review)
- [ ] **Diego** · Portfolio load errors use the market "Backend unavailable" banner, which the market poll clears every 2 s, and its Retry reloads only market data. Give the portfolio its own error state, or have Retry reload both. (#16 review)

## Demo, pitch and submission (Sunday)

- [ ] **Everyone** · Check that `SOLANA_RPC_URL` in `backend/.env` and `VITE_SOLANA_RPC_URL` in `frontend/.env` use the host `devnet.helius-rpc.com`. Khalil's copies had `mainnet.helius-rpc.com`, where our mints don't exist, so the faucet and every trade fail. The same Helius key works on both hosts. Restart uvicorn after editing `backend/.env`; `--reload` only watches `.py` files.
- [ ] **Anyone** · Rerun the must-have loop through Phantom on today's `main`. #26–#28 changed the scanner, the replay start and the whole app's styling after the 10:30 PM checkpoint. The backend half already passed: `seed_demo.py` ran clean on devnet at 9:40 AM (faucet, five trades, ledger matches the chain).
- [ ] **Justin** · Slides: peso vs. dollar (0:00), what's next (2:20).
- [ ] **Justin** · Devpost draft: description, the two reference repos listed as external code, all 4 collaborators, repo link, Discord tag.
- [ ] **Justin** · Opt into **Blackstone** and **MLH Best Use of Solana** on Devpost. Without this we aren't judged for either.
- [ ] **Khalil, Matthew** · Decide what the demo opens on. #23 makes the landing page the default view, so the run sheet either starts there and clicks through, or opens on `#dashboard` and saves the hero for the end.
- [ ] **Matthew** · Pre-demo run sheet: vault has devnet SOL, `seed_demo.py` (it runs `/demo/reset` and burns leftovers itself), demo wallet connected in Phantom, replay paused at 7:00 AM.
- [ ] **Everyone** · 9:00 AM feature freeze: bug fixes only. Rehearse 3 times with a reset between runs and record a backup screen video.
- [ ] **Justin** · Submit on Devpost by **10:30 AM**. Devpost closes at **11:00 AM**, with the code freeze.

## Docs and housekeeping

- [ ] **Matthew** · The old branches are gone. Still on GitHub: `logo` (fully merged, #25) and `branch-name` (one commit, an earlier copy of the average win/loss cards that landed in #27; it branches from before #23, so merging it would undo #23 and #26–#28). Delete both once you've confirmed nothing on them is needed.

## Open questions

- `seed_demo.py` seeds MSTR (win), AKAM (loss) and NVDA (held), all between 6:03 and 9:10 AM, before any alert fires. MSTR and NVDA never alert. Is that the story we want on the stats page, or should the seeded trades follow alerts? Also, the script leaves the clock at 7:00 AM, so the log already shows the 7:22, 8:30 and 9:10 trades before the replay reaches them.
- "Reset timer" rewinds the replay clock that every wallet shares, and it only checks that the connected wallet has no deposits. If a judge connects a fresh wallet and resets, the demo wallet's next trades are stamped before its earlier ones and the stats replay them out of order (a losing round trip can show as a win). Hide the button during judging, or have the backend refuse to seek back past any ledger row? (#16 review)
- The seeded log ends at −$6.98 total P/L (1 win, 1 loss; Sunday 9:40 AM devnet run). Does the live trade's gain turn that positive?
- Is xStocks available in Argentina, Ukraine and Nigeria? Unverified, so don't claim it in the pitch or on Devpost.
- Quote checks read only on-chain balances, but the ledger is the source of truth. After a bare `/demo/reset`, `sell_all` sells leftover shares as a fake win, and a buy can take ledger cash negative. Check the ledger too, or make "reset means rerun `seed_demo.py`" the rule? (#13 review) Related: `/faucet` answers 502 "try again" when its mint may have landed, so a retry can mint another $1,000 with only the second in the ledger. (#17 review) Also: if devnet stays unreachable for over 2 minutes mid-submit, the ticket gives up, and a trade that landed has no ledger row. (#21 review)

## Cut

- Stretch tier (live Jupiter quote, eligible-country badge, token names and logos in Phantom): out per the spec's timeline. Say "these are our test tokens" instead.

## Done

| When (ET) | What | PR |
| --- | --- | --- |
| Sun 11:22 AM | README setup guide: teammate and fork paths, a check after each step, stopping and restarting, wallet reset, troubleshooting for the faucet, trades and servers, and where to make changes | — |
| Sun 9:50 AM | `frontend/src/App 2.tsx` and `styles 2.css` (untracked scaffold leftovers) are gone from Khalil's checkout | — |
| Sun 3:06 AM | Dashboard and scanner match the landing hero: Geist type, near-black background, glass topbar, pill buttons | #28 |
| Sun 2:58 AM | Average win and average loss cards on the dashboard; chart analysis and scanner refinements | #27 |
| Sun 2:08 AM | Momentum scanner dashboard: replay starts at 7:00 AM pre-market, every stock monitored each minute through 4:15 PM, ten-minute news updates, line and candlestick charts | #26 |
| Sun 1:53 AM | New logo | #25 |
| Sun 12:40 AM | Landing hero restyled to the reviewed design (Round 4a): platinum coins, bold zigzag arrow, glass topbar, proof row removed; the arrow and coins now shrink as one group on phones | #23 |
| Sat night | Helius key replaces the rate-limited public RPC (shared on the mainnet host; see the first Demo item) | — |
| Sat 11:43 PM | Landing hero: animated momentum scene, lazy-loaded, with a reduced-motion and no-WebGL fallback | #23 |
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
