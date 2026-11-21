"""Fetches real public Instagram and TikTok posts about events in Münster via Apify, for DEMO_MODE=live.

Run: uv run python -m mcp_servers.event_sources.fetch_live
Needs APIFY_TOKEN in .env. Takes 1-3 min and a few cents of Apify credit. Writes fixtures/live_posts.json,
which search_posts reads instead of the demo fixtures. The guard still checks every post at search time.
"""
import json
import os
from datetime import date, datetime, timedelta, timezone

import httpx
from pydantic import ValidationError

from mcp_servers.event_sources.server import DATE, ROOT, in_window
from shared.schemas import SocialPost

OUT = ROOT / "fixtures" / "live_posts.json"
CITY_NAMES = ("münster", "muenster", "munster")
IG_TAGS = ["muensterevents", "münsterevents", "eventsmünster", "münsterparty"]
TT_TAGS = ["muensterevents", "münsterevents", "münster"]
PER_PLATFORM = 12  # every post costs one guard call (Gemini) per scan, keep the rate limit in mind


def _run(actor: str, payload: dict) -> list[dict]:
    r = httpx.post(f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items", json=payload, timeout=300,
                   headers={"Authorization": f"Bearer {os.environ['APIFY_TOKEN']}"})  # header: the token never shows in error URLs
    r.raise_for_status()
    return r.json()


def instagram() -> list[dict]:
    items = _run("apify~instagram-hashtag-scraper", {"hashtags": IG_TAGS, "resultsType": "posts", "resultsLimit": 30})
    # venue-only location names ("Sputnikhalle") would fail the server's city filter, the curator checks the city
    return [{"platform": "instagram", "url": i.get("url"), "text": i.get("caption") or "", "posted_at": i.get("timestamp"),
             "location": loc if (loc := i.get("locationName")) and any(c in loc.lower() for c in CITY_NAMES) else None}
            for i in items]


def tiktok() -> list[dict]:
    items = _run("clockworks~tiktok-scraper", {"hashtags": TT_TAGS, "resultsPerPage": 30})
    return [{"platform": "tiktok", "url": i.get("webVideoUrl"), "text": i.get("text") or "",
             "posted_at": i.get("createTimeISO"), "location": None} for i in items]


def select(raw: list[dict], today: date) -> list[SocialPost]:
    """Recent posts that name a date in the next 60 days (= event announcements), newest first."""
    since = datetime.now(timezone.utc) - timedelta(days=30)
    picked = {}
    for r in raw:
        try:
            p = SocialPost.model_validate(r)
        except ValidationError:
            continue
        posted = p.posted_at if p.posted_at.tzinfo else p.posted_at.replace(tzinfo=timezone.utc)
        if posted >= since and DATE.search(p.text) and in_window(p.text, today, 60):
            picked.setdefault(str(p.url), p)
    return sorted(picked.values(), key=lambda p: p.posted_at, reverse=True)[:PER_PLATFORM]


def main() -> None:
    if not os.getenv("APIFY_TOKEN"):
        raise SystemExit("APIFY_TOKEN is empty in .env")
    posts = []
    for source in (instagram, tiktok):
        try:
            raw = source()
        except httpx.HTTPError as e:
            print(f"{source.__name__}: failed ({type(e).__name__} {getattr(getattr(e, 'response', None), 'status_code', '')})")
            continue
        chosen = select(raw, date.today())
        print(f"{source.__name__}: {len(raw)} fetched, {len(chosen)} kept")
        posts += chosen
    if not posts:
        raise SystemExit(f"No posts kept, {OUT.name} unchanged")
    OUT.write_text(json.dumps([p.model_dump(mode="json") for p in posts], ensure_ascii=False, indent=1))
    print(f"wrote {len(posts)} posts to {OUT}")


if __name__ == "__main__":
    main()
