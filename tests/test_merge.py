"""_merge_events: the same event in several posts or on several platforms shows once (code rule, no LLM)."""
import asyncio
from types import SimpleNamespace

from agents.scouts import agent
from agents.scouts.agent import _merge_events
from shared.schemas import Event

TT = "https://www.tiktok.com/@thealbanianparty/video/"


def ev(n, title, start="2026-12-11T21:00:00+01:00", venue="Electrum Club Köln", platform="tiktok", url=None, **kw):
    return Event.model_validate({"id": f"id{n}", "title": title, "venue": venue, "city": "Köln", "platform": platform,
                                 "source_url": url or f"{TT}{n}", "start": start, **kw})


def test_three_dardan_posts_are_one_event_with_the_link_in_bio_signup():
    events = [ev(1, "DARDAN x ALBA EVENTS", venue="Electrum Club Köln", signup="unknown"),
              ev(2, "DARDAN x THE ALBANIAN PARTY", venue="Electrum Club", signup="link_in_bio", signup_hint="Link in der Bio"),
              ev(3, "BLACK FRIDAY? NEIN – DARDAN FRIDAY!!", venue="Electrum Club Köln", start="2026-12-11T00:00:00+01:00")]
    [m] = _merge_events(events, "Köln")
    assert m.id == "id2" and m.signup == "link_in_bio" and m.signup_hint == "Link in der Bio"
    assert [str(s.url) for s in m.sources] == [f"{TT}2", f"{TT}1", f"{TT}3"] and str(m.source_url) == f"{TT}2"
    assert m.venue == "Electrum Club Köln"


def test_same_title_on_two_days_stays_two_events():
    assert len(_merge_events([ev(1, "Dardan Night"), ev(2, "Dardan Night", start="2026-12-12T21:00:00+01:00")], "Köln")) == 2


def test_same_club_same_day_needs_close_times_and_a_shared_word():
    assert len(_merge_events([ev(1, "Dardan Night"), ev(2, "Dardan Night Vol 2", start="2026-12-11T23:00:00+01:00")], "Köln")) == 2
    assert len(_merge_events([ev(1, "Dardan Night"), ev(2, "Lauftreff am Rhein")], "Köln")) == 2
    assert len(_merge_events([ev(1, "Dardan Night"), ev(2, "Techno Party", venue="Gloria")], "Köln")) == 2
    assert len(_merge_events([ev(1, "Dardan Night"), ev(2, "Dardan Special", start="2026-12-11T21:45:00+01:00")], "Köln")) == 1


def test_cross_platform_merge_takes_web_image_and_longer_summary(monkeypatch):
    monkeypatch.setattr(agent, "resolve_signup", lambda *a: {"signup": "unknown"})
    ig = ev(1, "Dip Dye Workshop", platform="instagram", url="https://www.instagram.com/p/A/", venue="Atelier Bunt",
            summary="Färbe dein eigenes Shirt mit Dip Dye.", signup="none")
    web = ev(2, "DIY Workshop: Dip Dye & Bloom Bar", platform="web", url="https://shop.example/dip", venue="Atelier Bunt, Köln",
             summary="Dip Dye", signup="none")
    [m] = _merge_events([ig, web], "Köln")
    assert m.summary == ig.summary and m.venue == "Atelier Bunt, Köln" and len(m.sources) == 2
    state = {"temp:posts_instagram": [{"url": str(ig.source_url), "text": "x"}],
             "temp:posts_web": [{"url": "https://shop.example/dip", "text": "x", "image_url": "https://shop.example/i.jpg"}],
             "events": [m.model_dump(mode="json")]}
    asyncio.run(agent._resolve_signups(SimpleNamespace(state=state)))
    assert state["events"][0]["image_url"] == "https://shop.example/i.jpg"


def test_resolver_uses_the_bio_link_of_any_source(monkeypatch):
    calls = []
    monkeypatch.setattr(agent, "resolve_signup", lambda url, *a: calls.append(url) or {"signup": "unknown"})
    [m] = _merge_events([ev(1, "Dardan Night", signup="link_in_bio"), ev(2, "Dardan Party")], "Köln")
    state = {"temp:posts_tiktok": [{"url": f"{TT}1", "text": "x"}, {"url": f"{TT}2", "text": "x", "author_bio_url": "https://bio.example/b"}],
             "events": [m.model_dump(mode="json")]}
    asyncio.run(agent._resolve_signups(SimpleNamespace(state=state)))
    assert calls == ["https://bio.example/b"] and state["events"][0]["bio_url"] == "https://bio.example/b"
