"""Resolver: finds the real sign-up path (ticket shop or free web form) behind a link. Deterministic, no LLM.

Only numeric/structured fields leave this module (price formatted in code, availability enum, URLs), so no free page
text reaches an LLM. Never raises: every failure is signup "unknown" with a short note.
"""
import ipaddress
import json
import re
import socket
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

from mcp_servers.event_sources.server import SUSPICIOUS
from shared.schemas import TicketOffer

MAX_BYTES, MAX_REDIRECTS, TIMEOUT, TTL = 1_000_000, 2, 10, 3600
_cache: dict[tuple, tuple[float, dict]] = {}
_transport = None  # tests inject httpx.MockTransport
TOKEN = re.compile(r"[^\W_]{3,}")
ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


class _Fail(Exception):
    pass


def _check(url: str) -> None:
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.port not in (None, 443):
        raise _Fail("only https URLs on the default port are allowed")
    try:
        addrs = {a[4][0].split("%")[0] for a in socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)}
        ok = bool(addrs) and all(ipaddress.ip_address(a).is_global for a in addrs)
    except (OSError, ValueError):
        raise _Fail("host does not resolve") from None
    if not ok:
        raise _Fail("host is not a public address")


def _fetch(url: str) -> tuple[str, str]:
    """Returns (html, final_url). shortcut: _check and the connect resolve DNS separately (DNS rebinding gap), pin the IP via a custom transport if this ever faces untrusted users."""
    with httpx.Client(transport=_transport, timeout=TIMEOUT, follow_redirects=False, cookies=None) as c:
        for _ in range(MAX_REDIRECTS + 1):
            _check(url)
            with c.stream("GET", url, headers={"Accept": "text/html"}) as r:
                if r.is_redirect:
                    url = urljoin(url, r.headers.get("location", ""))
                    continue
                if r.status_code != 200:
                    raise _Fail(f"HTTP {r.status_code}")
                if r.headers.get("content-type", "").split(";")[0].strip().lower() not in ("text/html", "application/xhtml+xml"):
                    raise _Fail("not an HTML page")
                body = b""
                for chunk in r.iter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        raise _Fail("page larger than 1 MB")
                return body.decode(r.encoding or "utf-8", "replace"), url
    raise _Fail("too many redirects")


class _Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ld, self.links, self._ld, self._href = [], [], False, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._ld = True
            self.ld.append("")
        elif tag == "a" and a.get("href"):
            self._href = [a["href"], ""]
            self.links.append(self._href)

    def handle_endtag(self, tag):
        if tag == "script":
            self._ld = False
        elif tag == "a":
            self._href = None

    def handle_data(self, data):
        if self._ld:
            self.ld[-1] += data
        if self._href:
            self._href[1] += data


def _events(blocks: list[str]) -> list[dict]:
    out = []

    def walk(x):
        if isinstance(x, list):
            for i in x:
                walk(i)
        elif isinstance(x, dict):
            t = x.get("@type")
            if any(isinstance(s, str) and s.endswith("Event") for s in (t if isinstance(t, list) else [t])):
                out.append(x)
            walk(x.get("@graph", []))
    for b in blocks:
        try:
            walk(json.loads(b))
        except ValueError:
            pass
    return out


def _tokens(s) -> set[str]:
    return set(TOKEN.findall(str(s or "").casefold()))


def _day(s) -> str | None:
    m = ISO_DAY.match(str(s or "").strip())
    return m[0] if m else None


def _match(events: list[dict], title: str, start: str):
    want, sd = _tokens(title), _day(start)
    best, best_n = None, -1
    for e in events:
        ed, n = _day(e.get("startDate")), len(want & _tokens(e.get("name")))
        if sd and ed:
            ok = sd == ed
        else:
            ok = len(events) == 1 or (bool(want) and n * 2 >= len(want))
        if ok and n > best_n:
            best, best_n = e, n
    return best


def _from_event(e: dict, page_url: str) -> dict:
    offers = e.get("offers")
    offer = next((o for o in (offers if isinstance(offers, list) else [offers]) if isinstance(o, dict)
                  and (o.get("price") is not None or o.get("lowPrice") is not None or o.get("url"))), None)
    if offer is None:
        return _out("unknown", note="event found, but the page lists no offer")
    try:
        price = Decimal(str(offer.get("price", offer.get("lowPrice"))).replace(",", "."))
        price = price if price.is_finite() and 0 <= price < 100_000 else None  # bound: '1E+999999' would format to a huge string
    except InvalidOperation:
        price = None
    cur = offer.get("priceCurrency")
    url = offer.get("url")
    url = url if isinstance(url, str) and urlsplit(url).scheme == "https" else page_url
    if price == 0:
        return _out("web_form", reg=url, note="free event with a registration page")
    avail = str(offer.get("availability", ""))
    avail = ("available" if avail.endswith(("InStock", "LimitedAvailability", "PreOrder"))
             else "sold_out" if avail.endswith(("SoldOut", "OutOfStock")) else "unknown")
    label = None if price is None else f"{price:.2f}" + (f" {cur}" if isinstance(cur, str) and re.fullmatch(r"[A-Za-z]{3}", cur) else "")
    t = TicketOffer(url=url, price=label, availability=avail, checked_at=datetime.now(timezone.utc))
    return _out("tickets", ticket=t.model_dump(mode="json"), note="ticket offer read from the shop page")


def _out(signup="unknown", ticket=None, reg=None, note="") -> dict:
    return {"signup": signup, "ticket": ticket, "registration_url": reg, "note": note}


def _best_link(links, base: str, title: str, start: str) -> str | None:
    want, sd = _tokens(title), _day(start)
    pats = [sd] if sd else []
    if sd:
        pats.append(f"{sd[8:]}.{sd[5:7]}.")
    best, best_s = None, 0
    for href, text in links:
        u = urljoin(base, href.strip())
        if urlsplit(u).scheme != "https" or u == base:
            continue
        hay = f"{text} {u}".casefold()
        s = len(want & _tokens(hay)) + 2 * any(p in hay for p in pats)
        if s > best_s:
            best, best_s = u, s
    return best


def _resolve(url: str, title: str, start: str, hop: bool) -> dict:
    html, final = _fetch(url)
    if SUSPICIOUS.search(html):
        return _out(note="blocked: page looks like a prompt injection")
    page = _Page()
    page.feed(html)
    ev = _match(_events(page.ld), title, start)
    if ev:
        return _from_event(ev, final)
    if hop and (nxt := _best_link(page.links, final, title, start)):
        return _resolve(nxt, title, start, hop=False)
    return _out(note="no matching event found on the page")


def resolve_signup(url: str, title: str = "", start: str = "") -> dict:
    key = (url, title, start)
    if (hit := _cache.get(key)) and time.time() - hit[0] < TTL:
        return hit[1]
    try:
        res = _resolve(url, title, start, hop=True)
    except _Fail as e:
        res = _out(note=f"not resolved: {e}")
    except Exception as e:  # never raise into the agent
        res = _out(note=f"not resolved: {type(e).__name__}")
    _cache[key] = (time.time(), res)
    return res
