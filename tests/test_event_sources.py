import sys
import time
from datetime import date

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mcp_servers.event_sources import server


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(server, "today", lambda: date(2026, 11, 21))  # demo day
    monkeypatch.setattr(server, "FIXTURES", server.ROOT / "fixtures" / "posts.json")
    monkeypatch.setattr(server, "LIVE", False)  # also with DEMO_MODE=live
    monkeypatch.setattr(server, "llm_flags", lambda text: False)  # regex layer only, no Gemini call
    monkeypatch.setattr(server, "GUARD", "gemini")  # also when .env says model_armor


def test_poisoned_post_is_blocked():
    r = server.search_posts("instagram", "Münster", ["ai", "#Techno"], 14)
    texts = " ".join(p.text for p in r.posts)
    assert r.blocked == 1
    assert "ignore all previous instructions" not in texts
    assert "AI & Agents Meetup" in texts and "TECHNO NIGHT" in texts and "Jazz Jam" in texts
    assert "Berlin" not in texts  # city filter
    assert r.note == "Results may be incomplete"


def test_date_window():
    r = server.search_posts("tiktok", "Münster", [], 8)  # 29.11. is in, Glühweinlauf on 04.12. is out
    assert [p.text[:12] for p in r.posts] == ["Nachtflohmar", "Recap vom Li"]


@pytest.mark.parametrize("tags", [["a", "b", "c", "d"], ["two words"], ["drop;table"]])
def test_invalid_hashtags(tags):
    with pytest.raises(ToolError, match="INVALID_INPUT"):
        server.search_posts("instagram", "Münster", tags, 14)


def test_model_armor_guard_replaces_gemini_and_fails_closed(monkeypatch):
    base = server.search_posts("instagram", "Münster", ["ai"], 14)
    monkeypatch.setattr(server, "GUARD", "model_armor")
    monkeypatch.setattr(server, "armor_flags", lambda text: True)
    r = server.search_posts("instagram", "Münster", ["ai"], 14)
    assert r.posts == [] and r.blocked == base.blocked + len(base.posts)

    def down(text):
        raise server.gapi_errors.ServiceUnavailable("down")
    monkeypatch.setattr(server, "armor_flags", down)
    with pytest.raises(ToolError, match="SOURCE_UNAVAILABLE"):
        server.search_posts("instagram", "Münster", ["ai"], 14)


@pytest.fixture
def live(monkeypatch, tmp_path):
    from mcp_servers.event_sources import fetch_live
    monkeypatch.setattr(server, "LIVE", True)
    monkeypatch.setattr(fetch_live, "LIVE_DIR", tmp_path)
    monkeypatch.setenv("APIFY_TOKEN", "x")
    spawned = []
    monkeypatch.setattr(server, "_spawn", lambda city, *a: spawned.append(city))  # no process, no Apify
    return tmp_path, spawned


def test_live_missing_cache_starts_one_fetch(live):
    _, spawned = live
    for _ in range(3):  # three parallel scouts
        with pytest.raises(ToolError, match="SOURCE_UNAVAILABLE: live data for Köln is loading"):
            server.search_posts("instagram", "Köln", [], 14)
    assert len(spawned) == 1


def test_live_serves_cache_and_guard_still_runs(live, monkeypatch):
    import json
    import os
    import time
    tmp, spawned = live
    post = {"platform": "instagram", "url": "https://www.instagram.com/p/a/", "text": "Party 25.11.",
            "posted_at": "2026-11-20T10:00:00Z", "location": "Koeln Club"}
    f = tmp / "koeln.json"
    f.write_text(json.dumps([post]))
    r = server.search_posts("instagram", "Köln", [], 14)
    assert len(r.posts) == 1 and spawned == []  # fresh cache, no fetch
    old = time.time() - 25 * 3600
    os.utime(f, (old, old))
    monkeypatch.setattr(server, "llm_flags", lambda text: True)  # guard blocks, also on stale data
    r = server.search_posts("instagram", "Köln", [], 14)
    assert r.posts == [] and r.blocked == 1 and len(spawned) == 1  # stale: served and refreshed


def test_live_daily_cap_and_missing_token(live, monkeypatch):
    _, spawned = live
    monkeypatch.setattr(server, "MAX_FETCHES", 1)
    with pytest.raises(ToolError, match="is loading"):
        server.search_posts("instagram", "Köln", [], 14)
    with pytest.raises(ToolError, match="daily limit"):
        server.search_posts("instagram", "Berlin", [], 14)
    assert len(spawned) == 1
    monkeypatch.delenv("APIFY_TOKEN")
    with pytest.raises(ToolError, match="APIFY_TOKEN"):
        server.search_posts("instagram", "Hamburg", [], 14)


