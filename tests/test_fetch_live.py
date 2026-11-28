import json
from datetime import date, datetime, timedelta, timezone

import pytest

from mcp_servers.event_sources.fetch_live import select


def test_select_keeps_only_recent_posts_with_upcoming_date():
    now, old = datetime.now(timezone.utc), datetime.now(timezone.utc) - timedelta(days=90)
    soon = (date.today() + timedelta(days=5)).strftime("%d.%m.")
    post = lambda code, text, at: {"platform": "instagram", "url": f"https://www.instagram.com/p/{code}/",
                                   "text": text, "posted_at": at.isoformat()}
    raw = [post("a", f"Party am {soon} 22 Uhr", now), post("b", "no date here", now),
           post("c", f"Party am {soon}", old), {"platform": "instagram", "url": None, "text": "x", "posted_at": "x"}]
    assert [str(p.url) for p in select(raw, date.today())] == ["https://www.instagram.com/p/a/"]


def test_instagram_bio_links_only_for_kept_posts_and_failure_is_harmless(monkeypatch):
    import httpx

    from mcp_servers.event_sources import fetch_live
    soon = (date.today() + timedelta(days=5)).strftime("%d.%m.")
    now = datetime.now(timezone.utc).isoformat()
    raw = [{"platform": "instagram", "url": f"https://www.instagram.com/p/{c}/", "text": t, "posted_at": now, "owner": o}
           for c, t, o in [("a", f"Party {soon}", "club_a"), ("b", "no date", "club_b")]]
    calls = []

    def fake_run(actor, payload):
        calls.append((actor, payload))
        return [{"username": "club_a", "externalUrl": "https://linktr.ee/club_a"}, {"username": "club_b", "externalUrl": "junk"}]
    monkeypatch.setattr(fetch_live, "_run", fake_run)
    chosen = fetch_live.add_bio_links(fetch_live.select(raw, date.today()), raw)
    assert calls == [("apify~instagram-profile-scraper", {"usernames": ["club_a"]})]
    assert str(chosen[0].author_bio_url) == "https://linktr.ee/club_a"

    def boom(actor, payload):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(fetch_live, "_run", boom)
    assert fetch_live.bio_links(["x"]) == {}


def test_tiktok_bio_link_from_author_meta(monkeypatch):
    from mcp_servers.event_sources import fetch_live
    monkeypatch.setattr(fetch_live, "_run", lambda a, p: [
        {"webVideoUrl": "https://www.tiktok.com/@a/video/1", "text": "x", "createTimeISO": "2026-01-01T00:00:00Z",
         "authorMeta": {"bioLink": "https://example.org/a"}},
        {"webVideoUrl": "https://www.tiktok.com/@b/video/2", "text": "y", "createTimeISO": "2026-01-01T00:00:00Z",
         "authorMeta": {"bioLink": "not a url"}}])
    a, b = fetch_live.tiktok("Münster", ["muensterevents"])
    assert a["author_bio_url"] == "https://example.org/a" and b["author_bio_url"] is None


def test_variants_hashtags_and_cache_path():
    from mcp_servers.event_sources import fetch_live as f
    assert f.variants("Münster") == ["muenster", "münster", "munster"]
    assert f.hashtags("Münster") == (["muensterevents", "münsterevents", "eventsmuenster", "muensterparty"],
                                     ["muensterevents", "münsterevents", "muenster"])
    assert f.variants("Köln")[:2] == ["koeln", "köln"] and f.hashtags("Köln")[1][0] == "koelnevents"
    assert f.variants("Frankfurt am Main") == ["frankfurt am main"]  # spaces kept for the location filter
    assert f.hashtags("Frankfurt am Main")[0] == ["frankfurtammainevents", "eventsfrankfurtammain", "frankfurtammainparty"]
    assert f.cache_path("Frankfurt am Main").name == "frankfurtammain.json"
    assert f.cache_path("Münster") == f.LIVE_DIR / "muenster.json"
    assert f.variants("Weiß-Stadt")[0] == "weiss-stadt" and f._tag("weiß-stadt") == "weißstadt"


def test_fetch_writes_the_city_file(monkeypatch, tmp_path, capsys):
    from mcp_servers.event_sources import fetch_live as f
    monkeypatch.setattr(f, "LIVE_DIR", tmp_path)
    monkeypatch.setenv("APIFY_TOKEN", "x")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)  # a key in .env must not trigger a live call
    soon = (date.today() + timedelta(days=5)).strftime("%d.%m.")
    now = datetime.now(timezone.utc).isoformat()
    calls = []

    def fake_run(actor, payload):
        calls.append((actor, payload))
        if actor == "apify~instagram-hashtag-scraper":
            return [{"url": "https://www.instagram.com/p/a/", "caption": f"Party {soon}", "timestamp": now,
                     "locationName": "Koeln Club"}]
        return []
    monkeypatch.setattr(f, "_run", fake_run)
    assert f.fetch("Köln") == 1
    assert calls[0][1]["hashtags"][0] == "koelnevents"
    assert (tmp_path / "koeln.json").exists()
    assert capsys.readouterr().out == ""  # the server runs fetch() in its process: stdout is the MCP stdio channel


