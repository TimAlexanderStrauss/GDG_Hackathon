"""Browser agent for web forms: fake pages served via page.route (no network), real headless Chromium."""
import asyncio
from types import SimpleNamespace

import pytest
from google.genai import types

from agents.enrollment import browser
from agents.enrollment.agent import enrollment_guardrail
from mcp_servers.event_sources import resolver

URL = "https://forms.example.org/register"
THANKS = "<html><body><h1>Vielen Dank, du bist dabei!</h1></body></html>"


def form(fields: str, action="/thanks") -> str:
    return f'<html><body><form action="{action}" method="get">{fields}<button type="submit">Go</button></form></body></html>'


NAME_EMAIL = '<label for="n">Dein Name</label><input id="n" name="n" required><label for="e">E-Mail</label><input id="e" type="email" name="e" required>'
SEEN: list[str] = []


@pytest.fixture
def serve(monkeypatch, tmp_path):
    """serve(html) makes URL return html; /thanks returns a thank-you page; every other host returns a marker page."""
    monkeypatch.setattr(resolver, "_check", lambda url: None)
    monkeypatch.setattr(browser, "SHOTS", tmp_path)
    pages = {}
    SEEN.clear()
    orig = browser._context

    async def ctx(p):
        b, c = await orig(p)

        async def fake(route):
            SEEN.append(route.request.url)
            u = route.request.url.split("?")[0]
            body = pages.get(u, THANKS if u.endswith("/thanks") else "<html><body>other host</body></html>")
            await route.fulfill(status=200, content_type="text/html; charset=utf-8", body=body)

        await c.route("**/*", fake)  # registered before the domain lock, which runs first and falls back to this
        return b, c

    monkeypatch.setattr(browser, "_context", ctx)
    return lambda html: pages.__setitem__(URL, html)


def run(coro):
    try:
        return asyncio.run(coro)
    except Exception as e:  # Chromium missing or not launchable here
        if "Executable doesn't exist" in str(e) or "launch" in str(e).lower():
            pytest.skip(f"Chromium not usable: {str(e)[:80]}")
        raise


def test_simple_form_preview_then_submit_registers(serve, tmp_path):
    serve(form(NAME_EMAIL))
    p = run(browser.preview(URL, "Lea Müller", "lea@example.com", "ev1"))
    assert p["status"] == "needs_confirmation"
    assert "Lea Müller" in p["message"] and "lea@example.com" in p["message"]
    assert (tmp_path / p["screenshot"]).exists() and "ev1-preview-" in p["screenshot"]
    assert not any("/thanks" in u for u in SEEN)  # preview does not submit
    s = run(browser.submit(URL, "Lea Müller", "lea@example.com", "ev1"))
    assert s["status"] == "registered" and "ev1-submit-" in s["screenshot"]
    assert any("e=lea%40example.com" in u for u in SEEN)


def test_given_and_family_name_fields_are_split(serve):
    serve(form('<input name="vorname" autocomplete="given-name" required><input name="nachname" required><input type="email" name="m">'))
    p = run(browser.preview(URL, "Lea Marie Müller", "lea@example.com"))
    assert "- vorname: Lea" in p["message"] and "- nachname: Marie Müller" in p["message"]


def test_required_privacy_checkbox_is_listed_and_ticked(serve):
    serve(form(NAME_EMAIL + '<input type="checkbox" id="c" name="privacy" required><label for="c">Ich akzeptiere die Datenschutzerklärung</label>',
               action="/thanks"))
    p = run(browser.preview(URL, "Lea", "lea@example.com"))
    assert "Will be ticked" in p["message"] and "Datenschutzerklärung" in p["message"]
    run(browser.submit(URL, "Lea", "lea@example.com"))
    assert any("privacy=on" in u for u in SEEN)


@pytest.mark.parametrize("fields, reason", [
    (NAME_EMAIL + '<input type="password" name="pw">', "login"),
    (NAME_EMAIL + '<iframe src="https://www.google.com/recaptcha/api2/anchor"></iframe>', "captcha"),
    (NAME_EMAIL + '<select name="t" required><option value="">-</option><option>A</option></select>', "cannot be filled"),
    ("<p>no form here</p>", "No form"),
])
def test_stop_rules_give_manual_with_reason(serve, fields, reason):
    serve(fields if "<form" in fields or fields.startswith("<p>") else form(fields))
    p = run(browser.preview(URL, "Lea", "lea@example.com"))
    assert p["status"] == "manual" and reason in p["message"] and p["link"] == URL
    assert not any("/thanks" in u for u in SEEN)


