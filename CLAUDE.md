# Event Scout – Regeln für Claude

Vier Leute bauen parallel, jede Person mit eigener Claude-Session. Deadline: Showcase um 15:00.

- Plan, Architektur und Arbeitspakete: `PLAN.md`. Lies den Abschnitt deines Pakets, bevor du baust.
- Verträge: `shared/schemas.py` ist die Quelle der Wahrheit, `shared/schemas.ts` der Spiegel. Nur nach Absprache im Team ändern.
- Arbeite nur im Ordner deines Pakets (`web/`, `agents/<paket>/`, `mcp_servers/`). So gibt es keine Merge-Konflikte.
- mcp 2.x: `from mcp.server.mcpserver import MCPServer` (`FastMCP` gibt es nicht mehr). Keinen Ordner `mcp/` anlegen, er würde das Paket überdecken.
- Abhängigkeiten nur mit `uv add`, Tests mit `uv run pytest`.
- Secrets nur in `.env`: nie committen, nie ausgeben, nie in Logs schreiben. `DEMO_MODE=fixtures` ist der Standard.
- Kleinste funktionierende Lösung, keine Extras. Stretch-Ziele erst, wenn das MVP integriert ist.
- Commit und Push nur, wenn der Mensch es sagt. Vorher `git pull --rebase`.
