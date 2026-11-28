import asyncio
import json
import os
import sys
import time
from datetime import date

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mcp_servers.event_sources import server


def sp(*a):
    return asyncio.run(server.search_posts(*a))


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(server, "today", lambda: date(2026, 11, 21))  # demo day
    monkeypatch.setattr(server, "FIXTURES", server.ROOT / "fixtures" / "posts.json")
    monkeypatch.setattr(server, "LIVE", False)  # also with DEMO_MODE=live
    monkeypatch.setattr(server, "llm_flags", lambda text: False)  # regex layer only, no Gemini call
    monkeypatch.setattr(server, "GUARD", "gemini")  # also when .env says model_armor


def test_poisoned_post_is_blocked():
    r = sp("instagram", "Münster", ["ai", "#Techno"], 14)
    texts = " ".join(p.text for p in r.posts)
    assert r.blocked == 1
    assert "ignore all previous instructions" not in texts
    assert "AI & Agents Meetup" in texts and "TECHNO NIGHT" in texts and "Jazz Jam" in texts
    assert "Berlin" not in texts  # city filter
    assert r.note == "Results may be incomplete"


def test_date_window():
    r = sp("tiktok", "Münster", [], 8)  # 29.11. is in, Glühweinlauf on 04.12. is out
    assert [p.text[:12] for p in r.posts] == ["Nachtflohmar", "Recap vom Li"]


@pytest.mark.parametrize("tags", [["a", "b", "c", "d"], ["two words"], ["drop;table"]])
def test_invalid_hashtags(tags):
    with pytest.raises(ToolError, match="INVALID_INPUT"):
        sp("instagram", "Münster", tags, 14)


def test_model_armor_guard_replaces_gemini_and_fails_closed(monkeypatch):
    base = sp("instagram", "Münster", ["ai"], 14)
    monkeypatch.setattr(server, "GUARD", "model_armor")
    monkeypatch.setattr(server, "armor_flags", lambda text: True)
    r = sp("instagram", "Münster", ["ai"], 14)
    assert r.posts == [] and r.blocked == base.blocked + len(base.posts)

    def down(text):
        raise server.gapi_errors.ServiceUnavailable("down")
    monkeypatch.setattr(server, "armor_flags", down)
    with pytest.raises(ToolError, match="SOURCE_UNAVAILABLE"):
        sp("instagram", "Münster", ["ai"], 14)


POST = {"platform": "instagram", "url": "https://www.instagram.com/p/a/", "text": "Party 25.11.",
        "posted_at": "2026-11-20T10:00:00Z", "location": "Koeln Club"}


@pytest.fixture
def live(monkeypatch, tmp_path):
    """Live mode with a fake fetch process: _spawn writes the cache file at once (mode["write"]) or never."""
    from mcp_servers.event_sources import fetch_live
    from shared import store
    monkeypatch.setattr(server, "LIVE", True)
    monkeypatch.setattr(fetch_live, "LIVE_DIR", tmp_path)
    monkeypatch.setenv("APIFY_TOKEN", "x")
    monkeypatch.setattr(server, "POLL", 0.01)
    monkeypatch.setattr(server, "MAX_WAIT", 0.3)
    spawned, mode = [], {"write": True}

    def fake_spawn(city, tags=(), add=False):
        spawned.append((city, list(tags), add))
        if mode["write"]:
            (tmp_path / "koeln.json").write_text(json.dumps([POST]))
            known = (store.get("fetches", "tags-koeln") or []) if add else []
            store.put("fetches", "tags-koeln", known + list(tags))
    monkeypatch.setattr(server, "_spawn", fake_spawn)
    return tmp_path, spawned, mode


def test_live_missing_cache_waits_for_one_fetch_then_serves(live):
    _, spawned, _ = live
    for _ in range(3):  # three scouts
        assert len(sp("instagram", "Köln", ["techno"], 14).posts) == 1
    assert spawned == [("Köln", ["techno"], False)]


