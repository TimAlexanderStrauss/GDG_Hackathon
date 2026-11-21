import { PLATFORMS, type Platform, type UserProfile } from "./types";

export const SUGGESTED_INTERESTS = [
  "AI",
  "Techno",
  "Startups",
  "Live music",
  "Running",
  "Markets",
  "Food",
  "Art",
  "Networking",
  "Workshops",
];

export const DAYS_MIN = 1;
export const DAYS_MAX = 60;
export const MAX_INTERESTS = 12;

const PLATFORM_IDS = PLATFORMS.map((p) => p.id);
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export type ProfileDraft = Omit<UserProfile, "user_id">;

export const EMPTY_DRAFT: ProfileDraft = {
  display_name: "",
  email: "",
  city: "Münster",
  interests: [],
  days_ahead: 14,
  platforms: ["instagram", "tiktok", "web"],
  consent_enrollment: false,
};

export type DraftErrors = Partial<Record<keyof ProfileDraft, string>>;

/** Mirrors shared/schemas.py UserProfile, plus the UX limits shown in the form. */
export function validateDraft(d: ProfileDraft): DraftErrors {
  const e: DraftErrors = {};
  if (!d.display_name.trim()) e.display_name = "Enter your name.";
  if (!EMAIL_RE.test(d.email.trim())) e.email = "Enter a valid email address.";
  if (!d.city.trim()) e.city = "Enter a city.";
  if (d.interests.length === 0) e.interests = "Pick at least one interest.";
  if (d.interests.length > MAX_INTERESTS) e.interests = `Pick at most ${MAX_INTERESTS}.`;
  if (!Number.isInteger(d.days_ahead) || d.days_ahead < DAYS_MIN || d.days_ahead > DAYS_MAX)
    e.days_ahead = `Choose ${DAYS_MIN} to ${DAYS_MAX} days.`;
  if (d.platforms.length === 0) e.platforms = "Pick at least one source.";
  if (d.platforms.some((p) => !PLATFORM_IDS.includes(p))) e.platforms = "Unknown source.";
  return e;
}

export function toProfile(d: ProfileDraft, userId: string): UserProfile {
  return {
    user_id: userId,
    display_name: d.display_name.trim(),
    email: d.email.trim(),
    city: d.city.trim(),
    interests: d.interests.map((i) => i.trim()).filter(Boolean),
    days_ahead: d.days_ahead,
    platforms: d.platforms,
    consent_enrollment: d.consent_enrollment === true,
  };
}

// ---------- session storage (per-viewer convenience only) ----------

const UID_KEY = "sidequest:user_id";
const PROFILE_KEY = "sidequest:profile";

export function sessionUserId(): string {
  try {
    const existing = sessionStorage.getItem(UID_KEY);
    if (existing) return existing;
    const id = `u_${crypto.randomUUID().replace(/-/g, "").slice(0, 12)}`;
    sessionStorage.setItem(UID_KEY, id);
    return id;
  } catch {
    return `u_${Math.random().toString(36).slice(2, 14)}`;
  }
}

export function loadSavedProfile(): UserProfile | null {
  try {
    const raw = sessionStorage.getItem(PROFILE_KEY);
    return raw ? (JSON.parse(raw) as UserProfile) : null;
  } catch {
    return null;
  }
}

export function saveProfile(p: UserProfile) {
  try {
    sessionStorage.setItem(PROFILE_KEY, JSON.stringify(p));
  } catch {
    /* storage unavailable: the profile still lives in agent state */
  }
}

// ---------- import from another AI assistant ----------

export const IMPORT_PROMPT = `I'm setting up Sidequest, an app that finds local events in public social media posts. Based on what you know about me, fill in this JSON. Only include what you are fairly sure about and use null for anything you don't know. Do not include my email, phone number or anything sensitive. Reply with the JSON only.

{
  "display_name": "first name or nickname, or null",
  "city": "city I live in or want events in, or null",
  "interests": ["up to 8 short topics, e.g. AI, Techno, Running"],
  "days_ahead": "how many days ahead to look, 1-60, or null",
  "platforms": ["any of: instagram, tiktok, web"]
}`;

export type ImportResult = {
  patch: Partial<Pick<ProfileDraft, "display_name" | "city" | "interests" | "days_ahead" | "platforms">>;
  filled: (keyof ProfileDraft)[];
  ignored: string[];
};

function str(v: unknown): string | undefined {
  return typeof v === "string" && v.trim() && v.trim().toLowerCase() !== "null" ? v.trim().slice(0, 80) : undefined;
}

function list(v: unknown): string[] {
  if (Array.isArray(v)) return v.map(str).filter((x): x is string => !!x);
  const s = str(v);
  return s ? s.split(/[,;|]/).map((x) => x.trim()).filter(Boolean) : [];
}

function extractObject(text: string): Record<string, unknown> | null {
  const cleaned = text.replace(/```(?:json)?/gi, "");
  const start = cleaned.indexOf("{");
  const end = cleaned.lastIndexOf("}");
  if (start !== -1 && end > start) {
    try {
      const v = JSON.parse(cleaned.slice(start, end + 1));
      if (v && typeof v === "object" && !Array.isArray(v)) return v as Record<string, unknown>;
    } catch {
      /* fall through to line parsing */
    }
  }
  // "Key: value" lines, e.g. "City: Münster"
  const out: Record<string, unknown> = {};
  for (const line of cleaned.split("\n")) {
    const m = line.match(/^\s*[-*]?\s*"?([a-z _]+)"?\s*[:=]\s*(.+?)\s*,?$/i);
    if (m) out[m[1].trim().toLowerCase().replace(/\s+/g, "_")] = m[2].replace(/^"|"$/g, "");
  }
  return Object.keys(out).length ? out : null;
}

const ALIASES: Record<string, keyof ImportResult["patch"]> = {
  display_name: "display_name",
  name: "display_name",
  first_name: "display_name",
  city: "city",
  location: "city",
  interests: "interests",
  topics: "interests",
  days_ahead: "days_ahead",
  days: "days_ahead",
  platforms: "platforms",
  sources: "platforms",
};

/**
 * Turns a pasted reply (JSON or "key: value" lines) into form values.
 * Imported text is preference data only: email and consent are never taken from it.
 */
export function parseImport(text: string): ImportResult | null {
  const obj = extractObject(text);
  if (!obj) return null;
  const patch: ImportResult["patch"] = {};
  const ignored: string[] = [];

  for (const [rawKey, value] of Object.entries(obj)) {
    const key = ALIASES[rawKey.toLowerCase()];
    if (!key) {
      ignored.push(rawKey);
      continue;
    }
    if (key === "display_name" || key === "city") {
      const s = str(value);
      if (s) patch[key] = s;
    } else if (key === "interests") {
      const items = [...new Set(list(value).map((x) => x.slice(0, 30)))].slice(0, 8);
      if (items.length) patch.interests = items;
    } else if (key === "days_ahead") {
      const n = Math.round(Number(value));
      if (Number.isFinite(n) && n >= DAYS_MIN && n <= DAYS_MAX) patch.days_ahead = n;
    } else if (key === "platforms") {
      const ps = list(value)
        .map((x) => x.toLowerCase())
        .filter((x): x is Platform => (PLATFORM_IDS as string[]).includes(x));
      if (ps.length) patch.platforms = [...new Set(ps)];
    }
  }

  const filled = Object.keys(patch) as (keyof ProfileDraft)[];
  return filled.length ? { patch, filled, ignored } : null;
}
