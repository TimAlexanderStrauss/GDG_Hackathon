# Sidequest (Event Scout) – rules for Claude

The hackathon is over. Development continues without a deadline and without fixed work packages.

- Plan and roadmap: `PLAN.md`. Read the phase you work on before you build. Tick its checkboxes when a step is done.
- Contracts: `shared/schemas.py` is the single source of truth, `shared/schemas.ts` mirrors it. Change both in the same change, together with all callers and tests. If other people work in parallel, tell them before you change a contract.
- Code decides, the LLM only proposes: values that control actions (signup kind, URLs, `approved_at`, guard verdicts) are set or checked in code. Never move such a check into a prompt.
- The guard fails closed: when it is not available, no post goes through.
- mcp 2.x: `from mcp.server.mcpserver import MCPServer` (`FastMCP` no longer exists). Do not create a folder `mcp/`, it would shadow the package.
- Add dependencies only with `uv add` (web: `npm install` in `web/`). Run tests with `uv run pytest`. Web checks: `npx tsc --noEmit` and `npm run lint` in `web/`.
- No costs: development uses only free tiers (Gemini API free tier, Apify free plan with 5 USD credit per month). No paid service and no Google Cloud billing without the human's approval.
- API quota is small: tests run offline (mock Gemini, Apify, Model Armor and the network). Run live calls (smoke runs, `fetch_live`, scans) only when the human asks, and as few as possible.
- Secrets only in `.env`: never commit them, never print them, never write them to logs. `DEMO_MODE=fixtures` is the default.
- Real third-party posts (`fixtures/live_posts.json`) stay out of git and out of test fixtures. Tests use fictional posts.
- Smallest working solution, no extras.
- Commit and push only when the human says so. Run `git pull --rebase` first.