def _web_setup(monkeypatch, tmp_path, key):
    from mcp_servers.event_sources import fetch_live as f
    monkeypatch.setattr(f, "LIVE_DIR", tmp_path)
    monkeypatch.setenv("APIFY_TOKEN", "x")
    monkeypatch.setattr(f, "_run", lambda a, p: [{"url": "https://www.instagram.com/p/a/", "caption": f"Party {SOON}",
                                                   "timestamp": datetime.now(timezone.utc).isoformat()}] if "hashtag" in a else [])
    monkeypatch.setenv("FIRECRAWL_API_KEY", "secret") if key else monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    return f


SOON = (date.today() + timedelta(days=5)).strftime("%d.%m.")


def test_web_source_posts_land_in_city_file(monkeypatch, tmp_path):
    import httpx
    f = _web_setup(monkeypatch, tmp_path, True)
    sent = []

    def post(url, **kw):
        sent.append((url, kw))
        body = {"data": {"web": [{"url": "https://example.org/a", "title": "Termine", "markdown": f"Konzert am {SOON} 20 Uhr"}]}}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))
    monkeypatch.setattr(f.httpx, "post", post)
    assert f.fetch("Köln") == 2
    assert sent[0][0].endswith("/v2/search") and "Köln" in sent[0][1]["json"]["query"]
    assert "secret" in sent[0][1]["headers"]["Authorization"]
    assert {p["platform"] for p in json.loads((tmp_path / "koeln.json").read_text())} == {"instagram", "web"}


def test_web_source_skipped_without_key_and_failure_is_harmless(monkeypatch, tmp_path, capsys):
    import httpx
    f = _web_setup(monkeypatch, tmp_path, False)
    monkeypatch.setattr(f.httpx, "post", lambda *a, **k: pytest.fail("Firecrawl called without key"))
    assert f.fetch("Köln") == 1
    monkeypatch.setenv("FIRECRAWL_API_KEY", "secret")

    def boom(*a, **k):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(f.httpx, "post", boom)
    assert f.fetch("Köln") == 1
    cap = capsys.readouterr()
    assert "web: failed" in cap.err and "secret" not in cap.err and cap.out == ""


def test_city_without_posts_gets_an_empty_cache_but_all_failed_raises(monkeypatch, tmp_path):
    import httpx
    import pytest
    from mcp_servers.event_sources import fetch_live as f
    monkeypatch.setattr(f, "LIVE_DIR", tmp_path)
    monkeypatch.setenv("APIFY_TOKEN", "x")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.setattr(f, "_run", lambda actor, payload: [])  # sources answer, nothing to keep
    assert f.fetch("Emsdetten") == 0 and (tmp_path / "emsdetten.json").read_text().strip() == "[]"

    def down(actor, payload):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(f, "_run", down)
    with pytest.raises(RuntimeError):
        f.fetch("Greven")
    assert not (tmp_path / "greven.json").exists()  # retried on the next scan


def test_interest_tags_are_fetched_with_the_city_and_add_merges(monkeypatch, tmp_path):
    from mcp_servers.event_sources import fetch_live as f
    from shared import store
    monkeypatch.setattr(f, "LIVE_DIR", tmp_path)
    monkeypatch.setenv("APIFY_TOKEN", "x")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    now = datetime.now(timezone.utc).isoformat()
    calls = []

    def fake_run(actor, payload):
        calls.append(payload["hashtags"])
        code = payload["hashtags"][0]
        return [{"url": f"https://www.instagram.com/p/{code}/", "caption": f"Party {SOON}", "timestamp": now}] \
            if "hashtag" in actor else []
    monkeypatch.setattr(f, "_run", fake_run)
    assert f.interest_tags("Köln", ["techno"]) == ["koelntechno"]
    assert f.fetch("Köln", ["techno"]) == 2  # city posts and interest posts, selected separately
    assert ["koelntechno"] in calls and store.get("fetches", "tags-koeln") == ["techno"]
    calls.clear()
    assert f.fetch("Köln", ["jazz"], add=True) == 3  # only the new tag is fetched, the cache is kept
    assert calls == [["koelnjazz"], ["koelnjazz"]]
    assert store.get("fetches", "tags-koeln") == ["techno", "jazz"]
    assert f.fetch("Köln", ["jazz"], add=True) == 3  # the same post again: no duplicate


