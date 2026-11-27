import socket
from pathlib import Path

import httpx
import pytest

from mcp_servers.event_sources import resolver
from shared import store

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
    resolver._fc_calls.clear()
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)  # .env may hold a real key: tests stay offline
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
    store.clear("resolver")
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
    assert resolver.resolve_signup("https://a.example.org/t", TITLE, START) == a and len(web["seen"]) == 1


SHOP_MD = "# Nebula Night Synthwave\nSa., 05.12.2026, 20:00\n\nKategorie 1 € 19,15 inkl. Gebühren\n[In den Warenkorb](...)"


@pytest.fixture
def fc(web, monkeypatch):
    """Firecrawl fallback on, with mocked Firecrawl, guard and Gemini extraction. Records the calls."""
    calls = {"fc": [], "llm": [], "md": SHOP_MD, "offer": resolver._Offer(price="19,15", availability="available"),
             "poisoned": False}
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    monkeypatch.setattr(resolver, "_firecrawl", lambda url: calls["fc"].append(url) or (calls["md"], "eventim.de"))
    monkeypatch.setattr(resolver, "_extract", lambda md, title: calls["llm"].append(md) or calls["offer"])
    monkeypatch.setattr(resolver, "is_poisoned", lambda text: calls["poisoned"])
    web["https://shop.example.org/e"] = (403, {})
    return calls


def test_blocked_shop_falls_back_to_rendered_page(fc):
    r = resolver.resolve_signup("https://shop.example.org/e", TITLE, START)
    assert r["signup"] == "tickets" and r["ticket"]["price"] == "19.15 EUR" and r["ticket"]["availability"] == "available"
    assert r["ticket"]["url"] == "https://shop.example.org/e" and fc["fc"] == ["https://shop.example.org/e"]


def test_rendered_price_must_be_on_the_page_with_currency(fc):
    fc["offer"] = resolver._Offer(price="9,99", availability="available")  # LLM invents a price
    assert resolver.resolve_signup("https://shop.example.org/e", TITLE, START)["signup"] == "unknown"
    store.clear("resolver")
    fc["md"], fc["offer"] = SHOP_MD.replace("€ 19,15", "19,15"), resolver._Offer(price="19,15", availability="available")
    assert resolver.resolve_signup("https://shop.example.org/e", TITLE, START)["signup"] == "unknown"  # no currency


def test_rendered_page_of_another_event_skips_llm(fc):
    assert resolver.resolve_signup("https://shop.example.org/e", TITLE, "2026-12-06T20:00:00")["signup"] == "unknown"
    assert fc["fc"] and not fc["llm"]


def test_poisoned_rendered_page_skips_llm(fc):
    fc["poisoned"] = True
    r = resolver.resolve_signup("https://shop.example.org/e", TITLE, START)
    assert r["signup"] == "unknown" and r["note"].startswith("blocked") and not fc["llm"]


def test_unsafe_url_never_goes_to_firecrawl(fc, monkeypatch):
    assert resolver.resolve_signup("http://shop.example.org/e", TITLE, START)["signup"] == "unknown"
    monkeypatch.setattr(socket, "getaddrinfo", lambda h, *a, **k: [(2, 1, 6, "", ("10.0.0.1", 443))])
    assert resolver.resolve_signup("https://shop.example.org/e", TITLE, START)["signup"] == "unknown"
    assert not fc["fc"]


def test_firecrawl_hourly_limit(fc):
    for i in range(resolver.FC_PER_HOUR + 2):
        resolver.resolve_signup("https://shop.example.org/e", TITLE, f"2026-12-05T{i:02d}:00:00")  # new cache key
    assert len(fc["fc"]) == resolver.FC_PER_HOUR


def test_no_key_no_firecrawl(fc, monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY")
    r = resolver.resolve_signup("https://shop.example.org/e", TITLE, START)
    assert r["signup"] == "unknown" and r["note"] == "not resolved: HTTP 403" and not fc["fc"]
