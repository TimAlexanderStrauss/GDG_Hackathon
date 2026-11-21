from datetime import date

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mcp_servers.event_sources import server


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(server, "today", lambda: date(2026, 11, 21))  # demo day
    monkeypatch.setattr(server, "llm_flags", lambda text: False)  # regex layer only, no Gemini call


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
