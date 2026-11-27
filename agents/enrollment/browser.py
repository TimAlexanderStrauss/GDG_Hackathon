"""Phase 4: fills a free registration page (signup "web_form") in a real browser, in two steps.

Deterministic Playwright code. No page text ever goes to an LLM: code maps the fields and decides.
preview() fills the form and stops (screenshot, planned values); submit() does it again and clicks submit.
"""
import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import async_playwright

from mcp_servers.event_sources import resolver

SHOTS = Path(__file__).resolve().parents[2] / "data" / "screenshots"
TIMEOUT_MS = 20_000
CAPTCHA = re.compile(r"recaptcha|hcaptcha|turnstile|captcha", re.I)
EMAIL_KEY = re.compile(r"mail", re.I)
GIVEN_KEY = re.compile(r"vorname|first|given", re.I)
FAMILY_KEY = re.compile(r"nachname|family|last|surname", re.I)
NAME_KEY = re.compile(r"name|vorname|nachname|first|last", re.I)
SUCCESS = re.compile(r"danke|vielen dank|thank you|bestätig|confirm|erfolgreich|angemeldet|registered", re.I)

# Reads every form with visible fields and the keys the mapping needs. Runs in the page, returns plain data only.
_READ_FORMS = """() => {
  const label = e => ((e.labels && e.labels.length ? [...e.labels].map(l => l.innerText).join(' ') : '')
    || e.getAttribute('aria-label') || e.placeholder || '').trim();
  let i = 0;
  return [...document.forms].map((f, k) => {
    f.setAttribute('data-sq-form', k);
    const fields = [...f.querySelectorAll('input,select,textarea')]
      .filter(e => !['hidden', 'submit', 'button', 'image', 'reset'].includes(e.type) && getComputedStyle(e).display !== 'none')
      .map(e => { e.setAttribute('data-sq', i); return {i: i++, tag: e.tagName.toLowerCase(), type: e.type || '',
        name: e.name || '', id: e.id || '', autocomplete: e.autocomplete || '', label: label(e),
        required: e.required || e.getAttribute('aria-required') === 'true'}; });
    return {k, fields, captcha: /captcha/i.test(f.outerHTML)};
  }).filter(f => f.fields.length);
}"""


class _Stop(Exception):
    """The form cannot be completed by code: the user does it by hand. The message is the reason."""


def _split_name(name: str) -> tuple[str, str]:
    first, _, rest = name.strip().partition(" ")
    return first, rest


def _plan(form: dict, name: str, email: str) -> tuple[list[tuple[int, str, str]], list[tuple[int, str]]]:
    """(entries (index, label, value), checkboxes (index, label)). Raises _Stop on every stop rule."""
    if form["captcha"]:
        raise _Stop("The form has a captcha.")
    given, family = _split_name(name)
    entries, boxes = [], []
    for f in form["fields"]:
        key = " ".join((f["name"], f["id"], f["label"], f["autocomplete"]))
        label = f["label"] or f["name"] or f["id"] or f["type"]
        if f["type"] == "password":
            raise _Stop("The page needs a login or an account (password field).")
        if f["type"] == "checkbox":
            if f["required"]:
                boxes.append((f["i"], label))
            continue
        if f["tag"] == "input" and f["type"] in ("", "text", "email") or f["tag"] == "textarea":
            if f["type"] == "email" or EMAIL_KEY.search(key):
                entries.append((f["i"], "E-Mail", email))
                continue
            if f["tag"] == "input" and (f["autocomplete"] in ("name", "given-name", "family-name") or NAME_KEY.search(key)):
                ac = f["autocomplete"]
                if ac == "given-name" or (not ac and GIVEN_KEY.search(key)):
                    entries.append((f["i"], label, given))
                elif ac == "family-name" or (not ac and FAMILY_KEY.search(key)):
                    entries.append((f["i"], label, family or given))
                else:
                    entries.append((f["i"], label, name))
                continue
        if f["required"]:
            raise _Stop(f"A required field cannot be filled by code: {label!r} ({f['tag']}/{f['type']}).")
    if not any(lbl == "E-Mail" for _, lbl, _ in entries) or all(lbl == "E-Mail" for _, lbl, _ in entries):
        # a form without name and email is not a registration (e.g. a newsletter or search form in the header)
        raise _Stop("No form with a name and an email field found.")
    return entries, boxes


