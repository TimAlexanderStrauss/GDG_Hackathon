"use client";

import { answerChoice, useChoice } from "@/lib/choice-store";
import { PLATFORMS, type AgentState, type Event } from "@/lib/types";

type Status = NonNullable<AgentState["enrollments"]>[string];

const STATUS: Record<Status, { text: string; cls: string }> = {
  pending: { text: "Enrolling", cls: "bg-warn-soft text-warn" },
  registered: { text: "Registered", cls: "bg-ok-soft text-ok" },
  manual: { text: "Sign up yourself", cls: "bg-accent-soft text-accent" },
  failed: { text: "Enrollment failed", cls: "bg-bad-soft text-bad" },
};

const when = (iso: string | null) => {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Berlin",
  });
};

type Props = {
  events: Event[];
  enrollments: AgentState["enrollments"];
  consent: boolean;
  /** Compact = inside the chat bubble. */
  compact?: boolean;
  /** Restrict the enroll buttons to one pending choose_event call. */
  toolCallId?: string;
};

export function EventCards({ events, enrollments = {}, consent, compact, toolCallId }: Props) {
  const { pending, answered } = useChoice();
  const active = pending && (!toolCallId || pending.toolCallId === toolCallId) ? pending : null;
  const choosable = new Set(active?.events.map((e) => e.id));

  const enroll = (id: string) =>
    active && answerChoice(active.toolCallId, { event_id: id, approved_at: new Date().toISOString() });

  const chosenId = toolCallId ? answered[toolCallId]?.event_id : undefined;

  return (
    <ul className={compact ? "space-y-2" : "grid gap-4 md:grid-cols-2"}>
      {events.map((e) => {
        const status = enrollments[e.id];
        const s = status ? STATUS[status] : null;
        const date = when(e.start);
        const place = [e.venue, e.city].filter(Boolean).join(", ");
        const canEnroll = !!active && choosable.has(e.id);
        return (
          <li
            key={e.id}
            className={`panel flex flex-col ${compact ? "p-3" : "p-5"} ${
              chosenId === e.id ? "ring-2 ring-accent" : ""
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className={`font-medium tracking-tight ${compact ? "text-sm" : "text-lg"}`}>{e.title}</h3>
              </div>
              <span
                className="shrink-0 rounded-full bg-surface-2 px-2.5 py-1 text-xs font-semibold tabular-nums"
                title="Match with your preferences"
              >
                {Math.round(Math.max(0, Math.min(1, e.match_score)) * 100)}% match
              </span>
            </div>

            <dl className="mt-2 space-y-0.5 text-sm text-muted">
              <div>
                <dt className="sr-only">Found on</dt>
                <dd>{PLATFORMS.find((p) => p.id === e.platform)?.label ?? e.platform} post</dd>
              </div>
              {date && (
                <div>
                  <dt className="sr-only">When</dt>
                  <dd>{date}</dd>
                </div>
              )}
              {place && (
                <div>
                  <dt className="sr-only">Where</dt>
                  <dd>{place}</dd>
                </div>
              )}
              {e.price && (
                <div>
                  <dt className="sr-only">Price</dt>
                  <dd>{e.price}</dd>
                </div>
              )}
            </dl>

            {e.match_reason && !compact && <p className="mt-3 text-sm">{e.match_reason}</p>}

            <div className="mt-auto flex flex-wrap items-center gap-2 pt-4">
              {s ? (
                <span role="status" className={`rounded-full px-3 py-1.5 text-sm font-semibold ${s.cls}`}>
                  {s.text}
                </span>
              ) : canEnroll ? (
                <button type="button" className="btn btn-primary" onClick={() => enroll(e.id)}>
                  {consent && e.enrollment_mode === "auto" ? "Enroll me" : "Get sign-up steps"}
                </button>
              ) : null}
              <a
                href={e.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex min-h-11 items-center px-1 text-sm font-medium underline decoration-line-strong underline-offset-4 hover:decoration-ink"
              >
                Open post
              </a>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