def test_live_parallel_scouts_wait_for_the_same_fetch(live, monkeypatch):
    tmp, spawned, mode = live
    mode["write"] = False  # the fetch "runs": the file comes after a moment

    async def scouts():
        async def finish():
            await asyncio.sleep(0.1)
            (tmp / "koeln.json").write_text(json.dumps([POST]))
        done = await asyncio.gather(*(server.search_posts(pl, "Köln", [], 14) for pl in ("instagram", "tiktok", "web")),
                                    finish())
        return done[:3]
    monkeypatch.setattr(server, "MAX_WAIT", 5)
    r = asyncio.run(scouts())
    assert len(r[0].posts) == 1 and r[1].posts == [] and len(spawned) == 1


def test_live_serves_cache_and_guard_still_runs(live, monkeypatch):
    tmp, spawned, _ = live
    f = tmp / "koeln.json"
    f.write_text(json.dumps([POST]))
    assert len(sp("instagram", "Köln", [], 14).posts) == 1 and spawned == []  # fresh cache, no fetch
    old = time.time() - 25 * 3600
    os.utime(f, (old, old))
    monkeypatch.setattr(server, "llm_flags", lambda text: True)  # guard blocks, also on stale data
    r = sp("instagram", "Köln", [], 14)
    assert r.posts == [] and r.blocked == 1 and len(spawned) == 1  # stale: refreshed first, then served


def test_live_timeout_uses_the_cache_or_raises(live):
    tmp, spawned, mode = live
    mode["write"] = False
    with pytest.raises(ToolError, match="SOURCE_UNAVAILABLE: live data for Köln cannot be loaded: .*took longer"):
        sp("instagram", "Köln", [], 14)
    f = tmp / "koeln.json"
    f.write_text(json.dumps([POST]))
    old = time.time() - 25 * 3600
    os.utime(f, (old, old))
    from shared import store
    store.put("fetches", "koeln", {"started": 1})  # the first fetch is over
    assert len(sp("instagram", "Köln", [], 14).posts) == 1  # stale cache, the new fetch times out: cache is served


def test_live_failed_fetch_uses_the_cache_or_raises(live, monkeypatch):
    from shared import store
    tmp, spawned, mode = live
    mode["write"] = False
    monkeypatch.setattr(server, "_spawn", lambda city, *a: store.put("fetches", "koeln", {"started": time.time(), "failed": time.time()}))
    with pytest.raises(ToolError, match="cannot be loaded: the live fetch failed"):
        sp("instagram", "Köln", [], 14)
    with pytest.raises(ToolError, match="cannot be loaded: the last fetch failed"):  # back-off
        sp("tiktok", "Köln", [], 14)


def test_live_daily_cap_and_missing_token(live, monkeypatch):
    _, spawned, _ = live
    monkeypatch.setattr(server, "MAX_FETCHES", 1)
    assert len(sp("instagram", "Köln", [], 14).posts) == 1
    with pytest.raises(ToolError, match="daily limit"):
        sp("instagram", "Berlin", [], 14)
    assert len(spawned) == 1
    monkeypatch.delenv("APIFY_TOKEN")
    with pytest.raises(ToolError, match="APIFY_TOKEN"):
        sp("instagram", "Hamburg", [], 14)


def _new_process():
    from shared import store
    store._engines.clear()  # same DB file, fresh engine: what a new MCP server process sees


def test_live_running_fetch_survives_a_new_server_process(live):
    _, spawned, mode = live
    mode["write"] = False
    with pytest.raises(ToolError, match="took longer"):
        sp("instagram", "Köln", [], 14)
    _new_process()
    mode["write"] = True
    (live[0] / "koeln.json").write_text(json.dumps([POST]))  # the detached process finishes meanwhile
    assert len(sp("tiktok", "Köln", [], 14).posts) == 0 and spawned == [("Köln", [], False)]


def test_live_dead_fetch_is_restarted_after_ten_minutes(live):
    from shared import store
    _, spawned, _ = live
    store.put("fetches", "koeln", {"started": time.time() - 700})
    assert len(sp("instagram", "Köln", [], 14).posts) == 1
    assert len(spawned) == 1


