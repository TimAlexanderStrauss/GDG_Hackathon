# Sidequest web app (P1)

Next.js 16 + CopilotKit 1.90 (v2 API) frontend: sign-in (Google real, others demo), add socials, preferences (with AI-assistant import), event cards, chat, scan progress and audit log. Self-hosted CopilotKit runtime, no CopilotKit Cloud or Intelligence account.

## Run

```bash
cd web
npm install
cp .env.example .env.local   # optional, defaults work locally
npm run dev                  # http://localhost:3000
```

Checks: `npx tsc --noEmit`, `npm run lint`, `npm run build`. Design system: [DESIGN.md](DESIGN.md).

## Environment (web/.env.local)

| Variable | Default | What |
|---|---|---|
| `CONCIERGE_URL` | `http://localhost:8000/` | P3's AG-UI endpoint (server-side only) |
| `COPILOTKIT_TELEMETRY_DISABLED` | unset | set `true` to turn off CopilotKit runtime telemetry |

Google sign-in (Auth.js v5, `next-auth@beta`) needs `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET` and `AUTH_SECRET` in `web/.env.local` (git ignores it, see `.env.example`). The LLM keys stay in the Python processes.

## Sign-in

- **Google is real:** the button calls `signIn("google")` (scopes `openid email profile`). Config in `auth.ts`, route `app/api/auth/[...nextauth]/route.ts`. The Google client needs the redirect URI `http://localhost:3000/api/auth/callback/google`.
- After the redirect, `ScoutApp` turns the Auth.js session (real name and email) into the existing `Session` (provider `google`) and goes on to the socials step. Sign-out also ends the Auth.js session.
- Instagram, X, Facebook and email stay demo and are labelled "(Demo)" in the UI.

## Integration contract for P3 (concierge)

```
Browser ──AG-UI──▶ /api/copilotkit (Next.js, self-hosted CopilotKit runtime)
                     └─ agent "event_scout" = HttpAgent(CONCIERGE_URL)
                          └─▶ P3: ADK agent via ag-ui-adk on :8000
```

P3 must provide:

1. **AG-UI endpoint at `http://localhost:8000/`**: `add_adk_fastapi_endpoint(app, adk_agent, path="/")` in `agents/concierge/app.py`, run with `uv run uvicorn agents.concierge.app:app --port 8000`. Another path: set `CONCIERGE_URL`.
2. **Read the profile from state:** `state["profile"]` is a `UserProfile` (shared/schemas.py). The web app writes it before every run and keeps all other state keys. Each scan starts with a user message like *"Find events for me in Münster in the next 14 days. Interests: AI, Techno …"*.
3. **Write these state keys** (shapes = `AgentState` in shared/schemas.ts). The UI shows only what is in state, never invented values:
   - `progress`: `[{platform, status: "running"|"done"|"error", posts, blocked}]`
   - `events`: `Event[]`
   - `enrollments`: `{[event_id]: "pending"|"registered"|"manual"|"failed"}`
   - `audit`: `[{ts (ISO), agent, tool, note}]`
4. **Call the frontend tool `choose_event`** (registered by the web app, add `AGUIToolset()` to the concierge's tools):
   - args: `{"events": Event[]}`
   - result after the user clicks a card: `{"event_id": "<id>", "approved_at": "<ISO time>"}`. This is the approval for `EnrollmentRequest.approved_at`.
   - result if the user clicks "None of these": `{"event_id": null, "approved_at": null, "declined": true}`. Do not enroll.
   - Each call can be answered once; the buttons lock after the click.
5. **Consent:** `profile.consent_enrollment == false` means no automatic enrollment: return manual steps (`status: "manual"`). The button then reads "Get sign-up steps".

## Shared state handling

- `components/Dashboard.tsx`: `agent.setState({...state, profile})` before `copilotkit.runAgent()`; the profile is in the run input.
- `components/ChooseEventTool.tsx`: `useHumanInTheLoop` for `choose_event`; `lib/choice-store.ts` lets the chat and the main card grid answer the same call exactly once.
- `components/ConfirmSubmitTool.tsx`: `useHumanInTheLoop` for `confirm_submit` (args `{event_id, title, preview, link}`); returns `{event_id, confirmed_at}` on Submit or `{event_id, declined: true}` on Cancel.
- `components/ScanPanel.tsx`: renders `progress` and `audit` only.

## Demo-only parts (say so in the pitch)

- **Sign-in** with Instagram, X, Facebook and email is a demo: no OAuth, the session is in `sessionStorage`. Real login needs OAuth apps (Meta and X need app review). Google is real, see Sign-in.
- **"Connect" socials** only records the choice (labelled "Added (demo)"). Instagram and TikTok also preselect scan sources. X and Facebook are not in the shared `Platform` type and no scout reads them.
  The added socials go to the concierge as a hint in each scan message ("I use instagram, x; prefer events from those communities."). Recommendations from real follows and likes need official API access: roadmap.
- **AI import:** copy a prompt into ChatGPT, Claude or Grok and paste the JSON reply back. Only preferences are taken; email and consent are always ignored.

## Map

Discovery has a **Cards / Map** switch. The map is the keyless Google Maps embed (`lib/maps.ts`): one event at a time, picked from the list beside it, plus an "Open in Google Maps" link on every card. No API key and no billing. A single map with a pin per event would need the Maps JavaScript API with a billed key and geocoding (events only carry venue and city text).

## Limitations

- Tested end to end against a mock AG-UI agent, not yet against P3's real concierge.
- `EnrollmentResult` message, link and calendar link show only if the concierge writes them into chat; the card shows the status from `state.enrollments`.
