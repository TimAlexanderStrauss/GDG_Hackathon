import socket
from pathlib import Path

import httpx
import pytest

from mcp_servers.event_sources import resolver

FIX = Path(__file__).parent / "fixtures"
TITLE, START = "Nebula Night Synthwave", "2026-12-05T20:00:00"


def page(name):
    return (FIX / name).read_text()


@pytest.fixture
def web(monkeypatch):
    """Maps URL -> HTML (200) / (status, headers) / bytes; counts requests. All hosts resolve to a public IP."""
    pages, seen = {}, []

    def handler(req):
        seen.append(str(req.url))
        v = pages[str(req.url)]
        if isinstance(v, tuple):
            return httpx.Response(v[0], headers=v[1])
        return httpx.Response(200, content=v, headers={"content-type": "text/html; charset=utf-8"})
    monkeypatch.setattr(resolver, "_transport", httpx.MockTransport(handler))
    monkeypatch.setattr(socket, "getaddrinfo", lambda h, *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    resolver._cache.clear()
    pages["seen"] = seen  # type: ignore
    return pages


def test_ticket_page(web):
    web["https://a.example.org/t"] = page("event_ticket.html")
    r = resolver.resolve_signup("https://a.example.org/t", TITLE, START)
    assert r["signup"] == "tickets" and r["registration_url"] is None
    assert r["ticket"]["price"] == "10.00 EUR" and r["ticket"]["availability"] == "available"
    assert r["ticket"]["url"] == "https://shop.example.org/nebula" and r["ticket"]["checked_at"]


def test_graph_list_offers_sold_out(web):
    web["https://a.example.org/t"] = page("event_graph.html")
    r = resolver.resolve_signup("https://a.example.org/t", TITLE, START)
    assert r["signup"] == "tickets" and r["ticket"]["price"] == "12.50 EUR" and r["ticket"]["availability"] == "sold_out"
    assert r["ticket"]["url"] == "https://a.example.org/t"  # no offer url: the page itself


def test_free_event_is_web_form(web):
    web["https://a.example.org/t"] = page("event_free.html")
    r = resolver.resolve_signup("https://a.example.org/t", TITLE, START)
    assert (r["signup"], r["ticket"], r["registration_url"]) == ("web_form", None, "https://register.example.org/free")


def test_wrong_date_no_match(web):
    web["https://a.example.org/t"] = page("event_ticket.html")
    assert resolver.resolve_signup("https://a.example.org/t", TITLE, "2026-12-06T20:00:00")["signup"] == "unknown"


def test_title_overlap_without_start(web):
    web["https://a.example.org/t"] = page("event_ticket.html")
    assert resolver.resolve_signup("https://a.example.org/t", "Nebula Night", "")["signup"] == "tickets"


def test_bio_page_one_hop_only(web):
    web["https://linktr.example.org/club"] = page("bio_page.html")
    web["https://tickets.example.org/nebula"] = page("event_ticket.html")
    assert resolver.resolve_signup("https://linktr.example.org/club", TITLE, START)["signup"] == "tickets"
    # the second page is a bio page again: its link is not followed
    resolver._cache.clear()
    web["https://tickets.example.org/nebula"] = page("bio_page_deep.html")
    web["https://deep.example.org/nebula"] = page("event_ticket.html")
    web["seen"].clear()
    assert resolver.resolve_signup("https://linktr.example.org/club", TITLE, START)["signup"] == "unknown"
    assert "https://deep.example.org/nebula" not in web["seen"]


def test_http_rejected(web):
    r = resolver.resolve_signup("http://a.example.org/t", TITLE, START)
    assert r["signup"] == "unknown" and not web["seen"]


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "169.254.169.254"])
def test_private_ip_rejected(web, monkeypatch, ip):
    monkeypatch.setattr(socket, "getaddrinfo", lambda h, *a, **k: [(2, 1, 6, "", (ip, 443))])
    assert resolver.resolve_signup("https://a.example.org/t", TITLE, START)["signup"] == "unknown"
    assert not web["seen"]


def test_private_ip_on_redirect_hop(web, monkeypatch):
    web["https://a.example.org/t"] = (302, {"location": "https://internal.example.org/x"})
    web["https://internal.example.org/x"] = page("event_ticket.html")
    monkeypatch.setattr(socket, "getaddrinfo", lambda h, *a, **k: [(2, 1, 6, "", ("10.0.0.1" if h.startswith("internal") else "93.184.216.34", 443))])
    assert resolver.resolve_signup("https://a.example.org/t", TITLE, START)["signup"] == "unknown"
    assert web["seen"] == ["https://a.example.org/t"]


def test_redirect_limit(web):
    for i in range(4):
        web[f"https://a.example.org/{i}"] = (302, {"location": f"https://a.example.org/{i + 1}"})
    assert "redirect" in resolver.resolve_signup("https://a.example.org/0", TITLE, START)["note"]


def test_body_over_1mb_stops(web):
    web["https://a.example.org/big"] = "<html>" + "x" * 1_100_000
    r = resolver.resolve_signup("https://a.example.org/big", TITLE, START)
    assert r["signup"] == "unknown" and "1 MB" in r["note"]


def test_poisoned_page_blocked(web):
    web["https://a.example.org/p"] = page("poisoned.html")
    r = resolver.resolve_signup("https://a.example.org/p", TITLE, START)
    assert r["signup"] == "unknown" and r["note"].startswith("blocked")
    assert "ignore" not in str(r).lower().replace("blocked: page looks like a prompt injection", "")


def test_cache_hit_does_not_fetch_twice(web):
    web["https://a.example.org/t"] = page("event_ticket.html")
    a = resolver.resolve_signup("https://a.example.org/t", TITLE, START)
    assert resolver.resolve_signup("https://a.example.org/t", TITLE, START) is a and len(web["seen"]) == 1
