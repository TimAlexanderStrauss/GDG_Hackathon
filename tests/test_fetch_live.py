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
