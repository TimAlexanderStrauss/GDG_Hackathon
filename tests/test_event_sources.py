from datetime import date

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mcp_servers.event_sources import server


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(server, "today", lambda: date(2026, 11, 21))  # demo day
    monkeypatch.setattr(server, "FIXTURES", server.ROOT / "fixtures" / "posts.json")  # also with DEMO_MODE=live
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