def test_live_failure_marker_from_fetch_live_main_blocks_a_new_start(live, monkeypatch):
    from mcp_servers.event_sources import fetch_live
    from shared import store
    _, spawned, mode = live
    mode["write"] = False

    def fail(*args):
        raise RuntimeError("All sources failed")
    monkeypatch.setattr(fetch_live, "fetch", fail)
    monkeypatch.setattr(sys, "argv", ["fetch_live", "--city", "Köln"])
    monkeypatch.setattr(server, "_spawn", lambda city, *a: (spawned.append(city), fetch_live.main()))
    with pytest.raises(SystemExit):  # the "detached" run fails inside _spawn and leaves the marker
        sp("instagram", "Köln", [], 14)
    _new_process()
    with pytest.raises(ToolError, match="last fetch failed"):
        sp("tiktok", "Köln", [], 14)
    assert len(spawned) == 1
    store.put("fetches", "koeln", {"started": 1, "failed": time.time() - 700})  # back-off over
    with pytest.raises(SystemExit):
        sp("tiktok", "Köln", [], 14)
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


def test_live_new_interest_tags_start_an_add_fetch_and_wait_known_tags_do_not(live):
    from shared import store
    tmp, spawned, _ = live
    (tmp / "koeln.json").write_text(json.dumps([POST]))
    store.put("fetches", "tags-koeln", ["techno"])
    assert len(sp("instagram", "Köln", ["techno"], 14).posts) == 1 and spawned == []
    assert len(sp("instagram", "Köln", ["techno", "jazz"], 14).posts) == 1
    assert spawned == [("Köln", ["jazz"], True)]
    assert store.get("fetches", "tags-koeln") == ["techno", "jazz"]  # known now: no second fetch
    sp("instagram", "Köln", ["techno", "jazz"], 14)
    assert len(spawned) == 1
    store.put("fetches", "koeln", {"started": 1})  # the add run is over
    old = time.time() - 25 * 3600
    os.utime(tmp / "koeln.json", (old, old))
    sp("instagram", "Köln", ["kunst"], 14)
    assert spawned[-1] == ("Köln", ["techno", "jazz", "kunst"], False)  # stale: full refresh with known + new tags


def test_live_second_add_for_tags_another_scouts_fetch_did_not_bring(live, monkeypatch):
    from shared import store
    tmp, spawned, _ = live
    calls = []

    def spawn(city, tags=(), add=False):  # the fetch of scout A finishes, but with other tags than scout B asked for
        calls.append((list(tags), add))
        (tmp / "koeln.json").write_text(json.dumps([POST]))
        store.put("fetches", "tags-koeln", ["techno"] if len(calls) == 1 else ["techno", "jazz"])
    monkeypatch.setattr(server, "_spawn", spawn)
    assert len(sp("instagram", "Köln", ["jazz"], 14).posts) == 1
    assert calls == [(["jazz"], False), (["jazz"], True)]  # one more add, then it stops (at most once per call)


def test_live_city_name_is_no_tag_and_no_loading_note(live):
    from shared import store
    tmp, spawned, _ = live
    (tmp / "koeln.json").write_text(json.dumps([POST]))
    store.put("fetches", "tags-koeln", ["techno"])
    r = sp("instagram", "Köln", ["koeln", "techno"], 14)
    assert spawned == [] and r.note == server.NOTE  # city name ignored, nothing new
    r = sp("instagram", "Köln", ["koeln", "doppelkopf"], 14)
    assert spawned == [("Köln", ["doppelkopf"], True)] and r.note == server.NOTE


def test_live_old_cache_with_daily_limit_warns_and_names_the_interests(live, monkeypatch):
    import json
    import os
    tmp, spawned, _ = live
    post = {"platform": "instagram", "url": "https://www.instagram.com/p/a/", "text": "Party 30.11.",
            "posted_at": "2026-11-20T10:00:00Z", "location": "Koeln Club"}
    f = tmp / "koeln.json"
    f.write_text(json.dumps([post]))
    old = time.time() - 25 * 3600
    os.utime(f, (old, old))
    monkeypatch.setattr(server, "MAX_FETCHES", 0)  # limit already used up today
    r = sp("instagram", "Köln", ["doppelkopf"], 14)
    assert len(r.posts) == 1 and spawned == []
    assert r.note.startswith("warning: no new live posts (daily limit") and "interests not searched: doppelkopf" in r.note
