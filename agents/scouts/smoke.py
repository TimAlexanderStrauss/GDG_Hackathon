"""Run the scout pipeline once with the demo persona (real LLM + MCP). uv run python -m agents.scouts.smoke [city]
With DEMO_MODE=live it reads fixtures/live/<city>.json (default Münster) and prints the share of `unknown` (PLAN.md
phase 2). For a new city run `fetch_live --city <city>` first: the server's background fetch stops when this script exits."""
import asyncio
import sys

from dotenv import load_dotenv

load_dotenv(".env")  # before the agent import: it reads GEMINI_MODEL

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from agents.scouts.agent import event_sources, scout_pipeline  # noqa: E402

LEA = {"user_id": "lea", "display_name": "Lea", "email": "lea@example.com", "city": sys.argv[1] if len(sys.argv) > 1 else "Münster",
       "interests": ["AI", "Techno", "Startups"], "days_ahead": 14}


async def main():
    runner = InMemoryRunner(agent=scout_pipeline, app_name="smoke")
    s = await runner.session_service.create_session(app_name="smoke", user_id="lea", state={"profile": LEA})
    async for _ in runner.run_async(user_id="lea", session_id=s.id,
                                    new_message=types.Content(role="user", parts=[types.Part(text="Find events")])):
        pass
    state = (await runner.session_service.get_session(app_name="smoke", user_id="lea", session_id=s.id)).state
    for a in state["audit"]:
        print("audit:", a["agent"], "-", a["note"])
    for e in state["events"]:
        print(f"{e['match_score']:.2f} {e['signup']:11} {e['start']}  {e['title']}  ({e['match_reason']})")
    kinds = [e["signup"] for e in state["events"]]  # PLAN.md phase 2 target: unknown below 10 %
    print(f"unknown: {kinds.count('unknown')}/{len(kinds)}", {k: kinds.count(k) for k in sorted(set(kinds))})
    await event_sources.close()


asyncio.run(main())
