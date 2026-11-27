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
    state = {"temp:audit_instagram": [{"note": "error: SOURCE_UNAVAILABLE: live data for Köln is loading"}],
             "temp:audit_tiktok": [{"note": "tiktok Köln 14d #x: 3 posts, 0 blocked"}], "scan_notes": ["old"]}
    _merge_scout_state(SimpleNamespace(state=state))
    assert state["scan_notes"] == ["error: SOURCE_UNAVAILABLE: live data for Köln is loading"]


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
    _audit_search(SimpleNamespace(name="search_posts"), {}, c, err("SOURCE_UNAVAILABLE: live data for X is loading"))
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
