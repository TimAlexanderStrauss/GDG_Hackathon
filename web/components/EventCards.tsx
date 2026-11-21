"use client";

import { siInstagram, siTiktok } from "simple-icons";
import { answerChoice, useChoice } from "@/lib/choice-store";
import { PLATFORMS, type AgentState, type Event, type Platform } from "@/lib/types";
import { BrandIcon } from "./BrandIcon";

type Status = NonNullable<AgentState["enrollments"]>[string];

const STATUS: Record<Status, { text: string; cls: string }> = {
  pending: { text: "Enrolling…", cls: "bg-warn-soft text-warn" },
  registered: { text: "✓ You're registered", cls: "bg-accent-soft text-ink" },
  manual: { text: "Sign-up steps in chat", cls: "bg-accent-soft text-ink" },
  failed: { text: "Enrollment failed", cls: "bg-bad-soft text-bad" },
};

const TZ = "Europe/Berlin";

function dateParts(iso: string | null) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return {
    weekday: d.toLocaleDateString("en-GB", { weekday: "short", timeZone: TZ }),
    day: d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: TZ }),
    time: d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: TZ }),
  };
}

export function SourceLabel({ platform }: { platform: Platform }) {
  const label = PLATFORMS.find((p) => p.id === platform)?.label ?? platform;
  return (
    <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-muted">
      {platform === "instagram" ? (
        <BrandIcon icon={siInstagram} size={16} />
      ) : platform === "tiktok" ? (
        <BrandIcon icon={siTiktok} size={16} />
      ) : (
        <svg aria-hidden viewBox="0 0 24 24" width={16} height={16} fill="none" stroke="currentColor" strokeWidth={2}>
          <circle cx="12" cy="12" r="9" />
          <path d="M3 12h18M12 3c2.5 2.7 2.5 15.3 0 18M12 3c-2.5 2.7-2.5 15.3 0 18" />
        </svg>
      )}
      {label}
    </span>
  );
}


type Props = {
  events: Event[];
  enrollments: AgentState["enrollments"];
  consent: boolean;
  /** Compact = inside the chat. */
  compact?: boolean;
  /** Restrict the enroll buttons to one pending choose_event call. */
  toolCallId?: string;
};

export function EventCards({ events, enrollments = {}, consent, compact, toolCallId }: Props) {
  const { pending, answered } = useChoice();
  const active = pending && (!toolCallId || pending.toolCallId === toolCallId) ? pending : null;
  const choosable = new Set(active?.events.map((e) => e.id));
  const chosenId = toolCallId ? answered[toolCallId]?.event_id : undefined;

  const enroll = (id: string) =>
    active && answerChoice(active.toolCallId, { event_id: id, approved_at: new Date().toISOString() });

  return (
    <ul className={compact ? "space-y-2" : "grid gap-4 sm:grid-cols-2 2xl:grid-cols-3"}>
      {events.map((e) => {
        const status = enrollments[e.id];
        const s = status ? STATUS[status] : null;
        const d = dateParts(e.start);
        const canEnroll = !!active && choosable.has(e.id);
        const label = consent && e.enrollment_mode === "auto" ? "Enroll me" : "Get sign-up steps";
        const meta = [d?.time, e.price].filter(Boolean).join(" · ");

        if (compact) {
          return (
            <li key={e.id} className={`panel p-3 ${chosenId === e.id ? "ring-2 ring-accent" : ""}`}>
              <p className="text-xs font-semibold text-muted">
                {d ? `${d.weekday} ${d.day}` : "Date TBA"} · {PLATFORMS.find((p) => p.id === e.platform)?.label}
              </p>
              <p className="mt-0.5 font-bold leading-snug">{e.title}</p>
              {s ? (
                <p className={`mt-2 inline-block rounded-full px-3 py-1 text-xs font-bold ${s.cls}`}>{s.text}</p>
              ) : canEnroll ? (
                <button type="button" className="btn btn-primary btn-sm mt-2 w-full" onClick={() => enroll(e.id)}>
                  {label}
                </button>
              ) : null}
            </li>
          );
        }

        return (
          <li
            key={e.id}
            className={`panel relative flex flex-col overflow-hidden p-6 transition-transform duration-150 hover:-translate-y-0.5 ${
              chosenId === e.id ? "ring-2 ring-accent" : ""
            }`}
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- decorative static SVG */}
            <img
              src="/sidequest-mark.svg"
              alt=""
              aria-hidden
              className="pointer-events-none absolute top-5 right-5 h-12 w-12"
            />

            <div className="flex items-center gap-3 pr-16">
              <div className="rounded-[10px] bg-surface-2 px-2.5 py-1.5 text-center leading-tight">
                {d ? (
                  <>
                    <p className="text-xs font-bold">{d.weekday}</p>
                    <p className="text-sm font-extrabold">{d.day}</p>
                  </>
                ) : (
                  <p className="text-xs font-bold">Date TBA</p>
                )}
              </div>
              <SourceLabel platform={e.platform} />
            </div>

            <h3 className="mt-5 text-2xl leading-[1.1]">{e.title}</h3>

            <div className="mt-4 space-y-1 text-[0.9375rem]">
              {(e.venue || e.city) && (
                <p className="flex items-start gap-2 font-semibold">
                  <svg
                    aria-hidden
                    viewBox="0 0 24 24"
                    width={18}
                    height={18}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    className="mt-0.5 shrink-0"
                  >
                    <path d="M12 21s-7-5.5-7-11a7 7 0 1 1 14 0c0 5.5-7 11-7 11z" />
                    <circle cx="12" cy="10" r="2.5" />
                  </svg>
                  <span>{[e.venue, e.city].filter(Boolean).join(", ")}</span>
                </p>
              )}
              {meta && <p className="pl-[26px] text-muted">{meta}</p>}
            </div>

            {e.match_reason && (
              <p className="mt-3 text-sm text-muted">
                {e.match_reason}
                <span className="ml-1 font-semibold text-ink">
                  · {Math.round(Math.max(0, Math.min(1, e.match_score)) * 100)}% match
                </span>
              </p>
            )}

            <div className="mt-auto pt-5">
              {s ? (
                <p role="status" className={`rounded-full px-4 py-3 text-center text-sm font-bold ${s.cls}`}>
                  {s.text}
                </p>
              ) : (
                <button
                  type="button"
                  className="btn btn-primary w-full"
                  onClick={() => enroll(e.id)}
                  disabled={!canEnroll}
                  aria-describedby={canEnroll ? undefined : `wait-${e.id}`}
                >
                  {label}
                </button>
              )}
              {!s && !canEnroll && (
                <p id={`wait-${e.id}`} className="mt-2 text-center text-xs text-muted">
                  Ask your scout to enroll you in this one.
                </p>
              )}
              <a
                href={e.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 flex min-h-11 items-center justify-center text-sm font-semibold underline decoration-line-strong underline-offset-4 hover:decoration-ink"
              >
                View original post
              </a>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
