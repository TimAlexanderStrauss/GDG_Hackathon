from datetime import date, datetime, timedelta, timezone

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
    a, b = fetch_live.tiktok()
    assert a["author_bio_url"] == "https://example.org/a" and b["author_bio_url"] is None
