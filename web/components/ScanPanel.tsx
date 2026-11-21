"use client";

import { PLATFORMS, type AgentState } from "@/lib/types";

const label = (p: string) => PLATFORMS.find((x) => x.id === p)?.label ?? p;

const STATUS: Record<string, { text: string; cls: string }> = {
  running: { text: "Scanning", cls: "bg-warn-soft text-warn" },
  done: { text: "Done", cls: "bg-ok-soft text-ok" },
  error: { text: "Error", cls: "bg-bad-soft text-bad" },
};

const time = (ts: string) => {
  const d = new Date(ts);
  return Number.isNaN(d.getTime())
    ? ts
    : d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

/** Shows only what the agent reported in state.progress and state.audit. */
export function ScanPanel({ state, isRunning }: { state: AgentState; isRunning: boolean }) {
  const progress = state.progress ?? [];
  const audit = state.audit ?? [];
  const blocked = progress.reduce((n, p) => n + (p.blocked || 0), 0);

  return (
    <>
      <section className="panel p-5" aria-labelledby="scan-title">
        <div className="flex items-baseline justify-between gap-3">
          <h2 id="scan-title" className="font-medium tracking-tight">
            Scan progress
          </h2>
          {blocked > 0 && (
            <span className="rounded-full bg-warn-soft px-2.5 py-1 text-xs font-semibold text-warn">
              {blocked} blocked
            </span>
          )}
        </div>

        {progress.length === 0 ? (
          <p className="mt-3 text-sm text-muted" aria-live="polite">
            {isRunning ? "Waiting for the first scout report." : "No scan yet."}
          </p>
        ) : (
          <ul className="mt-3 divide-y divide-line" aria-live="polite">
            {progress.map((p) => {
              const s = STATUS[p.status] ?? STATUS.running;
              return (
                <li key={p.platform} className="flex items-center justify-between gap-3 py-2.5">
                  <div>
                    <p className="text-sm font-medium">{label(p.platform)}</p>
                    <p className="text-xs text-muted tabular-nums">
                      {p.posts} {p.posts === 1 ? "post" : "posts"} read
                      {p.blocked > 0 && (
                        <span className="text-warn">
                          {" "}
                          · {p.blocked} blocked as possible prompt injection
                        </span>
                      )}
                    </p>
                  </div>
                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${s.cls}`}>{s.text}</span>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="panel flex min-h-0 flex-col p-5" aria-labelledby="audit-title">
        <h2 id="audit-title" className="font-medium tracking-tight">
          Audit log
        </h2>
        <p className="mt-0.5 text-xs text-muted">Every tool call the agents report.</p>
        {audit.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No tool calls yet.</p>
        ) : (
          <ol className="mt-3 max-h-72 space-y-2 overflow-auto pr-1 font-mono text-xs">
            {[...audit].reverse().map((a, i) => (
              <li key={`${a.ts}-${i}`} className="rounded-[var(--es-radius-s)] bg-surface-2 px-3 py-2">
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
    </>
  );
}
