"""_finalize_events: code sets the final signup kind, hint and dedup, whatever the curator LLM proposed."""
from types import SimpleNamespace

from agents.scouts.agent import _finalize_events
from shared.schemas import Event

CLUB = "Club Night im Hafen! Programm: DJ Foo, DJ Bar. Eintritt: 10,00€ Barzahlung an der Kasse"


def run(posts, **proposed):
    """posts: {url: text}; proposed: per url a dict of Event fields the LLM proposed."""
    events = [Event.model_validate({"id": "", "title": "Event " + url[-1], "venue": "Hafen", "city": "Münster",
                                    "platform": "instagram", "source_url": url, "start": "2026-11-28T23:00:00+01:00",
                                    **proposed.get(url, {})}) for url in posts]
    return _finalize_events(events, posts)


def one(text, **fields):
    return run({"https://www.instagram.com/p/A/": text}, **{"https://www.instagram.com/p/A/": fields})[0]


def test_none_stays_and_unbacked_message_is_not_message():
    assert one(CLUB, signup="none")["signup"] == "none"
    assert one(CLUB, signup="message")["signup"] == "unknown"


def test_market_with_entry_fee_is_none():
    assert one("Weihnachtsmarkt. 2 € Eintritt", signup="none")["signup"] == "none"


def test_link_in_bio_and_dm():
    assert one("Ticket Link in Bio", signup="link_in_bio")["signup"] == "link_in_bio"
    assert one("Ticket Link in Bio", signup="message")["signup"] == "unknown"
    assert one("Tickets nur per DM", signup="message")["signup"] == "message"
    assert one("Tickets nur per dm", signup="message")["signup"] == "unknown"  # DM is case-sensitive


def test_google_form_host_wins_and_llm_form_is_demoted():
    url = "https://forms.gle/abc"
    assert one(f"Anmeldung: {url}", signup="none", registration_url=url)["signup"] == "google_form"
    assert one("Anmeldung folgt", signup="google_form")["signup"] == "unknown"


def test_tickets_and_web_form_never_from_llm():
    assert one("Tickets hier", signup="tickets")["signup"] == "unknown"
    assert one("Ticket Link in Bio", signup="web_form")["signup"] == "link_in_bio"
    assert one("x", signup="tickets", ticket={"url": "https://shop.example/t", "checked_at": "2026-11-20T10:00:00Z"})["ticket"] is None


def test_signup_hint_must_be_a_quote():
    assert one(CLUB, signup="none", signup_hint="eintritt:  10,00€")["signup_hint"] == "eintritt:  10,00€"
    assert one(CLUB, signup="none", signup_hint="Eintritt frei")["signup_hint"] == ""


def test_same_event_in_three_posts_is_one_event():
    posts = {f"https://www.instagram.com/p/{c}/": CLUB for c in "ABC"}
    same = {"title": "Club Night!", "start": "2026-11-28T23:00:00+01:00"}
    assert len(run(posts, **{u: same for u in posts})) == 1


def test_event_without_venue_or_start_does_not_crash():
    assert one(CLUB, signup="none", venue=None, start=None)["signup"] == "none"


def test_resolver_step_sets_tickets_web_form_and_clears_link_in_bio(monkeypatch):
    import asyncio
    from agents.scouts import agent
    ticket = {"url": "https://shop.example/t/1", "price": "10.00 EUR", "availability": "available",
              "checked_at": "2026-11-23T10:00:00Z"}
    answers = {"https://bio.example/a": {"signup": "tickets", "ticket": ticket, "registration_url": None, "note": ""},
               "https://bio.example/b": {"signup": "web_form", "ticket": None, "registration_url": "https://reg.example/b", "note": ""}}
    calls = []
    monkeypatch.setattr(agent, "resolve_signup", lambda url, title, start: calls.append(url) or answers.get(url, {"signup": "unknown"}))
    posts = [{"url": f"https://www.instagram.com/p/{k}/", "text": "x", "author_bio_url": f"https://bio.example/{k.lower()}"}
             for k in "ABCD"]
    events = [{"id": k, "title": k, "platform": "instagram", "source_url": f"https://www.instagram.com/p/{k}/", "signup": kind}
              for k, kind in zip("ABCD", ["none", "link_in_bio", "link_in_bio", "message"])]
    state = {"temp:posts_instagram": posts, "events": events}
    asyncio.run(agent._resolve_signups(SimpleNamespace(state=state)))
    got = {e["id"]: e for e in state["events"]}
    assert got["A"]["signup"] == "tickets" and got["A"]["ticket"]["price"] == "10.00 EUR"  # door event, presale found in bio
    assert got["B"]["signup"] == "web_form" and got["B"]["registration_url"] == "https://reg.example/b"
    assert got["C"]["signup"] == "unknown"  # link_in_bio, nothing found
    assert got["D"]["signup"] == "message" and "https://bio.example/d" not in calls  # final kinds are not resolved


