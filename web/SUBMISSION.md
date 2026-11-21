# Devpost submission draft: Sidequest

Paste-ready text. Before you submit:
- Update "What it does" once the team's parts are integrated. As of 14:00, the web app is tested only against a mock agent.
- Tick the prize category **Best Use of the Google Gemini API**.
- List the AI coding tools the team used (for example Claude Code, Antigravity).
- Registration, team invitations, making the repo public and the final submit are done by a person (see PLAN.md).

---

**Tagline:** Less scrolling. More going.

## Inspiration

The best events in Münster rarely show up in an event calendar. They live in Instagram posts, TikTok videos and small websites, and every one has its own sign-up: a form, a DM, "link in bio". We wanted an agent that does the scrolling for us and signs us up, but only when we say so.

## What it does

- You sign in (demo) and pick your interests, city, how far ahead to look and which sources to scan. You can also paste in preferences from ChatGPT, Claude or Grok: we give you a prompt, the assistant answers in JSON, and Sidequest fills the form for you to review.
- Scout agents read public posts for your city. Before any model sees a post, a guard checks it for prompt injection. Our demo data contains a poisoned post, and it gets blocked, with the block shown in the app.
- A curator ranks the remaining events against your interests and explains each match ("Matches: AI, evenings, Münster").
- Events appear as cards. When you click **Enroll me**, that click is the approval: the concierge hands the event to a separate enrollment agent over A2A. If the event uses a Google Form, the enrollment agent fills it in. If not, it gives you step-by-step instructions and a calendar link.
- An Activity panel shows every tool call the agents make, live.

## How we built it

- **Agents:** Google ADK with Gemini. A concierge orchestrates scouts that run in parallel, a curator, and an enrollment agent.
- **Tools:** an MCP server (`event-sources`) with one task-shaped tool, `search_posts`. The server validates input and runs the injection guard (regex plus a Gemini classifier).
- **Agent to agent:** A2A from the concierge to the enrollment agent. The enrollment agent runs as its own process with its own credentials.
- **Agent to UI:** AG-UI through `ag-ui-adk` and a self-hosted CopilotKit runtime in a Next.js 16 app. The profile, scan progress, events, enrollments and audit log live in shared agent state. The enroll click is a human-in-the-loop tool call (`choose_event`) that returns `{event_id, approved_at}` exactly once.
- **Design:** Manrope type, brand orange (#FF5A36) with charcoal text for accessible contrast, and a detour-arrow logo vectorised to SVG.

## Challenges we ran into

- Current CopilotKit and Next.js versions changed their APIs (the CopilotKit v2 hooks, Next.js 16 Cache Components), so we built against the installed type definitions instead of older tutorials.
- CopilotKit's chat styles define their own variable names (`--muted`, `--accent`), which clashed with ours. We namespaced our design tokens.
- Official Instagram, TikTok, X and Facebook APIs need app reviews that take days. So the demo uses fixture posts, and social sign-in and "Connect" are clearly labelled demos.
- Security without blocking the user: the scouts have read-only tools, and only the enrollment agent can enroll, and only after a real click.

## Accomplishments that we're proud of

- A prompt-injection post in the data gets blocked live, and the block shows up in the UI.
- The approval is a real click, recorded as `approved_at`, not a model's decision.
- Preferences can be imported from the assistant you already use, without handing it any consent.

## What we learned

The system prompt is a request; the tool set is the boundary. Showing every tool call to the user builds more trust than any disclaimer.

## What's next

- Real sign-in (Google OAuth first) and a live data provider in place of the fixtures.
- Recommendations from connected accounts: the people and venues you follow on Instagram, X and Facebook tune the ranking (needs official API access).
- X and Facebook as sources once the shared contract and the scouts support them.
- Event cards as A2UI surfaces, Model Armor as the guard, and deployment on Cloud Run.

## Built with

Google ADK · Gemini API · Model Context Protocol (MCP) · A2A · AG-UI · ag-ui-adk · CopilotKit · Next.js · React · TypeScript · Tailwind CSS · Python · FastAPI · uv · simple-icons
