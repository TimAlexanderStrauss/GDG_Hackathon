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


def test_scout_result_is_replaced_by_json_events_from_state():
    ctx = _ctx(None)
    raw = [object()]  # stands in for the HttpUrl objects ADK puts into the result
    out = concierge._json_safe_scouts(SimpleNamespace(name="scout_pipeline"), {}, ctx, raw)
    assert out == {"events": ctx.state["events"], "scan_notes": []} and json.dumps(out)
    assert concierge._json_safe_scouts(SimpleNamespace(name="enroll"), {}, ctx, {"x": 1}) is None


def test_enroll_repairs_empty_link_from_small_model(monkeypatch):
    click = _click()
    reply = json.dumps({"event_id": "wrong", "status": "manual", "message": "1.\n2.", "link": ""})
    result, _ = _run(_ctx(click), monkeypatch, reply)
    assert result["status"] == "manual" and result["event_id"] == click["event_id"] and result["link"]


def _click_for(ctx, i):
    return {"event_id": ctx.state["events"][i]["id"], "approved_at": "2026-11-21T14:05:00+01:00"}


def test_enroll_none_is_not_needed_with_calendar_and_no_a2a(monkeypatch):
    ctx = _ctx(None)
    ctx.session.events.append(AdkEvent(author="user", content=types.Content(role="user", parts=[types.Part(
        function_response=types.FunctionResponse(name="choose_event", response=_click_for(ctx, 2)))])))
    result, calls = _run(ctx, monkeypatch)
    assert result["status"] == "not_needed" and result["calendar_link"] and "maps" in result["link"] and calls == []
    assert "Already handled" in asyncio.run(concierge.enroll(ctx))["error"]  # double click


def test_enroll_unknown_is_manual_without_draft_and_a2a(monkeypatch):
    ctx = _ctx(None)
    ctx.state["events"][2]["signup"] = "unknown"
    ctx.session.events.append(AdkEvent(author="user", content=types.Content(role="user", parts=[types.Part(
        function_response=types.FunctionResponse(name="choose_event", response=_click_for(ctx, 2)))])))
    result, calls = _run(ctx, monkeypatch)
    assert result["status"] == "manual" and "draft" not in result["message"].lower() and calls == []


# --- web_form: preview, confirm_submit, submit ---
def _web_ctx(consent=True):
    ctx = _ctx(None, profile={**PROFILE, "consent_enrollment": consent})
    ev = ctx.state["events"][2]  # stub event without sign-up
    ev.update(signup="web_form", registration_url="https://forms.example.org/register")
    return ctx, ev["id"]


def _answer(ctx, name, response):
    part = types.Part(function_response=types.FunctionResponse(name=name, response=response))
    ctx.session.events.append(AdkEvent(author="user", content=types.Content(role="user", parts=[part])))


def _runs(ctx, monkeypatch, replies):
    calls = []

    async def fake_run_async(*, args, tool_context):
        calls.append(json.loads(args["request"]))
        return replies[len(calls) - 1]

    monkeypatch.setattr(concierge._enrollment, "run_async", fake_run_async)
    return calls


def test_web_form_without_consent_stays_manual_link(monkeypatch):
    ctx, eid = _web_ctx(consent=False)
    _answer(ctx, "choose_event", {"event_id": eid, "approved_at": "2026-11-21T14:05:00+01:00"})
    calls = _runs(ctx, monkeypatch, [])
    assert asyncio.run(concierge.enroll(ctx))["status"] == "manual" and calls == []


def test_web_form_preview_then_confirmed_submit(monkeypatch):
    ctx, eid = _web_ctx()
    _answer(ctx, "choose_event", {"event_id": eid, "approved_at": "2026-11-21T14:05:00+01:00"})
    calls = _runs(ctx, monkeypatch, [json.dumps({"event_id": eid, "status": "needs_confirmation", "message": "Planned: Lea"}),
                                    json.dumps({"event_id": eid, "status": "registered", "message": "done"})])
    first = asyncio.run(concierge.enroll(ctx))
    assert first["status"] == "needs_confirmation" and calls[0]["confirmed_at"] is None
    assert ctx.state["enrollments"][eid] == "needs_confirmation"
    _answer(ctx, "confirm_submit", {"event_id": eid, "confirmed_at": "2026-11-21T14:06:00+01:00"})
    second = asyncio.run(concierge.enroll(ctx))
    assert second["status"] == "registered" and calls[1]["confirmed_at"].startswith("2026-11-21T14:06")
    assert "error" in asyncio.run(concierge.enroll(ctx))  # registered: no third run


