"""Scan progress for the progress bar: the scout pipeline writes it, GET /progress (agents/concierge/app.py) reads it.

Stored per user in the shared store (table progress): {ts, city, stage, pct, text}. Stages: search, extract, rank,
resolve, done. While the scouts wait for a live fetch (stage search), the fetch's own progress is shown instead.
"""
import logging
import time

from shared import store

log = logging.getLogger(__name__)
IDLE = {"active": False, "pct": 0, "stage": "idle", "text": ""}
DONE_SHOWN = 10  # seconds the frontend can still read "done" (100 %)
MAX_AGE = 15 * 60


def report(ctx, stage: str, pct: int, text: str) -> None:
    """ctx: an ADK callback context (user id, state). Never raises: progress must not break a scan."""
    try:
        city = (ctx.state.get("profile") or {}).get("city") or ""
        store.put("progress", ctx.user_id, {"ts": time.time(), "city": city, "stage": stage, "pct": pct, "text": text})
    except Exception as e:
        log.warning("progress not written (%s)", type(e).__name__)


def progress_for(user_id: str) -> dict:
    rec = store.get("progress", user_id)
    age = time.time() - rec["ts"] if rec else 0
    if not rec or age > MAX_AGE or (rec["stage"] == "done" and age > DONE_SHOWN):
        return dict(IDLE)
    if rec["stage"] == "search" and rec.get("city"):
        from mcp_servers.event_sources import fetch_live  # lazy: pulls in the MCP server module
        fp = store.get("fetches", f"progress-{fetch_live.slug(rec['city'])}")
        if fp and fp["started"] >= rec["ts"] - 5 and fp["step"] < fp["steps"]:
            return {"active": True, "stage": "fetch", "pct": 5 + round(55 * fp["step"] / fp["steps"]),
                    "text": f"Loading live posts – {fp['text']}"}
    return {"active": True, "stage": rec["stage"], "pct": rec["pct"], "text": rec["text"]}
