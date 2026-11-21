"""Guardrails of the concierge's enroll tool: no click, no consent or a double click -> no A2A call."""
import asyncio
import json
from types import SimpleNamespace

from google.adk.events import Event as AdkEvent
from google.genai import types

from agents.concierge import agent as concierge

PROFILE = {"display_name": "Lea", "email": "lea@example.com", "consent_enrollment": True}


def _ctx(click: dict | None, profile=PROFILE, enrollments=None):
    ctx = SimpleNamespace(state={"profile": profile, "enrollments": enrollments or {}}, session=SimpleNamespace(events=[]))
    concierge.scout_pipeline(ctx)  # stub fills state["events"]
    if click:
        part = types.Part(function_response=types.FunctionResponse(name="choose_event", response=click))
        ctx.session.events.append(AdkEvent(author="user", content=types.Content(role="user", parts=[part])))
    return ctx


def _run(ctx, monkeypatch, reply="{}"):
    calls = []

    async def fake_run_async(*, args, tool_context):
        calls.append(json.loads(args["request"]))
        return reply

    monkeypatch.setattr(concierge._enrollment, "run_async", fake_run_async)
    return asyncio.run(concierge.enroll(ctx)), calls


def _click():
    return {"event_id": _ctx(None).state["events"][0]["id"], "approved_at": "2026-11-21T14:05:00+01:00"}


def test_enroll_sends_request_built_from_click_and_profile(monkeypatch):
    click = _click()
    reply = json.dumps({"event_id": click["event_id"], "status": "registered", "message": "ok"})
    ctx = _ctx(click)
    result, calls = _run(ctx, monkeypatch, reply)
    assert result["status"] == "registered"
    assert calls[0]["attendee_email"] == "lea@example.com" and calls[0]["event"]["id"] == click["event_id"]
    assert ctx.state["enrollments"] == {click["event_id"]: "registered"}


def test_enroll_refuses_without_click_declined_or_twice(monkeypatch):
    click = _click()
    declined = {"event_id": None, "approved_at": None, "declined": True}
    for ctx in (_ctx(None), _ctx(declined), _ctx(click, enrollments={click["event_id"]: "registered"})):
        result, calls = _run(ctx, monkeypatch)
        assert "error" in result and calls == []


def test_enroll_without_consent_gives_manual_steps_without_a2a(monkeypatch):
    ctx = _ctx(_click(), profile={**PROFILE, "consent_enrollment": False})
    result, calls = _run(ctx, monkeypatch)
    assert result["status"] == "manual" and result["link"] and calls == []


def test_enroll_marks_failed_when_agent_gives_no_result(monkeypatch):
    ctx = _ctx(_click())
    result, _ = _run(ctx, monkeypatch, reply="")
    assert result["status"] == "failed"
