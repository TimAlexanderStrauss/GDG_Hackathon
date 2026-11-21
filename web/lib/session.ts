import { siFacebook, siGoogle, siInstagram, siTiktok, siX, type SimpleIcon } from "simple-icons";
import type { Platform } from "./types";

// DEMO sign-in: no OAuth, no server. A session is a small record in sessionStorage.
// Real provider login (Google OAuth, Meta/X app review) is roadmap, see web/README.md.

export type Provider = "google" | "instagram" | "x" | "facebook" | "email";
export type Social = "instagram" | "tiktok" | "x" | "facebook";

export type Session = {
  provider: Provider;
  name?: string;
  email?: string;
  /** Socials the user added in the demo "Connect" step. */
  socials: Social[];
  /** True once the user finished or skipped the socials step. */
  socialsDone: boolean;
};

export const PROVIDERS: { id: Exclude<Provider, "email">; label: string; icon: SimpleIcon }[] = [
  { id: "google", label: "Google", icon: siGoogle },
  { id: "instagram", label: "Instagram", icon: siInstagram },
  { id: "x", label: "X", icon: siX },
  { id: "facebook", label: "Facebook", icon: siFacebook },
];

export const SOCIALS: { id: Social; label: string; icon: SimpleIcon; scanned: boolean }[] = [
  { id: "instagram", label: "Instagram", icon: siInstagram, scanned: true },
  { id: "tiktok", label: "TikTok", icon: siTiktok, scanned: true },
  { id: "x", label: "X", icon: siX, scanned: false },
  { id: "facebook", label: "Facebook", icon: siFacebook, scanned: false },
];

export const providerLabel = (p: Provider) => PROVIDERS.find((x) => x.id === p)?.label ?? "email";

/** Added socials that the scouts can read today become preselected scan sources. */
export function platformsFromSocials(socials: Social[]): Platform[] {
  const picked = socials.filter((s): s is "instagram" | "tiktok" => s === "instagram" || s === "tiktok");
  return [...picked, "web"];
}

const KEY = "sidequest:session";

export function loadSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function saveSession(s: Session) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* storage unavailable: session lasts until reload */
  }
}

export function clearAll() {
  try {
    sessionStorage.clear();
  } catch {
    /* ignore */
  }
}
