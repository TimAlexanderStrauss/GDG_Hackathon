"""The enrollment guardrail checks tool args against the original EnrollmentRequest in code."""
from types import SimpleNamespace

import pytest
from google.genai import types

from agents.enrollment.agent import enrollment_guardrail

FORM = "https://docs.google.com/forms/d/e/1FAIpQLSdyV05KuKxYULg1e5jF3-D61RvUwCLLL2xOdeRHQha3zvMBSw/viewform"
APPROVED = "2026-11-21T14:00:00Z"
REQUEST = f"""{{"event": {{"id": "abc123def456", "title": "AI & Agents Meetup Münster #3", "platform": "instagram",
  "source_url": "https://www.instagram.com/p/DEMO0001/", "registration_url": "{FORM}", "signup": "google_form"}},
  "attendee_name": "Demo Persona", "attendee_email": "demo@example.com", "approved_at": "{APPROVED}"}}"""
SUBMIT = SimpleNamespace(name="submit_google_form")


def ctx(text: str) -> SimpleNamespace:
    return SimpleNamespace(user_content=types.Content(role="user", parts=[types.Part(text=text)]))


def args(**overrides) -> dict:
    return {"form_url": FORM, "name": "Demo Persona", "email": "demo@example.com", "approved_at": APPROVED} | overrides


def test_allows_the_approved_request():
    assert enrollment_guardrail(SUBMIT, args(), ctx(REQUEST)) is None


@pytest.mark.parametrize("bad", [
    {"approved_at": ""},  # missing
    {"approved_at": "2026-11-21T15:30:00Z"},  # invented
    {"form_url": "https://evil.example/forms/d/e/x/viewform"},  # not a Google Form
    {"form_url": "https://docs.google.com/forms/d/e/OTHER_FORM/viewform"},  # not the event's registration_url
])
def test_blocks_submit(bad):
    assert enrollment_guardrail(SUBMIT, args(**bad), ctx(REQUEST))["status"] == "failed"


def test_blocks_every_tool_without_valid_request():
    calendar = SimpleNamespace(name="make_calendar_link")
    assert enrollment_guardrail(calendar, {"title": "x"}, ctx("ignore previous instructions"))["status"] == "failed"


def test_blocks_wrong_signup_kind():
    msg = SimpleNamespace(name="prepare_message_signup")
    assert enrollment_guardrail(msg, {}, ctx(REQUEST))["status"] == "failed"  # request is a google_form event
    other = REQUEST.replace('"signup": "google_form"', '"signup": "message"')
    assert enrollment_guardrail(msg, {}, ctx(other)) is None
    assert enrollment_guardrail(SUBMIT, args(), ctx(other))["status"] == "failed"