def _choose(forms: list[dict], name: str, email: str):
    """The first form that code can complete. Else the stop reason of the first form."""
    stops = []
    for form in forms:
        try:
            return form["k"], *_plan(form, name, email)
        except _Stop as e:
            stops.append(e)
    raise stops[0] if stops else _Stop("No form found on the page.")


def _result(status: str, message: str, url: str, shot: Path | None = None) -> dict:
    return {"status": status, "message": message, "link": url, "screenshot": shot.name if shot else None}


async def _run(url: str, name: str, email: str, event_id: str, submit: bool) -> dict:
    try:
        await asyncio.to_thread(resolver._check, url)  # https + public IP; the caller (guardrail) checked url == registration_url
    except Exception as e:
        return _result("failed", f"Blocked: {e}", url)
    host, step = urlsplit(url).hostname, "submit" if submit else "preview"
    # shortcut: runs on the host, not in a container. Upgrade: container/VM when other users use the app.
    async with async_playwright() as p:
        browser, context = await _context(p)
        try:
            page = await context.new_page()

            blocked: list[str] = []

            async def lock(route):  # domain lock: no page navigation to another host (css/js/images of other hosts are fine)
                req = route.request
                if req.is_navigation_request() and req.frame.parent_frame is None and urlsplit(req.url).hostname != host:
                    blocked.append(urlsplit(req.url).hostname or "?")
                    await route.abort()
                else:
                    await route.fallback()

            await context.route("**/*", lock)
            try:
                await page.goto(url)
                forms = await page.evaluate(_READ_FORMS)
                if any(CAPTCHA.search(fr.url) for fr in page.frames[1:]):
                    for form in forms:
                        form["captcha"] = True
                k, entries, boxes = _choose(forms, name, email)
                for i, _, value in entries:
                    await page.fill(f'[data-sq="{i}"]', value)
                for i, _ in boxes:
                    await page.check(f'[data-sq="{i}"]')
                if submit:
                    before = len(SUCCESS.findall(await page.inner_text("body")))
                    await page.locator(f'[data-sq-form="{k}"] :is([type=submit], button:not([type=button]):not([type=reset]))').first.click()
                    try:
                        await page.wait_for_load_state("networkidle", timeout=5_000)
                    except Exception:  # pages that never go idle: judge what is there
                        pass
                SHOTS.mkdir(parents=True, exist_ok=True)
                shot = SHOTS / f"{event_id}-{step}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.png"
                await page.screenshot(path=str(shot), full_page=True)
                if not submit:
                    lines = [f"Planned entries on {host}:"] + [f"- {lbl}: {v}" for _, lbl, v in entries]
                    if boxes:
                        lines += ["Will be ticked:"] + [f"- {lbl}" for _, lbl in boxes]
                    return _result("needs_confirmation", "\n".join(lines), url, shot)
                if blocked:
                    return _result("manual", f"Not submitted: the form sends to another site ({blocked[0]}). "
                                             "Please register yourself via the link.", url, shot)
                # success words count only if new after the click: forms often say "Ich bestätige ..." already
                after = len(SUCCESS.findall(await page.inner_text("body")))
                if urlsplit(page.url).hostname == host and (urlsplit(page.url).path != urlsplit(url).path or after > before):
                    return _result("registered", f"Registered {name} via the web form on {host}.", url, shot)
                return _result("manual", "Submitted, but no confirmation page detected — check your email.", url, shot)
            except _Stop as e:
                return _result("manual", f"{e} Please register yourself via the link.", url)
            except Exception as e:  # timeout, page crashed, selector gone
                return _result("failed", f"The browser could not complete the form ({type(e).__name__}).", url)
        finally:
            await context.close()
            await browser.close()


async def _context(p):
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context()  # fresh context per call: no cookies, no storage
    context.set_default_timeout(TIMEOUT_MS)
    return browser, context


async def preview(url: str, name: str, email: str, event_id: str = "event") -> dict:
    """Fills the form and stops before the submit. status needs_confirmation (message = planned values) or manual."""
    return await _run(url, name, email, event_id, submit=False)


async def submit(url: str, name: str, email: str, event_id: str = "event") -> dict:
    """Fills the form, ticks the required checkboxes and clicks submit. status registered only on a success page."""
    return await _run(url, name, email, event_id, submit=True)
