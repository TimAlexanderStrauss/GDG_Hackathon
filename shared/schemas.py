"""Shared contracts between all agents. Single source of truth: change only after team agreement.

Mirror for the frontend: shared/schemas.ts (keep both in sync by hand).
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, HttpUrl

Platform = Literal["instagram", "tiktok", "web"]
# How you get into an event. Code sets the final value, the curator LLM only proposes it (PLAN.md, section 3).
# link_in_bio is an intermediate value: the resolver step replaces it.
SignupKind = Literal["none", "google_form", "web_form", "tickets", "message", "link_in_bio", "unknown"]


class UserProfile(BaseModel):
    """P1 (Onboarding) writes it into the AG-UI state, all agents read it."""
    user_id: str
    display_name: str
    email: str  # only goes to the enrollment agent after the user clicks "Enroll me"
    city: str = "Münster"
    interests: list[str]  # e.g. ["AI", "Techno", "Startups"]
    days_ahead: int = 14
    platforms: list[Platform] = ["instagram", "tiktok", "web"]
    consent_enrollment: bool = False


class SocialPost(BaseModel):
    """P2: what the event-sources MCP server returns (fixtures have the same shape). Untrusted input!"""
    platform: Platform
    url: HttpUrl
    text: str
    posted_at: datetime
    location: str | None = None
    author_bio_url: HttpUrl | None = None  # bio link of the account, from the data provider
    image_url: HttpUrl | None = None  # post image / video cover / og:image, from the data provider (CDN links expire)


class TicketOffer(BaseModel):
    """Read by the resolver from the shop page (schema.org JSON-LD), never from the post or an LLM."""
    url: HttpUrl  # shop page for this event
    price: str | None = None  # e.g. "10.00 EUR"
    availability: Literal["available", "sold_out", "unknown"] = "unknown"
    checked_at: datetime


class Source(BaseModel):
    """One post or page that announces an event."""
    platform: Platform
    url: HttpUrl


class Event(BaseModel):
    """P2 (scouts/curator) produces it, P3 (display) shows it, P4 (enrollment) uses it."""
    id: str  # sha1(source_url|title|day)[:12]: a web page can list several events
    title: str
    start: datetime | None = None
    venue: str | None = None
    city: str | None = None
    price: str | None = None
    platform: Platform
    source_url: HttpUrl
    registration_url: HttpUrl | None = None
    signup: SignupKind = "unknown"
    signup_hint: str = ""  # quote from the post, e.g. "Eintritt 10 € an der Kasse", or the resolver's NO_PRESALE note
    ticket: TicketOffer | None = None
    match_score: float = 0.0  # 0..1
    match_reason: str = ""  # "Matches: AI, evenings, Münster"
    summary: str = ""  # 1-2 sentences from the post (LLM, plain text, shown as text only)
    image_url: HttpUrl | None = None  # code copies it from the post, never from the LLM
    bio_url: HttpUrl | None = None  # account bio link, code copies it from the post (for "Link in Bio" posts)
    sources: list[Source] = []  # every post/page of this event (code merges duplicates), source_url is one of them


class EnrollmentRequest(BaseModel):
    """Concierge -> enrollment agent (A2A). Without approved_at the enrollment agent refuses."""
    event: Event
    attendee_name: str
    attendee_email: str
    approved_at: datetime  # time of the "Enroll me" click = audit proof
    confirmed_at: datetime | None = None  # web_form: time of the "Submit" click after the preview; None = preview only


class EnrollmentResult(BaseModel):
    event_id: str
    status: Literal["registered", "purchased", "not_needed", "manual", "failed", "needs_confirmation"]  # needs_confirmation: web_form preview
    message: str  # confirmation or step-by-step instructions
    link: HttpUrl | None = None
    calendar_link: str | None = None  # Google Calendar template link
