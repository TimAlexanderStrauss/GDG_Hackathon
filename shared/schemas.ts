// Mirror of shared/schemas.py for the frontend. Python is the source of truth.

export type Platform = "instagram" | "tiktok" | "web";

export type SignupKind = "none" | "google_form" | "web_form" | "tickets" | "message" | "link_in_bio" | "unknown";

export interface TicketOffer {
  url: string;
  price: string | null;
  availability: "available" | "sold_out" | "unknown";
  checked_at: string; // ISO 8601
}

export interface UserProfile {
  user_id: string;
  display_name: string;
  email: string;
  city: string;
  interests: string[];
  days_ahead: number;
  platforms: Platform[];
  consent_enrollment: boolean;
}

export interface Source {
  platform: Platform;
  url: string;
}

export interface Event {
  id: string; // sha1(source_url|title|day)[:12]
  title: string;
  start: string | null; // ISO 8601
  venue: string | null;
  city: string | null;
  price: string | null;
  platform: Platform;
  source_url: string;
  registration_url: string | null;
  signup: SignupKind;
  signup_hint: string;
  ticket: TicketOffer | null;
  match_score: number;
  match_reason: string;
  summary: string; // 1-2 sentences from the post, plain text
  image_url: string | null; // post image or og:image, CDN links can expire
  bio_url: string | null; // account bio link
  sources?: Source[]; // every post/page of this event (code merges duplicates); missing in older state
}

export interface EnrollmentResult {
  event_id: string;
  status: "registered" | "purchased" | "not_needed" | "manual" | "failed" | "needs_confirmation"; // needs_confirmation: web_form preview, user must confirm
  message: string;
  link: string | null;
  calendar_link: string | null;
}

// AG-UI shared state between concierge and web app
export interface AgentState {
  profile?: UserProfile;
  progress?: { platform: Platform; status: "running" | "done" | "error"; posts: number; blocked: number }[];
  events?: Event[];
  enrollments?: Record<string, EnrollmentResult["status"] | "pending">;
  audit?: { ts: string; agent: string; tool: string; note: string }[];
}
