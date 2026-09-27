---
name: shellhacks-project
description: ShellHacks 2026 (Sept 26–27) project — tokenized US stocks on Solana devnet + large-cap momentum scanner + trade stats; spec doc link and settled decisions
metadata:
  node_type: memory
  type: project
  originSessionId: 61f191f9-5b72-4394-854d-c12c7d0a87d9
  modified: 2026-09-27T03:25:00.000Z
---

ShellHacks 2026 hackathon. Coding starts Sat 2026-09-26 2:45 PM (moved from 10 AM); feature freeze Sun 9 AM, deadline Sun 2026-09-27 11 AM EDT (~11 build hrs). Checkpoints Sat 6:00 PM and 10:30 PM, both passed (the must-have loop ran end to end on devnet at 10:35 PM). Judging Sun 1–5 PM, live 3-min demo. Entering Blackstone + MLH Best Use of Solana (must opt into both on Devpost).

Shared build spec (Claude Docs): https://claude.ai/code/artifact/3854c60f-284b-46e2-8c67-0fd57b3845b7 — the source of truth for contracts, scanner rules, vault flow, timeline, demo script.

Settled via a grilling session: fresh build (rules forbid reusing the two reference repos — high-momentum-scanner, quantsim); Python FastAPI + React; Phantom wallet login; devnet vault (one tx, vault fee payer, mint/burn mock tokens) because US persons can't buy xStocks; xStocks 19-stock universe; Friday Sept 25 replay (planned as AKAM/MSFT wins, TSLA loss; see below for what the real bars allowed); stats not backtesting, average-cost P/L; no AI; long only; runs on one laptop. Demo persona: Sofía in Argentina (Ukraine, Nigeria mentioned). China/Cuba dropped (sanctions/issuer exclusions).

After an independent review (2026-09-26) the spec was revised: Phantom signs first and the backend co-signs via `/trade/submit` (replaced `/trade/confirm`); Alpaca `feed=sip` not IEX; SQLite ledger is the source of truth for cash/deposits; mock dollar token is "dUSD"; `/demo/reset` + `seed_demo.py`; AKAM likely gapped up at open (deal announced Thursday), so demo trades must be scripted against real bars. They were: AKAM faded off its gap, so `seed_demo.py` pre-runs MSTR (win), AKAM (loss) and an open NVDA position, and the live trade is MSFT or DDOG. Project root has CLAUDE.md (entry point); docs/ has BUILD_SPEC.md (spec copy), DECISIONS.md (rationale, research, open items) and TODO.md (running to-do list).

Team: Khalil (backend, trade log/stats, pitch), Diego (scanner rules + service, React front-end), Matthew (vault via Solana Python SDK, Alpaca replay data), Justin (beginner: setup scripts, Devpost, slides).

**Why:** the vault was the team's biggest unknown; it now works on devnet (Phantom shows a "Failed to simulate" warning, explained in the demo).
**How to apply:** read the spec doc before helping with any piece; keep scope to the must-have loop.
