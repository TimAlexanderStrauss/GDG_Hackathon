"""Shared cache: guard verdicts, extraction per post, ranking merge, resolver results. All offline."""
import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

from agents.scouts import agent
from mcp_servers.event_sources import resolver, server
from shared import store

TODAY = date(2026, 11, 21)


@pytest.fixture(autouse=True)
def pinned_day(monkeypatch):
    class D(date):
        @classmethod
        def today(cls):
            return TODAY
    monkeypatch.setattr(agent, "date", D)


def post(c, text="Konzert im Hafen"):
    return {"url": f"https://www.instagram.com/p/{c}/", "text": text, "platform": "instagram", "posted_at": "2026-11-20T10:00:00Z"}


def ev(p, title, start="2026-11-28T20:00:00+01:00"):
    return agent.Event.model_validate({"id": "", "title": title, "platform": "instagram", "source_url": p["url"], "start": start})


@pytest.fixture
def llm(monkeypatch):
    """Mock structured(): one event per post, title "T<letter>"; records the urls it was asked about."""
    calls = []

    def fake(system, user, schema, small=True):
        assert small is False
        import json
        posts = json.loads(user.removeprefix("<posts>").removesuffix("</posts>"))
        calls.append([p["url"] for p in posts])
        return agent.Extracted(posts=[agent.PostEvents(url=p["url"], events=[ev(p, "T" + p["url"][-2])]) for p in posts])
    monkeypatch.setattr(agent, "structured", fake)
    return calls


def scan(posts, days=14):
    state = {"temp:posts_instagram": posts, "profile": {"days_ahead": days}}
    res = asyncio.run(agent._extract_events(SimpleNamespace(state=state)))
    return state, res


def test_second_scan_reuses_catalog_and_new_post_is_extracted_alone(llm):
    a, b = post("A"), post("B")
    state, _ = scan([a])
    assert len(llm) == 1 and [e["title"] for e in state["temp:candidates"]] == ["TA"]
    scan([a])
    assert len(llm) == 1  # warm: no extraction call
    state, _ = scan([a, b])
    assert llm[-1] == [b["url"]] and len(state["temp:candidates"]) == 2


def test_post_without_event_is_stored_empty_and_not_extracted_again(monkeypatch):
    calls = []
    monkeypatch.setattr(agent, "structured", lambda *a, **k: calls.append(1) or agent.Extracted(posts=[]))
    p = post("A")
    state, res = scan([p])
    scan([p])
    assert len(calls) == 1 and state["events"] == [] and res is not None  # no candidates: curator LLM is skipped


def test_failed_extraction_is_retried_and_noted(monkeypatch):
    monkeypatch.setattr(agent, "structured", lambda *a, **k: None)
    state, _ = scan([post("A")])
    assert state["scan_notes"] == ["error: event extraction failed for 1 posts"]
    assert store.get("events", agent._post_key(post("A"))) is None


def test_window_filter_keeps_start_none(monkeypatch):
    posts = [post(c) for c in "ABCD"]
    starts = {"A": "2026-11-20T20:00:00+01:00", "B": "2026-12-30T20:00:00+01:00", "C": None, "D": "2026-11-22T20:00:00+01:00"}
    monkeypatch.setattr(agent, "structured", lambda s, u, schema, small=True: agent.Extracted(posts=[
        agent.PostEvents(url=p["url"], events=[ev(p, "T" + p["url"][-2], starts[p["url"][-2]])]) for p in posts]))
    state, _ = scan(posts, days=14)
    assert sorted(e["title"] for e in state["temp:candidates"]) == ["TC", "TD"]


def test_ranking_merge_ignores_unknown_and_defaults_missing():
    cand = [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}, {"id": "c", "title": "C"}]
    state = {"temp:candidates": cand, "temp:ranked": {"items": [
        {"id": "a", "match_score": 0.4, "match_reason": "ok"}, {"id": "c", "match_score": 0.9, "match_reason": "best"},
        {"id": "zzz", "match_score": 1, "match_reason": "invented"}]}}
    agent._merge_ranking(SimpleNamespace(state=state))
    assert [(e["id"], e["match_score"], e["match_reason"]) for e in state["events"]] == [
        ("c", 0.9, "best"), ("a", 0.4, "ok"), ("b", 0, "")]


def test_guard_verdict_survives_new_engine_and_error_is_not_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "structured", lambda *a, **k: calls.append(1) or server.Verdict(injection=True, reason="x"))
    assert server.llm_flags("hello") is True
    store._engines.clear()  # new process, same DB
    assert server.llm_flags("hello") is True and len(calls) == 1

    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(server, "structured", boom)
    with pytest.raises(RuntimeError):
        server.llm_flags("other")
    monkeypatch.setattr(server, "structured", lambda *a, **k: server.Verdict(injection=False, reason=""))
    assert server.llm_flags("other") is False  # the error left nothing behind

    monkeypatch.setattr(server, "structured", lambda *a, **k: None)  # unreadable verdict
    assert server.llm_flags("third") is True  # blocked now (fail closed) ...
    monkeypatch.setattr(server, "structured", lambda *a, **k: server.Verdict(injection=False, reason=""))
    assert server.llm_flags("third") is False  # ... but not stored: checked again next time


def test_resolver_result_is_read_from_db(monkeypatch):
    def boom(*a):
        raise AssertionError("resolver must not run")
    monkeypatch.setattr(resolver, "_resolve", boom)
    key = __import__("hashlib").sha1(__import__("json").dumps(["https://a.example/t", "T", ""]).encode()).hexdigest()
    store.put("resolver", key, resolver._out("web_form", reg="https://r.example/x"))
    assert resolver.resolve_signup("https://a.example/t", "T", "")["registration_url"] == "https://r.example/x"
