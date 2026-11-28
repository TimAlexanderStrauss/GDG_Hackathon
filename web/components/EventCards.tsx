"use client";

import { useEffect, useState } from "react";
import { siInstagram, siTiktok } from "simple-icons";
import { answerChoice, useChoice } from "@/lib/choice-store";
import { PLATFORMS, type AgentState, type Event, type Platform, type Source } from "@/lib/types";
import { mapsOpenUrl, mapsQuery } from "@/lib/maps";
import { BrandIcon } from "./BrandIcon";

type Status = NonNullable<AgentState["enrollments"]>[string];

const STATUS: Record<Status, { text: string; cls: string }> = {
  pending: { text: "Enrolling…", cls: "bg-warn-soft text-warn" },
  registered: { text: "✓ You're registered", cls: "bg-accent-soft text-ink" },
  manual: { text: "Sign-up steps in chat", cls: "bg-accent-soft text-ink" },
  failed: { text: "Enrollment failed", cls: "bg-bad-soft text-bad" },
  not_needed: { text: "✓ No sign-up needed – just go", cls: "bg-accent-soft text-ink" },
  purchased: { text: "✓ Ticket bought", cls: "bg-accent-soft text-ink" },
  needs_confirmation: { text: "Check the preview in the chat and confirm", cls: "bg-warn-soft text-warn" },
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

/** All posts/pages of an event; older state without `sources` counts as the single source_url. */
const sourcesOf = (e: Event): Source[] => (e.sources?.length ? e.sources : [{ platform: e.platform, url: e.source_url }]);

/** "TikTok post", "Web page"; a repeated platform gets a number from its second link on ("TikTok post 2"). */
function sourceLinkLabels(sources: Source[]): string[] {
  const seen: Record<string, number> = {};
  return sources.map((s) => {
    const n = (seen[s.platform] = (seen[s.platform] ?? 0) + 1);
    const base = s.platform === "web" ? "Web page" : `${PLATFORMS.find((p) => p.id === s.platform)?.label ?? s.platform} post`;
    return n > 1 ? `${base} ${n}` : base;
  });
}

type Props = {
  events: Event[];
  enrollments: AgentState["enrollments"];
  consent: boolean;
  /** Restrict the enroll buttons to one pending choose_event call. */
  toolCallId?: string;
  /** Marks an event as purchased in the shared agent state (only where an agent is available). */
  onPurchased?: (id: string) => void;
};

const LINK_CLS = "inline-flex min-h-11 items-center underline decoration-line-strong underline-offset-4 hover:decoration-ink";

const norm = (t: string | null) => (t ?? "").toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
const t = (e: Event) => (e.start ? new Date(e.start).getTime() || Infinity : Infinity);

/** Same title + venue = one card with several dates. A group sits where its best-ranked member sits. */
function groupEvents(events: Event[]): Event[][] {
  const map = new Map<string, Event[]>();
  for (const e of events) {
    const k = `${norm(e.title)}|${norm(e.venue)}`;
    map.set(k, [...(map.get(k) ?? []), e]);
  }
  return [...map.values()].map((g) => g.sort((x, y) => t(x) - t(y)));
}

/** Grid columns, mirroring the Tailwind breakpoints sm (640px) and 2xl (1536px). */
function useColumns() {
  const [cols, setCols] = useState(3);
  useEffect(() => {
    const qs = [window.matchMedia("(min-width: 640px)"), window.matchMedia("(min-width: 1536px)")];
    const upd = () => setCols(1 + qs.filter((q) => q.matches).length);
    upd();
    qs.forEach((q) => q.addEventListener("change", upd));
    return () => qs.forEach((q) => q.removeEventListener("change", upd));
  }, []);
  return cols;
}

const GRADIENTS = [
  "from-accent-soft to-surface-2",
  "from-surface-2 to-accent-soft",
  "from-surface-2 via-accent-soft to-surface-2",
  "from-accent-soft via-surface-2 to-accent-soft",
];

function Placeholder({ e }: { e: Event }) {
  let h = 0;
  for (const c of e.title) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return (
    <div
      aria-hidden
      className={`-mx-6 -mt-6 mb-5 flex aspect-video max-w-none flex-col items-center justify-center gap-2 bg-gradient-to-br ${GRADIENTS[h % GRADIENTS.length]}`}
      style={{ width: "calc(100% + 3rem)" }}
    >
      <SourceLabel platform={e.platform} />
      {e.venue && <p className="max-w-[80%] truncate text-sm font-semibold text-muted">{e.venue}</p>}
    </div>
  );
}

export function EventCards({ events, enrollments = {}, consent, toolCallId, onPurchased }: Props) {
  const [clicked, setClicked] = useState<Set<string>>(new Set());
  const [failed, setFailed] = useState<Set<string>>(new Set());
  const [rows, setRows] = useState(3);
  const ids = events.map((e) => e.id).join();
  const [seen, setSeen] = useState(ids);
  if (seen !== ids) {
    setSeen(ids); // new scan result (other ids): start over; state updates with the same events keep the rows
    setRows(3);
  }
  const cols = useColumns();
  const groups = groupEvents(events);
  const shown = cols * rows;
  const { pending, answered } = useChoice();
  const active = pending && (!toolCallId || pending.toolCallId === toolCallId) ? pending : null;
  const choosable = new Set(active?.events.map((e) => e.id));
  const chosenId = toolCallId ? answered[toolCallId]?.event_id : undefined;

  const enroll = (id: string) =>
    active && answerChoice(active.toolCallId, { event_id: id, approved_at: new Date().toISOString() });

  return (
    <>
      <ul className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
        {groups.slice(0, shown).map((g) => (
          <Card
            key={g[0].id}
            group={g}
            {...{ enrollments, consent, onPurchased, active, choosable, chosenId, enroll, clicked, setClicked, failed, setFailed }}
          />
        ))}
      </ul>
      {groups.length > shown && (
        <div className="mt-6 text-center">
          <button type="button" className="btn btn-secondary" onClick={() => setRows((r) => r + 3)}>
            Load more events ({groups.length - shown} more)
          </button>
        </div>
      )}
    </>
  );
}

type CardProps = Pick<Props, "consent" | "onPurchased"> & {
  group: Event[];
  enrollments: NonNullable<Props["enrollments"]>;
  active: unknown;
  choosable: Set<string>;
  chosenId?: string | null;
  enroll: (id: string) => unknown;
  clicked: Set<string>;
  setClicked: React.Dispatch<React.SetStateAction<Set<string>>>;
  failed: Set<string>;
  setFailed: React.Dispatch<React.SetStateAction<Set<string>>>;
};

function Card({ group, enrollments, consent, onPurchased, active, choosable, chosenId, enroll, clicked, setClicked, failed, setFailed }: CardProps) {
  const [sel, setSel] = useState<string | null>(null);
  const [now] = useState(() => Date.now());
  // default: earliest upcoming date, else the first
  const e = group.find((m) => m.id === sel) ?? group.find((m) => t(m) >= now) ?? group[0];
  {
    {
        const status = enrollments[e.id];
        const s = status ? STATUS[status] : null;
        const d = dateParts(e.start);
        const canEnroll = !!active && choosable.has(e.id);
        const buy = e.signup === "tickets" ? e.ticket : null;
        const openPost = e.signup === "unknown" || e.signup === "link_in_bio" || (e.signup === "tickets" && !buy);
        const postUrl = e.registration_url ?? e.source_url;
        const label =
          e.signup === "none"
            ? "Just go · add to calendar"
            : e.signup === "web_form"
              ? "Get sign-up link"
              : e.signup === "message"
                ? "Prepare message"
                : consent
                  ? "Enroll me"
                  : "Get sign-up steps";
        // Actions that need no pending choose_event call: ticket deep link, open post.
        const direct = buy || openPost;
        const btn = "btn btn-primary w-full";
        const directAction = buy ? (
          buy.availability === "sold_out" ? (
            <p className="rounded-full bg-surface-2 px-4 py-3 text-center text-sm font-bold text-muted">Sold out</p>
          ) : (
            <>
              <a
                href={buy.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`${btn} inline-flex items-center justify-center`}
                onClick={() => setClicked((c) => new Set(c).add(e.id))}
              >
                {buy.price ? `Buy ticket · ${buy.price}` : "Buy ticket"}
              </a>
              {onPurchased && clicked.has(e.id) && (
                <button type="button" className="btn btn-secondary btn-sm mt-2 w-full" onClick={() => onPurchased(e.id)}>
                  I bought it
                </button>
              )}
            </>
          )
        ) : (
          <>
            {/* hints sit above the button, so the buttons of a card row stay on one line */}
            <p className="mb-1 text-center text-xs text-muted">
              {e.bio_url ? "Sign-up page found via the bio link" : "No sign-up link found"}
            </p>
            <a href={postUrl} target="_blank" rel="noopener noreferrer" className={`${btn} inline-flex items-center justify-center`}>
              Open post
            </a>
            {e.bio_url && (
              <a
                href={e.bio_url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-secondary mt-2 inline-flex w-full items-center justify-center"
              >
                Open sign-up page
              </a>
            )}
          </>
        );
        const sources = sourcesOf(e);
        const linkLabels = sourceLinkLabels(sources);
        const meta = [d?.time, e.price].filter(Boolean).join(" · ");

        return (
          <li
            className={`panel relative flex flex-col overflow-hidden p-6 transition-transform duration-150 hover:-translate-y-0.5 ${
              chosenId === e.id ? "ring-2 ring-accent" : ""
            }`}
          >
            {e.image_url && !failed.has(e.id) ? (
              // whole image (object-contain) on a blurred, zoomed copy of itself: square posters are not cropped
              <div className="relative -mx-6 -mt-6 mb-5 aspect-video max-w-none overflow-hidden bg-surface-2" style={{ width: "calc(100% + 3rem)" }}>
                {/* eslint-disable-next-line @next/next/no-img-element -- external CDN, not optimizable */}
                <img src={e.image_url} alt="" aria-hidden loading="lazy" referrerPolicy="no-referrer"
                  className="absolute inset-0 h-full w-full scale-110 object-cover opacity-60 blur-xl" />
                {/* eslint-disable-next-line @next/next/no-img-element -- external CDN, not optimizable */}
                <img
                  src={e.image_url}
                  alt={e.title}
                  loading="lazy"
                  referrerPolicy="no-referrer"
                  className="relative h-full w-full object-contain"
                  onError={() => setFailed((f) => new Set(f).add(e.id))}
                />
              </div>
            ) : (
              <Placeholder e={e} />
            )}
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
              <div className="flex flex-wrap items-center gap-x-1.5">
                {[...new Set(sources.map((s) => s.platform))].map((p, i) => (
                  <span key={p} className="inline-flex items-center gap-1.5">
                    {i > 0 && <span aria-hidden className="text-muted">·</span>}
                    <SourceLabel platform={p} />
                  </span>
                ))}
              </div>
            </div>

            <h3 className="mt-5 text-2xl leading-[1.1]">{e.title}</h3>

            {group.length > 1 && (
              <div className="mt-3">
                <p className="text-xs text-muted">{group.length} dates – pick one</p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {group.map((m) => {
                    const p = dateParts(m.start);
                    return (
                      <button
                        key={m.id}
                        type="button"
                        aria-pressed={m.id === e.id}
                        onClick={() => setSel(m.id)}
                        className={`min-h-9 rounded-full border px-3 text-xs font-bold ${
                          m.id === e.id ? "border-ink bg-ink text-surface" : "border-line-strong text-muted hover:text-ink"
                        }`}
                      >
                        {p ? `${p.weekday} ${p.day}` : "Date TBA"}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

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
              {e.signup_hint && <p className="pl-[26px] text-xs text-muted">{e.signup_hint}</p>}
            </div>

            {e.summary && <p className="mt-3 line-clamp-3 text-sm text-muted">{e.summary}</p>}

            {e.match_reason && (
              <p className="mt-3 text-sm text-muted">
                {e.match_reason}
                <span className="ml-1 font-semibold text-ink">
                  · {Math.round(Math.max(0, Math.min(1, e.match_score)) * 100)}% match
                </span>
              </p>
            )}

            <div className="mt-auto pt-5">
              {!s && !direct && !canEnroll && (
                <p id={`wait-${e.id}`} className="mb-2 text-center text-xs text-muted">
                  Ask your scout to enroll you in this one.
                </p>
              )}
              {s ? (
                <p role="status" className={`rounded-full px-4 py-3 text-center text-sm font-bold ${s.cls}`}>
                  {s.text}
                </p>
              ) : direct ? (
                directAction
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
              <div className="mt-2 flex flex-wrap items-center justify-center gap-x-5 text-sm font-semibold">
                {sources.length > 1
                  ? sources.map((s, i) =>
                      openPost && postUrl === s.url ? null : (
                        <a key={s.url} href={s.url} target="_blank" rel="noopener noreferrer" className={LINK_CLS}>
                          {linkLabels[i]}
                        </a>
                      ),
                    )
                  : !(openPost && postUrl === e.source_url) && (
                      <a href={e.source_url} target="_blank" rel="noopener noreferrer" className={LINK_CLS}>
                        View original post
                      </a>
                    )}
                {mapsQuery(e) && (
                  <a
                    href={mapsOpenUrl(mapsQuery(e)!)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex min-h-11 items-center underline decoration-line-strong underline-offset-4 hover:decoration-ink"
                  >
                    Google Maps
                  </a>
                )}
              </div>
            </div>
          </li>
        );
    }
  }
}
