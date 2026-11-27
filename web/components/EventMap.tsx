"use client";

import { useState } from "react";
import { mapsEmbedUrl, mapsOpenUrl, mapsQuery } from "@/lib/maps";
import type { AgentState, Event } from "@/lib/types";

const TZ = "Europe/Berlin";
const when = (iso: string | null) => {
  if (!iso) return "Date TBA";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "Date TBA"
    : d.toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: TZ });
};

/** Google Map of one event at a time, picked from the list beside it. */
export function EventMap({ events, enrollments = {} }: { events: Event[]; enrollments: AgentState["enrollments"] }) {
  const located = events.filter((e) => mapsQuery(e));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = located.find((e) => e.id === selectedId) ?? located[0];

  if (!selected) {
    return (
      <div className="panel flex min-h-64 items-center justify-center p-8 text-center text-sm text-muted">
        None of these events has a venue to show on the map.
      </div>
    );
  }
  const q = mapsQuery(selected)!;

  return (
    <div className="panel grid overflow-hidden lg:grid-cols-[300px_minmax(0,1fr)]">
      <ul className="max-h-[480px] divide-y divide-line overflow-auto border-b border-line lg:border-r lg:border-b-0" aria-label="Events on the map">
        {located.map((e) => {
          const on = e.id === selected.id;
          const status = enrollments[e.id];
          return (
            <li key={e.id}>
              <button
                type="button"
                onClick={() => setSelectedId(e.id)}
                aria-pressed={on}
                className={`block min-h-11 w-full px-5 py-4 text-left transition-colors hover:bg-surface-2 ${
                  on ? "bg-accent-soft hover:bg-accent-soft" : ""
                }`}
              >
                <span className="block text-xs font-semibold text-muted">{when(e.start)}</span>
                <span className="mt-0.5 block font-bold leading-snug">{e.title}</span>
                <span className="mt-0.5 block text-sm text-muted">{mapsQuery(e)}</span>
                {status === "registered" && <span className="mt-1 block text-xs font-bold">✓ You&apos;re registered</span>}
                {status === "purchased" && <span className="mt-1 block text-xs font-bold">✓ Ticket bought</span>}
                {status === "not_needed" && <span className="mt-1 block text-xs font-bold">✓ No sign-up needed</span>}
              </button>
            </li>
          );
        })}
      </ul>
      <div className="flex min-h-[360px] flex-col">
        <iframe
          key={q}
          title={`Google Map: ${selected.title}, ${q}`}
          src={mapsEmbedUrl(q)}
          className="min-h-[360px] w-full flex-1 border-0 lg:min-h-[420px]"
          loading="lazy"
          referrerPolicy="no-referrer-when-downgrade"
        />
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-5 py-3 text-sm">
          <span className="font-semibold">{q}</span>
          <a
            href={mapsOpenUrl(q)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-h-11 items-center font-bold underline decoration-line-strong underline-offset-4 hover:decoration-ink"
          >
            Open in Google Maps
          </a>
        </div>
      </div>
    </div>
  );
}
