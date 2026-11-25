"""AG-UI endpoint for the concierge.

Run: python -m uv run uvicorn agents.concierge.app:app --port 8000
"""
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from fastapi import FastAPI
from google.adk.apps import App, ResumabilityConfig

from agents.concierge.agent import root_agent

adk_app = App(
    name="concierge",
    root_agent=root_agent,
    resumability_config=ResumabilityConfig(is_resumable=True),  # needed for human-in-the-loop (choose_event)
)

agui_agent = ADKAgent.from_app(
    adk_app,
    user_id="demo_user",
    session_timeout_seconds=3600,
    use_in_memory_services=True,
)

app = FastAPI(title="Event Scout concierge")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# TODO(P1/P3): match the path to the CopilotKit template's runtime config once web/ exists.
add_adk_fastapi_endpoint(app, agui_agent, path="/")