def test_none_without_presale_gets_note_but_keeps_quote(monkeypatch):
    import asyncio
    from agents.scouts import agent
    monkeypatch.setattr(agent, "resolve_signup", lambda *a: {"signup": "unknown"})
    events = [{"id": k, "title": k, "platform": "instagram", "source_url": f"https://www.instagram.com/p/{k}/",
               "signup": kind, "signup_hint": hint}
              for k, kind, hint in [("A", "none", ""), ("B", "none", "Eintritt frei"), ("C", "unknown", "")]]
    state = {"temp:posts_instagram": [], "events": events}
    asyncio.run(agent._resolve_signups(SimpleNamespace(state=state)))
    assert [e["signup_hint"] for e in state["events"]] == [agent.NO_PRESALE, "Eintritt frei", ""]


def test_scout_skip_is_decided_in_code():
    from agents.scouts.agent import _skip_unselected
    ctx = lambda name, profile: SimpleNamespace(agent_name=name, state={"profile": profile})  # noqa: E731
    assert _skip_unselected(ctx("tiktok_scout", {"platforms": ["instagram"]})).parts[0].text == "skipped"
    assert _skip_unselected(ctx("instagram_scout", {"platforms": ["instagram"]})) is None
    assert _skip_unselected(ctx("tiktok_scout", {"city": "Münster"})) is None  # no platforms field = all


def test_scan_notes_hold_only_this_scans_errors():
    from agents.scouts.agent import _merge_scout_state
    state = {"temp:audit_instagram": [{"note": "error: SOURCE_UNAVAILABLE: live data for Köln cannot be loaded: the live fetch failed"}],
             "temp:audit_tiktok": [{"note": "tiktok Köln 14d #x: 3 posts, 0 blocked"}], "scan_notes": ["old"]}
    _merge_scout_state(SimpleNamespace(state=state))
    assert state["scan_notes"] == ["error: SOURCE_UNAVAILABLE: live data for Köln cannot be loaded: the live fetch failed"]


def test_events_from_one_page_get_different_ids():
    url = "https://example.org/termine"
    events = [Event.model_validate({"id": "", "title": t, "venue": "Hafen", "city": "Münster", "platform": "web",
                                    "source_url": url, "start": "2026-11-28T23:00:00+01:00"})
              for t in ("Konzert A", "Konzert B")]
    assert len({e["id"] for e in _finalize_events(events, {url: "Termine"})}) == 2


def test_event_from_unfetched_post_and_foreign_registration_url_are_dropped():
    url = "https://www.instagram.com/p/A/"
    assert run({url: "x"}, **{url: {"source_url": "https://www.instagram.com/p/Z/"}}) == []
    assert one("Anmeldung folgt", registration_url="https://evil.example/x")["registration_url"] is None


def test_city_filter_in_code():
    from agents.scouts.agent import _in_city
    assert _in_city("Münster", "Muenster") and _in_city("Münster-Hiltrup", "Münster") and _in_city(None, "Münster")
    assert not _in_city("München", "Münster") and not _in_city("Köln", "Münster")
    assert _in_city("Frankfurt am Main", "frankfurt am main")


def test_curator_without_candidates_runs_through_adk_without_llm():
    """Regression: the skip content is validated by ADK against output_schema Ranked ("no events" crashed the scan)."""
    import asyncio

    from google.adk.runners import InMemoryRunner
    from google.genai import types

    from agents.scouts.agent import curator

    async def go():
        runner = InMemoryRunner(agent=curator, app_name="t")
        s = await runner.session_service.create_session(app_name="t", user_id="u",
                                                        state={"profile": {"city": "Emsdetten", "days_ahead": 14}})
        async for _ in runner.run_async(user_id="u", session_id=s.id,
                                        new_message=types.Content(role="user", parts=[types.Part(text="go")])):
            pass
        return (await runner.session_service.get_session(app_name="t", user_id="u", session_id=s.id)).state
    assert asyncio.run(go())["events"] == []


