# Event Scout

Multi-agent system (Google ADK + Gemini) that scans social media posts for events that match your preferences, shows them as cards in a web app and, after your click, enrolls you via a separate agent.

Built at the DevFest Münster 2026 Agentic AI Hackathon. Plan, architecture and team split: [PLAN.md](PLAN.md).

## Stack

| Part | Tech |
|---|---|
| Agents | Google ADK 2.15 (Python), Gemini 3.8 Flash |
| Tools | MCP server `mcp_servers/event_sources` with prompt-injection guard (Gemini guard or Model Armor) |
| Agent to agent | A2A: concierge → enrollment agent |
| Agent to UI | AG-UI via `ag-ui-adk` + CopilotKit (Next.js) |

## Setup

```bash
uv sync
cp .env.example .env      # add your own GOOGLE_API_KEY from https://aistudio.google.com/apikey
uv run pytest             # checks fixtures against shared/schemas.py
```

## Run

```bash
npx concurrently "uv run uvicorn agents.concierge.app:app --port 8000" \
                 "uv run uvicorn agents.enrollment.agent:a2a_app --port 8001" \
                 "npm --prefix web run dev"
```

`DEMO_MODE=fixtures` (default) uses `fixtures/posts.json` (fictional demo posts). `DEMO_MODE=live` uses Apify.

## Team

| Part | Owner |
|---|---|
| 1 Onboarding platform (web app, profile) | P1 |
| 2 Scanning socials (MCP server, scouts, guard) | P2 |
| 3 Display events (concierge, AG-UI) | P3 |
| 4 Enrollment (A2A agent) | P4 |
