// Re-export the shared contracts. Type-only, so nothing outside web/ is bundled.
export type {
  AgentState,
  EnrollmentResult,
  Event,
  Platform,
  UserProfile,
} from "../../shared/schemas";

import type { Platform } from "../../shared/schemas";

/** Sources the scouts can read today (must match `Platform` in shared/schemas). */
export const PLATFORMS: { id: Platform; label: string }[] = [
  { id: "instagram", label: "Instagram" },
  { id: "tiktok", label: "TikTok" },
  { id: "web", label: "Web" },
];

/**
 * Shown but locked: not in the shared `Platform` contract and no scout reads them yet.
 * To enable one, the team extends `Platform` in shared/schemas.py + .ts and P2 adds a scout;
 * then move it into PLATFORMS.
 */
export const PLANNED_PLATFORMS = [
  { id: "x", label: "X" },
  { id: "facebook", label: "Facebook" },
] as const;

/** Reply of the `choose_event` human-in-the-loop tool. */
export type ChooseEventResponse =
  | { event_id: string; approved_at: string }
  | { event_id: null; approved_at: null; declined: true };
