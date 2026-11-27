"""Fetches real public Instagram and TikTok posts about events in any city via Apify, plus web pages via Firecrawl
search (only if FIRECRAWL_API_KEY is set: 1 query, 5 pages, about 7 credits per city), for DEMO_MODE=live.

Run: uv run python -m mcp_servers.event_sources.fetch_live --city "Köln"   (default: Münster)
Needs APIFY_TOKEN in .env. Takes 1-3 min and a few cents of Apify credit. Writes fixtures/live/<slug>.json
(slug = ascii form of the city, e.g. muenster), which search_posts reads instead of the demo fixtures. The server also
starts this fetch as a detached process when the cache of a city is missing or older than 24 h. Hashtags and the location
filter are derived from the city name (umlaut and ascii variants). The guard still checks every post at search time.
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone

import httpx
from pydantic import ValidationError

from mcp_servers.event_sources.server import DATE, ROOT, in_window
from shared.schemas import SocialPost

LIVE_DIR = ROOT / "fixtures" / "live"
PER_PLATFORM = 12  # every post costs one guard call (Gemini) per scan, keep the rate limit in mind


def variants(city: str) -> list[str]:
    """Name forms for the location filter (spaces kept): transliterated (ü→ue), umlaut, plain (ü→u)."""
    c = " ".join(city.casefold().split())
    forms = [c.translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})), c,
             c.translate(str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"}))]
    return [f for f in dict.fromkeys(forms) if f]


def _tag(v: str) -> str:
    return re.sub(r"[^a-z0-9äöüß]", "", v)


def slug(city: str) -> str:
    return re.sub(r"[^a-z0-9]", "", variants(city)[0]) if variants(city) else ""


def cache_path(city: str):
    if not slug(city):
        raise ValueError("city needs at least one letter a-z")
    return LIVE_DIR / f"{slug(city)}.json"


def hashtags(city: str) -> tuple[list[str], list[str]]:
    """(instagram max 4, tiktok max 3), e.g. muensterevents, münsterevents, eventsmuenster, muensterparty."""
    v = [t for x in variants(city) if (t := _tag(x))]
    ig = [t + "events" for t in v[:2]] + ["events" + v[0], v[0] + "party"]
    tt = [t + "events" for t in v[:2]] + [v[0]]
    return list(dict.fromkeys(ig))[:4], list(dict.fromkeys(tt))[:3]


def _run(actor: str, payload: dict) -> list[dict]:
    r = httpx.post(f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items", json=payload, timeout=300,
                   headers={"Authorization": f"Bearer {os.environ['APIFY_TOKEN']}"})  # header: the token never shows in error URLs
    r.raise_for_status()
    return r.json()


def instagram(city: str) -> list[dict]:
    items = _run("apify~instagram-hashtag-scraper", {"hashtags": hashtags(city)[0], "resultsType": "posts", "resultsLimit": 30})
    # venue-only location names ("Sputnikhalle") would fail the server's city filter, the curator checks the city
    return [{"platform": "instagram", "url": i.get("url"), "text": i.get("caption") or "", "posted_at": i.get("timestamp"),
             "location": loc if (loc := i.get("locationName")) and any(c in loc.lower() for c in variants(city)) else None,
             "owner": i.get("ownerUsername")}  # popped in main(): bio links are fetched only for the posts select keeps
            for i in items]


def _link(v) -> str | None:
    return v if isinstance(v, str) and v.startswith(("https://", "http://")) else None  # junk would fail SocialPost validation


def bio_links(owners: list[str]) -> dict[str, str]:
    """username -> bio link (externalUrl of apify~instagram-profile-scraper). Failure = no links, never an abort."""
    if not owners:
        return {}
    try:
        items = _run("apify~instagram-profile-scraper", {"usernames": owners})
    except (httpx.HTTPError, ValueError) as e:
        print(f"instagram profiles: failed ({type(e).__name__}), posts keep no bio link", file=sys.stderr)
        return {}
    return {i["username"]: u for i in items if i.get("username") and (u := _link(i.get("externalUrl")))}


def tiktok(city: str) -> list[dict]:
    items = _run("clockworks~tiktok-scraper", {"hashtags": hashtags(city)[1], "resultsPerPage": 30})
    return [{"platform": "tiktok", "url": i.get("webVideoUrl"), "text": i.get("text") or "",
             "posted_at": i.get("createTimeISO"), "location": None,
             "author_bio_url": _link((i.get("authorMeta") or {}).get("bioLink"))} for i in items]


def web(city: str) -> list[dict]:
    """One Firecrawl v2 search (past month, 5 results, pages scraped as markdown). 2 credits + 1 per page."""
    r = httpx.post("https://api.firecrawl.dev/v2/search", timeout=120,
                   headers={"Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY']}"},
                   json={"query": f"Events Veranstaltungen {city}", "limit": 5, "tbs": "qdr:m",  # any city: no country filter
                         "scrapeOptions": {"formats": ["markdown"], "onlyMainContent": True}})
    r.raise_for_status()
    data = r.json().get("data") or []
    items = data.get("web", []) if isinstance(data, dict) else data  # v2 docs show both shapes
    now = datetime.now(timezone.utc).isoformat()
    return [{"platform": "web", "url": i.get("url"), "posted_at": now, "location": None,
             "text": f"{i.get('title') or ''}\n{(i.get('markdown') or i.get('description') or '')[:4000]}"} for i in items]


def add_bio_links(chosen: list[SocialPost], raw: list[dict]) -> list[SocialPost]:
    owner_of = {r.get("url"): r.get("owner") for r in raw}
    links = bio_links(sorted({o for p in chosen if (o := owner_of.get(str(p.url)))}))
    return [SocialPost.model_validate({**p.model_dump(), "author_bio_url": u}) if (u := links.get(owner_of.get(str(p.url)))) else p
            for p in chosen]


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


def fetch(city: str) -> int:
    """Fetch, select and write fixtures/live/<slug>.json (also when empty). Returns the number of posts.
    Raises RuntimeError when no source answered."""
    if not os.getenv("APIFY_TOKEN"):
        raise RuntimeError("APIFY_TOKEN is empty in .env")
    out = cache_path(city)
    posts, answered = [], 0
    for source in (instagram, tiktok, web):
        if source is web and not os.getenv("FIRECRAWL_API_KEY"):
            continue
        try:
            raw = source(city)
        except (httpx.HTTPError, ValueError) as e:  # ValueError: bad JSON
            print(f"{source.__name__}: failed ({type(e).__name__} {getattr(getattr(e, 'response', None), 'status_code', '')})", file=sys.stderr)
            continue
        answered += 1
        chosen = select(raw, date.today())
        if source is instagram:
            chosen = add_bio_links(chosen, raw)
        print(f"{source.__name__}: {len(raw)} fetched, {len(chosen)} kept", file=sys.stderr)
        posts += chosen
    if not answered:
        raise RuntimeError(f"All sources failed, {out.name} unchanged")
    # an empty list is written too: a small city with no posts is known for 24 h instead of a new Apify run per scan
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([p.model_dump(mode="json") for p in posts], ensure_ascii=False, indent=1))
    print(f"wrote {len(posts)} posts to {out}", file=sys.stderr)
    return len(posts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="Münster")
    city = ap.parse_args().city
    try:
        fetch(city)
    except Exception as e:  # the detached run has no caller: leave a marker the server reads (never print e, token)
        from shared import store
        key = slug(city)
        if key:
            store.put("fetches", key, {**(store.get("fetches", key) or {}), "failed": time.time()})
        raise SystemExit(str(e) if isinstance(e, (RuntimeError, ValueError)) else f"fetch failed ({type(e).__name__})")


if __name__ == "__main__":
    main()