def test_web_form_declined_confirmation_sends_nothing(monkeypatch):
    ctx, eid = _web_ctx()
    _answer(ctx, "choose_event", {"event_id": eid, "approved_at": "2026-11-21T14:05:00+01:00"})
    calls = _runs(ctx, monkeypatch, [json.dumps({"event_id": eid, "status": "needs_confirmation", "message": "Planned"})])
    asyncio.run(concierge.enroll(ctx))
    _answer(ctx, "confirm_submit", {"event_id": eid, "declined": True})
    out = asyncio.run(concierge.enroll(ctx))
    assert "Not submitted" in out["message"] and len(calls) == 1
    assert ctx.state["enrollments"][eid] == "needs_confirmation"


def test_confirmation_for_another_event_is_ignored(monkeypatch):
    ctx, eid = _web_ctx()
    _answer(ctx, "choose_event", {"event_id": eid, "approved_at": "2026-11-21T14:05:00+01:00"})
    calls = _runs(ctx, monkeypatch, [json.dumps({"event_id": eid, "status": "needs_confirmation", "message": "P"})] * 2)
    asyncio.run(concierge.enroll(ctx))
    _answer(ctx, "confirm_submit", {"event_id": "other", "confirmed_at": "2026-11-21T14:06:00+01:00"})
    asyncio.run(concierge.enroll(ctx))
    assert calls[1]["confirmed_at"] is None


def _pctx(profile=None):
    return SimpleNamespace(state={"profile": dict(PROFILE if profile is None else profile, interests=["AI"], city="Münster", days_ahead=14)})


def test_update_profile_writes_state_and_audit():
    ctx = _pctx()
    out = concierge.update_profile(ctx, city="  Dortmund ", interests=["AI", " Techno", "techno", "ai"], days_ahead=7)
    assert out["ok"] and out["profile"] == {"city": "Dortmund", "interests": ["AI", "Techno"], "days_ahead": 7}
    p = ctx.state["profile"]
    assert (p["city"], p["interests"], p["days_ahead"]) == ("Dortmund", ["AI", "Techno"], 7)
    assert p["display_name"] == "Lea" and p["email"] == "lea@example.com" and p["consent_enrollment"] is True
    assert ctx.state["audit"][-1]["tool"] == "update_profile"


def test_update_profile_partial_keeps_other_fields():
    ctx = _pctx()
    assert concierge.update_profile(ctx, days_ahead=30)["ok"]
    assert ctx.state["profile"]["city"] == "Münster" and ctx.state["profile"]["interests"] == ["AI"]


def test_update_profile_invalid_changes_nothing():
    for kw in ({"city": "x" * 61}, {"city": "  "}, {"interests": [f"i{n}" for n in range(13)]}, {"interests": []},
               {"interests": ["x" * 41]}, {"days_ahead": 0}, {"days_ahead": 61}, {"days_ahead": True}, {}):
        ctx = _pctx()
        before = json.dumps(ctx.state["profile"])
        assert "error" in concierge.update_profile(ctx, **kw)
        assert json.dumps(ctx.state["profile"]) == before and "audit" not in ctx.state
    # valid city does not apply when interests are invalid
    ctx = _pctx()
    assert "error" in concierge.update_profile(ctx, city="Bonn", days_ahead=99)
    assert ctx.state["profile"]["city"] == "Münster"


def test_update_profile_cannot_touch_name_or_email():
    ctx = _pctx()
    try:
        concierge.update_profile(ctx, email="evil@example.com")  # not a parameter
        raise AssertionError("must reject unknown fields")
    except TypeError:
        pass
    assert ctx.state["profile"]["email"] == "lea@example.com"
