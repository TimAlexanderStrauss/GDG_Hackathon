"""AG-UI endpoint for the web app. Run: uv run uvicorn agents.concierge.app:app --port 8000"""
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from fastapi import FastAPI
from google.adk.apps import App, ResumabilityConfig

from agents.concierge.agent import root_agent

app = FastAPI(title="Event Scout concierge")
agent = ADKAgent.from_app(
    App(name="event_scout", root_agent=root_agent, resumability_config=ResumabilityConfig(is_resumable=True)),
    user_id="demo_user",
)
add_adk_fastapi_endpoint(app, agent, path="/")  # path must match the agent URL in web/
