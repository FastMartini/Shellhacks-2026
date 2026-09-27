# Running to-do list

What's left before the Sunday 10:30 AM submission, in the order it has to happen. Scope and contracts live in [`BUILD_SPEC.md`](BUILD_SPEC.md); this file only tracks who is doing what next.

Last updated: Sun Sept 27, 12:40 AM ET. **Next checkpoint: 10:30 PM**, when the must-have loop works end to end (connect → demo dollars → buy → sell → log → total P/L).

**How to use it**

- Check off your item in the same PR that finishes it, and add the PR number: `- [x] ... (#14)`.
- Found new work? Add it under the right heading, with an owner. Nobody owns it yet? Write **Anyone**.
- Cutting something? Move it to **Cut** with one line on why. Never cut the must-have loop.
- Finished items move to **Done** at the bottom, newest first.

## Now: 10:30 PM checkpoint (must-have loop)

- [ ] **Matthew** · Merge #13 (real `/faucet`, `/trade/quote`, `/trade/submit`, `seed_demo.py`). Diego approved it; it's 8 commits behind `main`, so merge `main` in and rerun `pytest` first.
- [ ] **Diego** · Open a PR for `fix/ui-changes` (Get demo dollars, quote → Phantom signs → submit, re-quote on `quote_expired`). Merge `main` in after #13 lands.
- [ ] **Justin** · Add `SOLANA_RPC_URL` (Helius devnet URL) and `VAULT_KEYPAIR` to `backend/.env.example`. Everyone puts the Helius URL in `backend/.env`, and in `frontend/.env` as `VITE_SOLANA_RPC_URL`.
- [ ] **Everyone** · Run the loop on devnet with Phantom (Testnet Mode on): connect → Get demo dollars → buy → click "Confirm (unsafe)" → sell → the log row has an explorer link → total P/L updates.
- [ ] **Matthew** · Add #13's error codes to the vault contract in the spec, both copies (see [Changing a contract](../CONTRIBUTING.md#changing-a-contract)). The ticket shows these messages.

## Should tier (after the loop works)

- [ ] **Diego, Matthew** · Pick the live demo trade: stock, buy minute and sell minute, checked against the real bars. `seed_demo.py` already uses AKAM as the loss, so per the spec the live trade is MSFT or DDOG. Write it into the spec's demo script (both copies).
- [ ] **Diego** · Demo reset button in the UI that calls `/demo/reset`. Today's "Reset timer" only moves the clock and is disabled after a deposit. Optional if `seed_demo.py` covers every rehearsal.

## Nice tier (only after the 10:30 PM checkpoint passes)

- [ ] **Anyone** · Pick the hero arrow weight on a real screen. #23 ships Round 4a ("bold") from the Claude Design project; 4b ("heavy") is one word away: set `ARROW` to `ARROW_PRESETS.heavy` in `MomentumArrow.tsx`.
- [ ] **Diego** · Decide whether the dashboard and scanner adopt the landing's look (Geist type, glass pill topbar). The design only covered the landing, so clicking through to the dashboard switches back to DM Sans and the old topbar.
- [ ] **Diego, Justin** · Show average win vs. average loss on the dashboard. `/portfolio` already returns `stats.avg_win` and `stats.avg_loss`; the UI shows only win and loss counts. Khalil's 1:40 demo line needs these.

## Demo, pitch and submission (Sunday)

- [ ] **Justin** · Slides: peso vs. dollar (0:00), what's next (2:20).
- [ ] **Justin** · Devpost draft: description, the two reference repos listed as external code, all 4 collaborators, repo link, Discord tag.
- [ ] **Justin** · Opt into **Blackstone** and **MLH Best Use of Solana** on Devpost. Without this we aren't judged for either.
- [ ] **Khalil, Matthew** · Decide what the demo opens on. #23 makes the landing page the default view, so the run sheet either starts there and clicks through, or opens on `#dashboard` and saves the hero for the end.
- [ ] **Matthew** · Pre-demo run sheet: vault has devnet SOL, `/demo/reset`, `seed_demo.py`, demo wallet connected in Phantom, replay paused at 9:25 AM.
- [ ] **Everyone** · 9:00 AM feature freeze: bug fixes only. Rehearse 3 times with a reset between runs and record a backup screen video.
- [ ] **Justin** · Submit on Devpost by **10:30 AM** (code freeze 11:00 AM).

## Docs and housekeeping

- [ ] **Whoever merges #13 / the UI PR** · Update the README status table. The vault row still says the routes are stubs.
- [ ] **Justin** · Tick the spec's setup checklist (both copies). Vault keypair, mints and `mints.json` are done. Helius and Phantom are still open.
- [ ] **Khalil** · `DECISIONS.md` intro still says the folder holds "only planning docs, no code".
- [ ] **Anyone** · Delete `frontend/src/App 2.tsx` and `frontend/src/styles 2.css`. Stale leftovers from the original Vite scaffold, untracked and deliberately left out of #23.
- [ ] **Matthew** · Delete the stale branches `backend`, `dev`, `matthew-wallet` and `solana-testing`, which are 42+ commits behind `main`, once you've confirmed nothing on them is needed.

## Open questions

- `seed_demo.py` seeds MSTR (win), AKAM (loss) and NVDA (held), all between 6:03 and 9:10 AM, before any alert fires. MSTR and NVDA never alert. Is that the story we want on the stats page, or should the seeded trades follow alerts?
- The seeded log ends at −$7.07 total P/L (dry run). Does the live trade's gain turn that positive?
- Is xStocks available in Argentina, Ukraine and Nigeria? Unverified, so don't claim it in the pitch or on Devpost.

## Cut

- Stretch tier (live Jupiter quote, eligible-country badge, token names and logos in Phantom): out per the spec's timeline. Say "these are our test tokens" instead.

## Done

| When (ET) | What | PR |
| --- | --- | --- |
| Sun 12:40 AM | Landing hero restyled to the reviewed design (Round 4a): platinum coins, bold zigzag arrow, glass topbar, proof row removed; the arrow and coins now shrink as one group on phones | #23 |
| Sat 11:43 PM | Landing hero: animated momentum scene, lazy-loaded, with a reduced-motion and no-WebGL fallback | #23 |
| Sat 8:27 PM | Scanner fires 3 alerts on the real bars (AKAM and DDOG at 9:30 AM, MSFT at 9:41 AM); dashboard, scanner feed, replay controls | #11 |
| Sat 8:02 PM | Vault test run lands on devnet (Phantom's warning is expected); devnet setup script, 20 mints in `mints.json` | #9 |
| Sat 6:46 PM | Replay data loader: Alpaca SIP minute bars, 20 daily baselines, Finnhub news | #8 |
| Sat 4:31 PM | README and CONTRIBUTING | #5 |
| Sat 4:20 PM | `stats.transaction` lookup for `/trade/submit`, must-have loop test | #4 |
| Sat 3:40 PM | Backend skeleton: replay clock, prices, ledger, stats, `/transactions`, `/portfolio` | #2 |
| Sat 3:32 PM | React + Vite frontend skeleton | #1 |