def test_image_url_per_source(monkeypatch):
    from mcp_servers.event_sources import fetch_live
    monkeypatch.setattr(fetch_live, "_run", lambda a, p: [
        {"url": "https://www.instagram.com/p/a/", "caption": "x", "timestamp": "2026-01-01T00:00:00Z", "displayUrl": "https://cdn.example/a.jpg"},
        {"url": "https://www.instagram.com/p/b/", "caption": "x", "timestamp": "2026-01-01T00:00:00Z", "displayUrl": "junk"}])
    assert [i["image_url"] for i in fetch_live.instagram("Münster", ["x"])] == ["https://cdn.example/a.jpg", None]
    monkeypatch.setattr(fetch_live, "_run", lambda a, p: [
        {"webVideoUrl": "https://www.tiktok.com/@a/video/1", "videoMeta": {"coverUrl": "https://cdn.example/c.jpg"}},
        {"webVideoUrl": "https://www.tiktok.com/@a/video/2", "videoMeta": None}])
    assert [i["image_url"] for i in fetch_live.tiktok("Münster", ["x"])] == ["https://cdn.example/c.jpg", None]

    import httpx
    monkeypatch.setenv("FIRECRAWL_API_KEY", "k")
    items = [{"url": "https://example.org/a", "metadata": {"ogImage": "https://example.org/og.png"}},
             {"url": "https://example.org/b", "metadata": {"og:image": "https://example.org/og2.png"}},
             {"url": "https://example.org/c"}]
    monkeypatch.setattr(fetch_live.httpx, "post", lambda url, **kw: httpx.Response(
        200, json={"data": {"web": items}}, request=httpx.Request("POST", url)))
    assert [i["image_url"] for i in fetch_live.web("Münster", "q")] == [
        "https://example.org/og.png", "https://example.org/og2.png", None]


@pytest.mark.parametrize("text,want", [
    ("Party am 05.12. ab 22 Uhr", date(2026, 12, 5)), ("Sa, 5. Dezember 2026", date(2026, 12, 5)),
    ("am 5. Dez. im Club", date(2026, 12, 5)), ("5 Dec · 20:00", date(2026, 12, 5)), ("Dec 5th, doors 8pm", date(2026, 12, 5)),
    ("Sonntag 10. Januar", date(2027, 1, 10)), ("Konzert im März: 14 März", date(2027, 3, 14)),
    ("ab 19.30 Uhr, kein Datum", None), ("Eintritt 5 Euro", None), ("31. Februar", None),
])
def test_first_date_reads_german_and_english_dates(text, want):
    from mcp_servers.event_sources.server import first_date
    assert first_date(text, date(2026, 11, 28)) == want


def test_tiktok_profile_call_only_for_kept_posts_without_bio_link_and_failure_is_harmless(monkeypatch):
    import httpx

    from mcp_servers.event_sources import fetch_live
    soon = (date.today() + timedelta(days=5)).strftime("%d.%m.")
    now = datetime.now(timezone.utc).isoformat()
    raw = [{"platform": "tiktok", "url": f"https://www.tiktok.com/@{o}/video/{n}", "text": t, "posted_at": now, "owner": o,
            "author_bio_url": b} for n, o, t, b in [(1, "a", f"Party {soon}", None), (2, "b", "no date", None),
                                                    (3, "c", f"Party {soon}", "https://own.example/c")]]
    calls = []

    def fake_run(actor, payload):
        calls.append((actor, payload))
        return [{"authorMeta": {"name": "a", "bioLink": "https://linktr.ee/a"}}, {"authorMeta": {"name": "b", "bioLink": "junk"}}]
    monkeypatch.setattr(fetch_live, "_run", fake_run)
    chosen = fetch_live.add_bio_links(fetch_live.select(raw, date.today()), raw, fetch_live.tiktok_bio_links)
    assert calls == [("clockworks~tiktok-profile-scraper", {"profiles": ["a"], "resultsPerPage": 1})]
    assert {p.url.path.split("/")[-1]: str(p.author_bio_url) for p in chosen} == {"1": "https://linktr.ee/a", "3": "https://own.example/c"}

    def boom(actor, payload):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(fetch_live, "_run", boom)
    assert fetch_live.tiktok_bio_links(["x"]) == {}


def test_instagram_bio_link_falls_back_to_external_urls(monkeypatch):
    from mcp_servers.event_sources import fetch_live
    monkeypatch.setattr(fetch_live, "_run", lambda a, p: [
        {"username": "a", "externalUrl": None, "externalUrls": [{"title": "Tickets", "url": "https://shop.example.org/a"}]},
        {"username": "b", "externalUrl": "https://b.example.org", "externalUrls": [{"url": "https://other.example.org"}]}])
    assert fetch_live.bio_links(["a", "b"]) == {"a": "https://shop.example.org/a", "b": "https://b.example.org"}


def test_instagram_image_falls_back_to_images_and_child_posts():
    from mcp_servers.event_sources.fetch_live import _ig_image
    assert _ig_image({"displayUrl": "https://cdn.example.org/a.jpg", "images": ["https://cdn.example.org/b.jpg"]}) == "https://cdn.example.org/a.jpg"
    assert _ig_image({"displayUrl": None, "images": ["junk", "https://cdn.example.org/b.jpg"]}) == "https://cdn.example.org/b.jpg"
    assert _ig_image({"childPosts": [{"displayUrl": "https://cdn.example.org/c.jpg"}]}) == "https://cdn.example.org/c.jpg"
    assert _ig_image({}) is None