def test_scout_stops_after_a_source_error_but_may_fix_invalid_input():
    from agents.scouts.agent import _audit_search

    def ctx():
        return SimpleNamespace(agent_name="tiktok_scout", state={}, actions=SimpleNamespace(skip_summarization=False))
    err = lambda text: {"isError": True, "content": [{"text": text}]}  # noqa: E731
    c = ctx()
    _audit_search(SimpleNamespace(name="search_posts"), {}, c, err("SOURCE_UNAVAILABLE: live data for X cannot be loaded: x"))
    assert c.actions.skip_summarization is True  # no retry loop
    c = ctx()
    _audit_search(SimpleNamespace(name="search_posts"), {}, c, err("INVALID_INPUT: max. 3 hashtags"))
    assert c.actions.skip_summarization is False  # the model may fix the input


def test_same_event_with_differently_written_venue_is_one_event():
    from agents.scouts.agent import Event, _dedup_key
    a = Event(id="", title="Black Friday Vintage Pop-up", venue="Cuba Club", platform="tiktok",
              source_url="https://x.example/1", start="2026-11-27T15:00:00+01:00")
    b = a.model_copy(update={"venue": "Cuba Club Münster, Achtermannstraße", "source_url": "https://x.example/2"})
    assert _dedup_key(a) == _dedup_key(b)


def test_image_and_bio_come_from_the_post_not_from_the_llm(monkeypatch):
    import asyncio

    from agents.scouts import agent
    monkeypatch.setattr(agent, "resolve_signup", lambda *a: {"signup": "unknown"})
    url = "https://www.instagram.com/p/A/"
    got = run({url: CLUB}, **{url: {"image_url": "https://evil.example/x.png", "bio_url": "https://evil.example/b",
                                    "summary": "x" * 400}})[0]
    assert got["image_url"] is None and got["bio_url"] is None and len(got["summary"]) == 300
    state = {"temp:posts_instagram": [{"url": url, "text": "x", "image_url": "https://cdn.example/a.jpg",
                                       "author_bio_url": "https://bio.example/a"}], "events": [got, {**got, "id": "2", "source_url": "https://www.instagram.com/p/Z/", "image_url": "https://evil.example/x.png"}]}
    asyncio.run(agent._resolve_signups(SimpleNamespace(state=state)))
    assert state["events"][0]["image_url"] == "https://cdn.example/a.jpg" and state["events"][0]["bio_url"] is None  # resolver found no event page
    assert state["events"][1]["image_url"] is None  # post without image: the LLM value is overwritten


def test_listing_events_get_original_and_never_the_listing_image(monkeypatch):
    import asyncio
    from agents.scouts import agent
    L, S = "https://www.agg.example/events/hamburg", "https://www.solo.example/e"
    monkeypatch.setattr(agent, "find_original", lambda url, text, title, start: {
        "url": "https://lu.example.org/a", "image_url": "https://img.example.org/a.jpg", "note": ""}
        if title == "A" else {"url": None, "image_url": None, "note": ""})
    monkeypatch.setattr(agent, "resolve_signup", lambda url, *a: {"signup": "web_form", "registration_url": url, "ticket": None})
    posts = [{"url": u, "text": "x", "image_url": "https://agg.example/ad.png"} for u in (L, S)]
    mk = lambda i, t, u: {"id": i, "title": t, "platform": "web", "source_url": u, "signup": "unknown",
                          "sources": [{"platform": "web", "url": u}]}
    state = {"temp:posts_web": posts, "temp:listings": [L],
             "events": [mk("1", "A", L), mk("2", "B", L), mk("3", "C", S)]}
    asyncio.run(agent._resolve_signups(SimpleNamespace(state=state)))
    a, b, c = state["events"]
    assert a["source_url"] == "https://lu.example.org/a" and a["image_url"] == "https://img.example.org/a.jpg"
    assert [x["url"] for x in a["sources"]] == ["https://lu.example.org/a"] and a["id"] == "1"
    assert a["signup"] == "web_form"  # normal resolver ran on the found url
    assert b["source_url"] == L and b["image_url"] is None
    assert c["image_url"] == "https://agg.example/ad.png"  # single-event page is no listing
    assert any("original found: lu.example.org" in e["note"] for e in state["audit"])


