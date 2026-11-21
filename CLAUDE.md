# Event Scout – rules for Claude

Four people build in parallel, each with their own Claude session. Deadline: showcase at 15:00.

- Plan, architecture and work packages: `PLAN.md`. Read the section of your package before you build.
- Contracts: `shared/schemas.py` is the single source of truth, `shared/schemas.ts` mirrors it. Change them only after the team agrees.
- Work only in the folder of your package (`web/`, `agents/<package>/`, `mcp_servers/`). This avoids merge conflicts.
- mcp 2.x: `from mcp.server.mcpserver import MCPServer` (`FastMCP` no longer exists). Do not create a folder `mcp/`, it would shadow the package.
- Add dependencies only with `uv add`, run tests with `uv run pytest`.
- Secrets only in `.env`: never commit them, never print them, never write them to logs. `DEMO_MODE=fixtures` is the default.
- Smallest working solution, no extras. Stretch goals only once the MVP is integrated.
- Commit and push only when the human says so. Run `git pull --rebase` first.