def test_navigation_to_another_host_is_blocked(serve):
    serve(form(NAME_EMAIL, action="https://evil.example.net/steal"))
    s = run(browser.submit(URL, "Lea", "lea@example.com"))
    assert s["status"] == "manual" and "Not submitted" in s["message"] and "evil.example.net" in s["message"]
    assert not any("evil.example.net" in u for u in SEEN)


def test_newsletter_form_before_the_registration_is_skipped(serve):
    newsletter = '<form action="/newsletter"><input type="email" name="nl" required><button>Abo</button></form>'
    serve(f'<html><body>{newsletter}{form(NAME_EMAIL)[12:]}')
    p = run(browser.preview(URL, "Lea", "lea@example.com"))
    assert p["status"] == "needs_confirmation" and "Dein Name" in p["message"]
    s = run(browser.submit(URL, "Lea", "lea@example.com"))
    assert s["status"] == "registered" and not any("/newsletter" in u for u in SEEN)


def test_success_word_already_on_the_form_is_no_success(serve):
    # the form posts back to its own page, which still says "Ich bestätige ...": nothing new, no success
    serve(form(NAME_EMAIL + "<p>Ich bestätige die Teilnahmebedingungen.</p>", action="/register"))
    s = run(browser.submit(URL, "Lea", "lea@example.com"))
    assert s["status"] == "manual" and "no confirmation" in s["message"]


def test_url_must_pass_the_public_https_check(monkeypatch):
    monkeypatch.undo()
    assert run(browser.preview("http://forms.example.org/x", "Lea", "lea@example.com"))["status"] == "failed"


# --- guardrail ---
APPROVED, CONFIRMED = "2026-11-21T14:00:00Z", "2026-11-21T14:01:00Z"


def _req(signup="web_form", confirmed=CONFIRMED) -> SimpleNamespace:
    c = f', "confirmed_at": "{confirmed}"' if confirmed else ""
    text = (f'{{"event": {{"id": "abc123def456", "title": "T", "platform": "web", "source_url": "https://x.example/p", '
            f'"registration_url": "{URL}", "signup": "{signup}"}}, "attendee_name": "Lea", "attendee_email": "lea@example.com", '
            f'"approved_at": "{APPROVED}"{c}}}')
    return SimpleNamespace(user_content=types.Content(role="user", parts=[types.Part(text=text)]))


def _args(**o):
    return {"form_url": URL, "name": "Lea", "email": "lea@example.com", "approved_at": APPROVED, "confirmed_at": CONFIRMED} | o


PREVIEW, SUBMIT = SimpleNamespace(name="preview_web_form"), SimpleNamespace(name="submit_web_form")


def test_guardrail_allows_preview_and_confirmed_submit():
    assert enrollment_guardrail(PREVIEW, _args(), _req(confirmed=None)) is None
    assert enrollment_guardrail(SUBMIT, _args(), _req()) is None


@pytest.mark.parametrize("tool, args, req", [
    (SUBMIT, _args(), _req(confirmed=None)),  # no confirmation in the request
    (SUBMIT, _args(confirmed_at="2026-11-21T14:09:00Z"), _req()),  # invented confirmation
    (SUBMIT, _args(confirmed_at=""), _req()),
    (SUBMIT, _args(form_url="https://evil.example.net/register"), _req()),
    (PREVIEW, _args(form_url="https://evil.example.net/register"), _req()),
    (PREVIEW, _args(approved_at="2026-11-21T15:00:00Z"), _req()),
    (PREVIEW, _args(), _req(signup="google_form")),
    (SUBMIT, _args(), _req(signup="message")),
    (PREVIEW, _args(email="attacker@example.net"), _req(confirmed=None)),  # name/email only from the request
    (SUBMIT, _args(name="Someone Else"), _req()),
    (SimpleNamespace(name="submit_google_form"), _args(email="attacker@example.net"), _req(signup="google_form")),
])
def test_guardrail_blocks(tool, args, req):
    assert enrollment_guardrail(tool, args, req)["status"] == "failed"