def test_social_listing_uses_search_for_first_12_events_only(monkeypatch):
    import asyncio
    from agents.scouts import agent
    L = "https://www.instagram.com/p/list/"
    searched = []
    monkeypatch.setattr(agent, "search_original", lambda title, venue, city, start, host: searched.append(title) or {
        "url": "https://lu.example.org/" + title, "image_url": "https://img.example.org/a.jpg", "note": ""})
    monkeypatch.setattr(agent, "resolve_signup", lambda url, *a: {"signup": "unknown"})
    state = {"temp:posts_instagram": [{"url": L, "text": "x", "image_url": "https://insta.example/list.jpg"}],
             "temp:listings": [L],
             "events": [{"id": str(i), "title": f"T{i}", "platform": "instagram", "source_url": L, "signup": "unknown",
                         "sources": [{"platform": "instagram", "url": L}]} for i in range(14)]}
    asyncio.run(agent._resolve_signups(SimpleNamespace(state=state)))
    ev = state["events"]
    assert searched == [f"T{i}" for i in range(12)] or sorted(searched) == sorted(f"T{i}" for i in range(12))
    assert ev[0]["source_url"] == "https://lu.example.org/T0" and ev[0]["image_url"] == "https://img.example.org/a.jpg"
    assert ev[13]["source_url"] == L and ev[13]["image_url"] is None  # never the list graphic
    assert any("via search: lu.example.org" in e["note"] for e in state["audit"])


def test_bio_url_only_for_a_verified_event_page(monkeypatch):
    import asyncio
    from agents.scouts import agent
    ticket = {"url": "https://shop.example/t/1", "price": "10.00 EUR", "availability": "available", "checked_at": "2026-11-23T10:00:00Z"}
    answers = {"https://bio.example/a": {"signup": "unknown", "event_page": "https://bio.example/a/event"},
               "https://bio.example/b": {"signup": "tickets", "ticket": ticket, "event_page": "https://bio.example/b/e"},
               "https://bio.example/c": {"signup": "unknown", "event_page": None}}
    monkeypatch.setattr(agent, "resolve_signup", lambda url, *a: answers[url])
    posts = [{"url": f"https://www.instagram.com/p/{k}/", "text": "x", "author_bio_url": f"https://bio.example/{k.lower()}"} for k in "ABCD"]
    events = [{"id": k, "title": k, "platform": "instagram", "source_url": f"https://www.instagram.com/p/{k}/", "signup": kind,
               "bio_url": "https://evil.example/b"} for k, kind in zip("ABCD", ["link_in_bio", "link_in_bio", "link_in_bio", "message"])]
    state = {"temp:posts_instagram": posts, "events": events}
    asyncio.run(agent._resolve_signups(SimpleNamespace(state=state)))
    assert [e["bio_url"] for e in state["events"]] == ["https://bio.example/a/event", None, None, None]


def test_weak_best_match_adds_a_scan_note_and_code_sets_the_platform():
    from agents.scouts.agent import _merge_ranking, _merge_scout_state, _own_platform
    state = {"temp:candidates": [{"id": "a", "title": "Rave"}], "temp:ranked": {"items": [{"id": "a", "match_score": 0.1}]}}
    _merge_ranking(SimpleNamespace(state=state))
    assert state["scan_notes"] == ["info: no event matches the interests well (best match 10 %)"]
    state = {"temp:ranked": {"items": [{"id": "a", "match_score": 0.8}]}, "temp:candidates": [{"id": "a"}]}
    _merge_ranking(SimpleNamespace(state=state))
    assert "scan_notes" not in state
    args = {"platform": "instagram"}
    _own_platform(None, args, SimpleNamespace(agent_name="web_scout"))
    assert args["platform"] == "web"
    audit = {"temp:audit_web": [{"note": "web X 14d #a: 1 posts, 0 blocked; warning: no new live posts (daily limit)"}]}
    _merge_scout_state(SimpleNamespace(state=audit))
    assert audit["scan_notes"] == ["warning: no new live posts (daily limit)"]
