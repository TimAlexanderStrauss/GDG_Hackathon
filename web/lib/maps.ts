import type { Event } from "./types";

// Keyless Google Maps: the public embed (one place per map) and the official search URL.
// A multi-pin map would need the Maps JavaScript API with a billed key (see web/README.md).

export function mapsQuery(e: Event): string | null {
  const q = [e.venue, e.city].filter(Boolean).join(", ");
  return q || null;
}

export const mapsEmbedUrl = (q: string) => `https://www.google.com/maps?q=${encodeURIComponent(q)}&output=embed`;

export const mapsOpenUrl = (q: string) =>
  `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`;
