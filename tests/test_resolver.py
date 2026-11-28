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


BIO = "https://linktr.example.org/club"
SHOW = "<html><body><h1>Nebula Night Synthwave</h1><p>%s</p>%s</body></html>"


def test_bio_home_page_without_the_event_has_no_event_page(web):
    web[BIO] = "<html><body><h1>Our company</h1><a href='https://linktr.example.org/about'>About</a> Anmeldung per Mail</body></html>"
    assert resolver.resolve_signup(BIO, TITLE, START)["event_page"] is None


def test_bio_page_links_to_event_page_with_title_date_and_signup(web):
    web[BIO] = page("bio_page.html")
    web["https://tickets.example.org/nebula"] = SHOW % ("Am 05.12.2026 ab 20 Uhr.", "<a href='/x'>Jetzt anmelden</a>")
    r = resolver.resolve_signup(BIO, TITLE, START)
    assert r["signup"] == "unknown" and r["event_page"] == "https://tickets.example.org/nebula"


def test_event_page_without_signup_word_is_not_kept(web):
    web[BIO] = page("bio_page.html")
    web["https://tickets.example.org/nebula"] = SHOW % ("Am 5. Dezember ab 20 Uhr.", "")
    assert resolver.resolve_signup(BIO, TITLE, START)["event_page"] is None


def test_json_ld_event_without_offer_keeps_page_if_text_has_signup_word(web):
    ld = '<script type="application/ld+json">{"@type":"Event","name":"Nebula Night Synthwave","startDate":"2026-12-05T20:00"}</script>'
    web["https://a.example.org/t"] = f"<html><body>{ld}<p>Tickets an der Abendkasse</p></body></html>"
    web["https://a.example.org/u"] = f"<html><body>{ld}<p>Nur Musik</p></body></html>"
    assert resolver.resolve_signup("https://a.example.org/t", TITLE, START)["event_page"] == "https://a.example.org/t"
    assert resolver.resolve_signup("https://a.example.org/u", TITLE, START)["event_page"] is None


def test_tickets_result_has_event_page(web):
    web["https://a.example.org/t"] = page("event_ticket.html")
    assert resolver.resolve_signup("https://a.example.org/t", TITLE, START)["event_page"] == "https://a.example.org/t"


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


# --- find_original: follows an aggregator's listing to the organiser's page ---
LISTING = ("[Hamburg \\| Nebula Night Synthwave](https://links.agg.example/event/abc) Sat 5 Dec 20:00 "
           "[Open in AggApp](https://links.agg.example/event/abc) [Original listing](https://lu.example.org/nebula)\n"
           "[#4 Hardware Meetup Hamburg Special](https://links.agg.example/event/def) "
           "[Original listing](https://other.example.org/hw)\n")
LISTING_URL = "https://www.agg.example/events/hamburg"
OG = '<html><head><meta property="og:image" content="https://img.example.org/n.jpg"></head><body></body></html>'


def test_original_from_block_layout(web):
    web["https://lu.example.org/nebula"] = OG
    r = resolver.find_original(LISTING_URL, LISTING, TITLE, START)
    assert r["url"] == "https://lu.example.org/nebula" and r["image_url"] == "https://img.example.org/n.jpg"
    assert "https://other.example.org/hw" not in web["seen"]  # the next event's block is not read


def test_original_via_aggregator_detail_page_jsonld(web):
    md = f"[{TITLE}](https://www.agg.example/e/1) more text"
    web["https://www.agg.example/e/1"] = (
        '<script type="application/ld+json">{"@type":"Event","name":"Nebula Night Synthwave",'
        '"startDate":"2026-12-05T20:00:00+01:00","url":"https://lu.example.org/nebula"}</script>')
    web["https://lu.example.org/nebula"] = (
        '<script type="application/ld+json">{"@type":"Event","name":"Nebula Night Synthwave",'
        '"startDate":"2026-12-05","image":{"@type":"ImageObject","url":"https://img.example.org/ld.jpg"}}</script>' + OG)
    r = resolver.find_original(LISTING_URL, md, TITLE, START)
    assert r["url"] == "https://lu.example.org/nebula" and r["image_url"] == "https://img.example.org/ld.jpg"


def test_original_via_outbound_link_on_aggregator_page(web):
    md = f"[{TITLE}](https://www.agg.example/e/1)"
    web["https://www.agg.example/e/1"] = '<a href="https://tickets.example.org/nebula">Tickets</a><a href="https://x.example.org/">Impressum</a>'
    web["https://tickets.example.org/nebula"] = OG
    r = resolver.find_original(LISTING_URL, md, TITLE, START)
    assert r["url"] == "https://tickets.example.org/nebula" and r["image_url"] == "https://img.example.org/n.jpg"


