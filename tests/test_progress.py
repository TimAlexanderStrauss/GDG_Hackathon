import time
from types import SimpleNamespace

from shared import store
from shared.progress import progress_for, report

IDLE = {"active": False, "pct": 0, "stage": "idle", "text": ""}


def put(user, **kw):
    store.put("progress", user, {"ts": time.time(), "city": "Köln", "stage": "extract", "pct": 75, "text": "Reading", **kw})


def test_idle_cases():
    assert progress_for("u") == IDLE  # no record
    put("u", stage="done", pct=100, ts=time.time() - 11)
    assert progress_for("u") == IDLE  # done and shown long enough
    put("u", ts=time.time() - 16 * 60)
    assert progress_for("u") == IDLE  # stale


def test_record_is_returned_and_done_stays_for_a_moment():
    put("u")
    assert progress_for("u") == {"active": True, "stage": "extract", "pct": 75, "text": "Reading"}
    put("u", stage="done", pct=100, text="Done", ts=time.time() - 5)
    assert progress_for("u")["pct"] == 100


def test_search_stage_shows_the_fetch_while_it_runs():
    put("u", stage="search", pct=2, text="Scouts")
    assert progress_for("u")["stage"] == "search"  # no fetch record
    store.put("fetches", "progress-koeln", {"started": time.time(), "step": 2, "steps": 4, "text": "TikTok: #koeln"})
    assert progress_for("u") == {"active": True, "stage": "fetch", "pct": 33, "text": "Loading live posts – TikTok: #koeln"}
    store.put("fetches", "progress-koeln", {"started": time.time() - 100, "step": 2, "steps": 4, "text": "x"})
    assert progress_for("u")["stage"] == "search"  # fetch of an earlier scan
    store.put("fetches", "progress-koeln", {"started": time.time(), "step": 4, "steps": 4, "text": "Saving posts"})
    assert progress_for("u")["stage"] == "search"  # fetch is done


def test_report_writes_and_never_raises(monkeypatch):
    report(SimpleNamespace(user_id="u", state={"profile": {"city": "Köln"}}), "rank", 88, "Ranking")
    assert store.get("progress", "u")["stage"] == "rank" and store.get("progress", "u")["city"] == "Köln"
    report(SimpleNamespace(state={}), "rank", 88, "no user id")  # must not raise

    def boom(*a):
        raise OSError("db locked")
    monkeypatch.setattr(store, "put", boom)
    report(SimpleNamespace(user_id="u", state={}), "rank", 88, "db down")


def test_fetch_writes_progress_records(monkeypatch, tmp_path):
    from mcp_servers.event_sources import fetch_live as f
    monkeypatch.setattr(f, "LIVE_DIR", tmp_path)
    monkeypatch.setenv("APIFY_TOKEN", "x")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.setattr(f, "_run", lambda a, p: [])
    seen = []
    real_put = store.put
    monkeypatch.setattr(store, "put", lambda t, k, v: (seen.append(v) if k == "progress-koeln" else None, real_put(t, k, v))[1])
    store.put("fetches", "koeln", {"started": 123.0})
    f.fetch("Köln")
    assert [r["text"] for r in seen] == ["Instagram: #koelnevents, #kölnevents, #eventskoeln …", "Instagram: looking up bio links",
                                         "TikTok: #koelnevents, #kölnevents, #koeln", "TikTok: looking up bio links", "Saving posts"]
    assert seen[-1]["step"] == seen[-1]["steps"] == 4 and all(r["started"] == 123.0 for r in seen)