def _new_process():
    from shared import store
    store._engines.clear()  # same DB file, fresh engine: what a new MCP server process sees


def test_live_running_fetch_survives_a_new_server_process(live):
    _, spawned = live
    with pytest.raises(ToolError, match="is loading"):
        server.search_posts("instagram", "Köln", [], 14)
    _new_process()
    with pytest.raises(ToolError, match="is loading"):
        server.search_posts("tiktok", "Köln", [], 14)
    assert spawned == ["Köln"]


def test_live_dead_fetch_is_restarted_after_ten_minutes(live):
    from shared import store
    _, spawned = live
    store.put("fetches", "koeln", {"started": time.time() - 700})
    with pytest.raises(ToolError, match="is loading"):
        server.search_posts("instagram", "Köln", [], 14)
    assert spawned == ["Köln"]


def test_live_daily_cap_is_counted_in_the_store(live, monkeypatch):
    from shared import store
    _, spawned = live
    monkeypatch.setattr(server, "MAX_FETCHES", 1)
    with pytest.raises(ToolError, match="is loading"):
        server.search_posts("instagram", "Köln", [], 14)
    assert store.get("fetches", f"day-{server.today()}") == 1
    _new_process()
    with pytest.raises(ToolError, match="daily limit"):
        server.search_posts("instagram", "Berlin", [], 14)
    assert len(spawned) == 1


def test_live_failure_marker_from_fetch_live_main_blocks_a_new_start(live, monkeypatch):
    from mcp_servers.event_sources import fetch_live
    _, spawned = live

    def fail(*args):
        raise RuntimeError("All sources failed")
    monkeypatch.setattr(fetch_live, "fetch", fail)
    monkeypatch.setattr(sys, "argv", ["fetch_live", "--city", "Köln"])
    with pytest.raises(ToolError, match="is loading"):
        server.search_posts("instagram", "Köln", [], 14)
    with pytest.raises(SystemExit):  # the detached process fails and leaves the marker
        fetch_live.main()
    _new_process()
    with pytest.raises(ToolError, match="last fetch failed"):
        server.search_posts("tiktok", "Köln", [], 14)
    assert len(spawned) == 1
    from shared import store
    store.put("fetches", "koeln", {"started": 1, "failed": time.time() - 700})  # back-off over
    with pytest.raises(ToolError, match="is loading"):
        server.search_posts("tiktok", "Köln", [], 14)
    assert len(spawned) == 2


def test_spawn_passes_the_city_as_one_argv_element_without_shell(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server.subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
    server._spawn("Köln; rm -rf /")
    (argv,), kw = calls[0]
    assert argv[-2:] == ["--city", "Köln; rm -rf /"] and not kw.get("shell") and kw["start_new_session"]
    server._spawn("Köln", ["techno", "jazz"], add=True)
    assert calls[1][0][0][-6:] == ["--city", "Köln", "--tags", "techno", "jazz", "--add"]


def test_live_new_interest_tags_start_an_add_fetch_known_tags_do_not(live, monkeypatch):
    import json
    import os
    from shared import store
    tmp, _ = live
    spawned = []
    monkeypatch.setattr(server, "_spawn", lambda city, tags=(), add=False: spawned.append((city, list(tags), add)))
    post = {"platform": "instagram", "url": "https://www.instagram.com/p/a/", "text": "Party 25.11.",
            "posted_at": "2026-11-20T10:00:00Z", "location": "Koeln Club"}
    f = tmp / "koeln.json"
    f.write_text(json.dumps([post]))
    store.put("fetches", "tags-koeln", ["techno"])
    assert len(server.search_posts("instagram", "Köln", ["techno"], 14).posts) == 1 and spawned == []
    assert len(server.search_posts("instagram", "Köln", ["techno", "jazz"], 14).posts) == 1  # served now
    assert spawned == [("Köln", ["jazz"], True)]
    store.put("fetches", "koeln", {"started": 1})  # the add run is over
    old = time.time() - 25 * 3600
    os.utime(f, (old, old))
    server.search_posts("instagram", "Köln", ["kunst"], 14)
    assert spawned[-1] == ("Köln", ["techno", "kunst"], False)  # stale: full refresh with known + new tags
