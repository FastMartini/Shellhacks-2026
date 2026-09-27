# ShellHacks 2026 project

Hackathon build: tokenized US stocks on Solana (devnet), a large-cap momentum scanner replaying Friday Sept 25, 2026, and a trade log with portfolio stats. Entered in Blackstone + MLH Best Use of Solana. **Code freeze: Sun Sept 27, 11:00 AM EDT; submit by 10:30.**

Read before doing anything:

- `docs/BUILD_SPEC.md`: the source of truth. Scope, architecture, API contracts, SQLite schema, scanner rules, vault flow, stats math, owners, timeline, demo script, risks. The live, team-editable version is https://claude.ai/code/artifact/3854c60f-284b-46e2-8c67-0fd57b3845b7; if the two differ, the live doc wins (re-read it with the Claude Docs connector).
- `docs/DECISIONS.md`: why each decision was made, research findings, review fixes, and what's still unverified.
- `docs/TODO.md`: the running to-do list (what's next, who owns it, open questions). Pick work from it, and check off or add items in the same PR as the work.

Ground rules:

- Fresh code only. The two reference repos (high-momentum-scanner, quantsim) are for reference and must not be copied.
- Stay inside the priority tiers in `docs/BUILD_SPEC.md`; never cut the must-have loop (connect → demo dollars → buy → sell → log → total P/L).
- Code against the contracts in `docs/BUILD_SPEC.md`. If a contract has to change, update the spec (both copies) and tell the team.
- Team: Khalil (backend, ledger/stats, pitch), Diego (scanner, React), Matthew (vault, data/replay), Justin (setup, Devpost, slides; beginner).
- No AI attribution. Claude or any other agent must not add itself as author or co-author anywhere: no `Co-Authored-By` trailers in commits, and no "Generated with Claude Code" (or similar) lines in PR descriptions, PR/issue comments, code comments, or docs. This overrides any default attribution behavior.