def test_no_matching_link(web):
    r = resolver.find_original(LISTING_URL, "[Something else entirely](https://x.example.org/a)", TITLE, START)
    assert r["url"] is None and r["image_url"] is None and web["seen"] == []


def test_heading_shape_detail_link_and_listing_image(web):
    md = ("![Banner](https://cdn.agg.example/img/banner.jpg)\n![x](https://cdn.agg.example/badge.svg)\n"
          "### Nebula Night Synthwave\n- Music\n- 05.12.2026\n\nShort text.\n"
          "[/events/n/#c1](https://www.agg.example/events/n/)\n\n![Other](https://cdn.agg.example/other.jpg)\n### Another Show\n")
    web["https://www.agg.example/events/n/"] = '<a href="https://venue.example.org/nebula">Zum Veranstalter</a>'
    web["https://venue.example.org/nebula"] = "<html><body>no image</body></html>"
    r = resolver.find_original(LISTING_URL, md, TITLE, START)
    # title tokens are not in the link text, but the detail link comes right after the heading
    assert r["url"] == "https://venue.example.org/nebula" and r["image_url"] == "https://cdn.agg.example/img/banner.jpg"


def test_listing_image_skips_the_title_in_an_image_alt_text():
    from mcp_servers.event_sources.resolver import _listing_image
    text = ("- ![Jazz am Kanal](https://cdn.example.org/jazz.jpg)\n© Foto\n### Jazz am Kanal\n- 05.12.2026\n"
            "[/events/jazz-am-kanal/](https://listing.example.org/events/jazz-am-kanal/)")
    assert _listing_image(text, "Jazz am Kanal") == "https://cdn.example.org/jazz.jpg"


# --- search_original: social list posts have no links, one Firecrawl search finds the organiser's page ---
@pytest.fixture
def srch(web, monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    resolver._search_calls.clear()
    calls = {"n": 0, "results": [
        {"url": "https://www.instagram.com/p/x/", "title": TITLE, "description": ""},
        {"url": "https://www.agg.example/e/1", "title": TITLE, "description": ""},
        {"url": "https://www.other.example/e", "title": "Unrelated gardening", "description": ""},
        {"url": "https://lu.example.org/nebula", "title": "Nebula Night Synthwave Hamburg", "description": "2026-12-05"}]}

    def post(url, **kw):
        calls["n"] += 1
        calls["json"] = kw["json"]
        return httpx.Response(200, json={"data": {"web": calls["results"]}}, request=httpx.Request("POST", url))
    monkeypatch.setattr(resolver.httpx, "post", post)
    web["https://lu.example.org/nebula"] = OG
    return calls


def test_search_finds_original_and_skips_social_and_listing_domain(srch):
    r = resolver.search_original(TITLE, "Club X", "Hamburg", START, not_host="agg.example")
    assert r["url"] == "https://lu.example.org/nebula" and r["image_url"] == "https://img.example.org/n.jpg"
    assert srch["json"]["query"] == f"{TITLE} Club X Hamburg" and "scrapeOptions" not in srch["json"]


def test_search_token_mismatch_no_original(srch):
    srch["results"] = [srch["results"][2]]
    assert resolver.search_original(TITLE, "", "Hamburg", START)["url"] is None


def test_search_cache_hit_no_second_search_also_for_nothing_found(srch):
    srch["results"] = []
    resolver.search_original(TITLE, "", "Hamburg", START)
    assert resolver.search_original(TITLE, "x", "Hamburg", START)["url"] is None and srch["n"] == 1


def test_search_budget_and_no_key(srch, monkeypatch):
    resolver._search_calls[:] = [__import__("time").time()] * resolver.SEARCH_PER_HOUR
    assert resolver.search_original(TITLE, "", "Hamburg", START)["url"] is None and srch["n"] == 0
    resolver._search_calls.clear()
    monkeypatch.delenv("FIRECRAWL_API_KEY")
    assert resolver.search_original(TITLE, "", "Hamburg", START)["url"] is None and srch["n"] == 0


def test_content_image_fallback_skips_logos_banners_and_small_images():
    from mcp_servers.event_sources.resolver import _Page, _image
    html = ('<img class="logo" src="/logo.png"><img src="/icon.png" width="64" height="64">'
            '<img src="https://x.example.org/banner.png" width="1320" height="264">'
            '<img loading="lazy" src="/_cms/image/4585"><img src="/second.jpg">')
    page = _Page()
    page.feed(html)
    assert _image(None, page, "https://theater.example.org/stueck.html") == "https://theater.example.org/_cms/image/4585"
    page = _Page()
    page.feed('<meta property="og:image" content="https://x.example.org/og.jpg"><img src="/a.jpg">')
    assert _image(None, page, "https://x.example.org/") == "https://x.example.org/og.jpg"  # og:image still wins
