"""AG-UI endpoint for the web app. Run: uv run uvicorn agents.concierge.app:app --port 8000"""
import os
import re
from contextvars import ContextVar
from pathlib import Path

from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from fastapi import FastAPI, Request
from google.adk.apps import App, ResumabilityConfig
from google.adk.sessions import DatabaseSessionService

from agents.concierge.agent import root_agent

DEMO_USER = "demo_user"
_USER_RE = re.compile(r"^(demo_user|google:[^\s@]+@[^\s@]+)$")
_header_user: ContextVar[str | None] = ContextVar("header_user", default=None)

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "sidequest.db"


def extract_user_id(_input=None) -> str:
    """User id from the X-Sidequest-User header (set by the Next.js route); anything else is demo_user."""
    value = (_header_user.get() or "").strip()
    return value if _USER_RE.match(value) else DEMO_USER


def make_session_service(url: str | None = None) -> DatabaseSessionService:
    if url is None:
        url = os.environ.get("SESSION_DB_URL")
    if not url:
        DB_PATH.parent.mkdir(exist_ok=True)
        url = f"sqlite+aiosqlite:///{DB_PATH}"
    return DatabaseSessionService(db_url=url)


app = FastAPI(title="Event Scout concierge")


# shortcut: the concierge trusts any caller on its port; when hosted, add a shared secret between the route and here.
@app.middleware("http")
async def _read_user_header(request: Request, call_next):
    token = _header_user.set(request.headers.get("x-sidequest-user"))
    try:
        return await call_next(request)
    finally:
        _header_user.reset(token)


agent = ADKAgent.from_app(
    App(name="event_scout", root_agent=root_agent, resumability_config=ResumabilityConfig(is_resumable=True)),
    user_id_extractor=extract_user_id,
    session_service=make_session_service(),
    # The cache cleanup after the timeout must only untrack sessions, never delete the persisted ones.
    delete_session_on_cleanup=False,
    save_session_to_memory_on_cleanup=False,
)
add_adk_fastapi_endpoint(app, agent, path="/")  # path must match the agent URL in web/
