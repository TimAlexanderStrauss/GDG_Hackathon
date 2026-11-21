"use client";

import { PLATFORMS, type AgentState } from "@/lib/types";

const label = (p: string) => PLATFORMS.find((x) => x.id === p)?.label ?? p;

const STATUS: Record<string, { text: string; cls: string }> = {
  running: { text: "Scanning", cls: "bg-warn-soft text-warn" },
  done: { text: "✓ Done", cls: "bg-ok-soft text-ok" },
  error: { text: "Error", cls: "bg-bad-soft text-bad" },
};

const time = (ts: string) => {
  const d = new Date(ts);
  return Number.isNaN(d.getTime())
    ? ts
    : d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

function totals(state: AgentState) {
  const progress = state.progress ?? [];
  return {
    progress,
    posts: progress.reduce((n, p) => n + (p.posts || 0), 0),
    blocked: progress.reduce((n, p) => n + (p.blocked || 0), 0),
    running: progress.filter((p) => p.status === "running").length,
    errors: progress.filter((p) => p.status === "error").length,
  };
}

/** One concise line near the results. Every number comes from state.progress. */
export function ScanStatusLine({ state, isRunning }: { state: AgentState; isRunning: boolean }) {
  const t = totals(state);
  if (t.progress.length === 0) {
    return (
      <p className="text-sm text-muted" aria-live="polite">
        {isRunning ? "Your scouts are starting…" : "No scan yet."}
      </p>
    );
  }
  return (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted" aria-live="polite">
      {t.progress.map((p) => (
        <span key={p.platform} className="inline-flex items-center gap-1.5">
          <span
            aria-hidden
            className={`h-2 w-2 rounded-full ${
              p.status === "done" ? "bg-ok" : p.status === "error" ? "bg-bad" : "bg-warn motion-safe:animate-pulse"
            }`}
          />
          {label(p.platform)} {p.status === "running" ? "scanning" : p.status}
        </span>
      ))}
      <span>
        · {t.posts} {t.posts === 1 ? "post" : "posts"} read
      </span>
      {t.blocked > 0 && <span className="font-semibold text-warn">· {t.blocked} blocked</span>}
    </p>
  );
}

/** Expandable details: per-platform progress and the full audit log. */
export function ActivityPanel({ state }: { state: AgentState }) {
  const t = totals(state);
  const audit = state.audit ?? [];
  return (
    <details className="panel group mt-6">
      <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 px-5 py-3 [&::-webkit-details-marker]:hidden">
        <span className="font-bold">
          Activity
          <span className="ml-2 font-medium text-muted">
            {audit.length} tool {audit.length === 1 ? "call" : "calls"}
            {t.blocked > 0 && ` · ${t.blocked} blocked`}
          </span>
        </span>
        <svg
          aria-hidden
          viewBox="0 0 24 24"
          width={20}
          height={20}
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          className="transition-transform group-open:rotate-180"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </summary>

      <div className="grid gap-6 border-t border-line px-5 py-5 lg:grid-cols-[280px_minmax(0,1fr)]">
        <section aria-labelledby="act-scan">
          <h3 id="act-scan" className="text-base">
            Scan progress
          </h3>
          {t.progress.length === 0 ? (
            <p className="mt-2 text-sm text-muted">No scout has reported yet.</p>
          ) : (
            <ul className="mt-2 divide-y divide-line">
              {t.progress.map((p) => {
                const s = STATUS[p.status] ?? STATUS.running;
                return (
                  <li key={p.platform} className="flex items-center justify-between gap-3 py-2.5">
                    <div>
                      <p className="text-sm font-bold">{label(p.platform)}</p>
                      <p className="text-xs text-muted tabular-nums">
                        {p.posts} {p.posts === 1 ? "post" : "posts"} read
                        {p.blocked > 0 && (
                          <span className="text-warn"> · {p.blocked} blocked as possible prompt injection</span>
                        )}
                      </p>
                    </div>
                    <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${s.cls}`}>{s.text}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section aria-labelledby="act-audit" className="min-w-0">
          <h3 id="act-audit" className="text-base">
            Audit log
          </h3>
          {audit.length === 0 ? (
            <p className="mt-2 text-sm text-muted">No tool calls yet.</p>
          ) : (
            <ol className="mt-2 max-h-72 space-y-2 overflow-auto pr-1 font-mono text-xs">
              {[...audit].reverse().map((a, i) => (
                <li key={`${a.ts}-${i}`} className="rounded-[10px] bg-surface-2 px-3 py-2">
                  <div className="flex flex-wrap gap-x-2 text-muted">
                    <time dateTime={a.ts}>{time(a.ts)}</time>
                    <span>{a.agent}</span>
                    <span className="text-ink">{a.tool}</span>
                  </div>
                  {a.note && <p className="mt-1 break-words text-ink">{a.note}</p>}
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </details>
  );
}
