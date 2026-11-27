"""Run the scout pipeline once with the demo persona (real Gemini + MCP). uv run python -m agents.scouts.smoke"""
import asyncio

from dotenv import load_dotenv

load_dotenv(".env")  # before the agent import: it reads GEMINI_MODEL

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from agents.scouts.agent import event_sources, scout_pipeline  # noqa: E402

LEA = {"user_id": "lea", "display_name": "Lea", "email": "lea@example.com", "city": "Münster",
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
    await event_sources.close()


asyncio.run(main())
