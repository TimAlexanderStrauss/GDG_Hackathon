"""Shared contracts between all agents. Single source of truth: change only after team agreement.

Mirror for the frontend: shared/schemas.ts (keep both in sync by hand).
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, HttpUrl

Platform = Literal["instagram", "tiktok", "web"]


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


class Event(BaseModel):
    """P2 (scouts/curator) produces it, P3 (display) shows it, P4 (enrollment) uses it."""
    id: str  # sha1(source_url)[:12]
    title: str
    start: datetime | None = None
    venue: str | None = None
    city: str | None = None
    price: str | None = None
    platform: Platform
    source_url: HttpUrl
    registration_url: HttpUrl | None = None
    enrollment_mode: Literal["auto", "manual", "unknown"] = "unknown"  # auto = Google Form
    match_score: float = 0.0  # 0..1
    match_reason: str = ""  # "Passt zu: AI, abends, Münster"


class EnrollmentRequest(BaseModel):
    """Concierge -> enrollment agent (A2A). Without approved_at the enrollment agent refuses."""
    event: Event
    attendee_name: str
    attendee_email: str
    approved_at: datetime  # time of the "Enroll me" click = audit proof


class EnrollmentResult(BaseModel):
    event_id: str
    status: Literal["registered", "manual", "failed"]
    message: str  # confirmation or step-by-step instructions
    link: HttpUrl | None = None
    calendar_link: str | None = None  # Google Calendar template link
