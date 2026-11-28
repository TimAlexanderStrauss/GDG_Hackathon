"use client";

import { useEffect, useRef, useState } from "react";

type Progress = { active: boolean; pct: number; stage: string; text: string };

const STEPS = [
  { label: "Live posts", stages: ["search", "fetch"] },
  { label: "Safety check", stages: ["guard"] },
  { label: "Reading posts", stages: ["extract"] },
  { label: "Ranking", stages: ["rank"] },
  { label: "Sign-up links", stages: ["resolve"] },
];

/** Progress bar bound to the concierge's real scan progress (polled through /api/progress). */
export function ScanProgress({ isRunning }: { isRunning: boolean }) {
  const [server, setServer] = useState<Progress | null>(null);
  const [shown, setShown] = useState(0);
  const [visible, setVisible] = useState(false);
  const serverPct = useRef(0);

  // Poll once per second while running; the next request starts only after the last one ended.
  useEffect(() => {
    if (!isRunning) return;
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    serverPct.current = 0;
    /* eslint-disable react-hooks/set-state-in-effect -- reset when a new scan starts */
    setShown(0);
    setServer(null);
    setVisible(false); // shown on the first active report: chat runs without a scan get no bar
    /* eslint-enable react-hooks/set-state-in-effect */
    const poll = async () => {
      try {
        const p: Progress = await (await fetch("/api/progress", { cache: "no-store" })).json();
        if (!stop && p.active) {
          serverPct.current = Math.max(serverPct.current, p.pct);
          setServer(p);
          setVisible(true);
        }
      } catch {}
      if (!stop) timer = setTimeout(poll, 1000);
    };
    void poll();
    // Creep forward between updates: never past server pct + 8 or 99, never backwards.
    const creep = setInterval(
      () => setShown((s) => Math.max(s, Math.min(Math.max(s, serverPct.current), s + 0.3, serverPct.current + 8, 99))),
      1000,
    );
    // Follow the server value (the CSS transition smooths the jump).
    const follow = setInterval(() => setShown((s) => Math.max(s, Math.min(serverPct.current, 99))), 250);
    return () => {
      stop = true;
      clearTimeout(timer);
      clearInterval(creep);
      clearInterval(follow);
    };
  }, [isRunning]);

  // Run ended: fill to 100 %, then hide.
  useEffect(() => {
    if (isRunning || !visible) return;
    const t = setTimeout(() => setVisible(false), 1200);
    return () => clearTimeout(t);
  }, [isRunning, visible]);

  if (!visible) return null;
  const done = !isRunning;
  const pct = done ? 100 : Math.round(shown);
  const cur = STEPS.findIndex((s) => s.stages.includes(server?.stage ?? ""));
  const text = done ? "Done" : server?.text || "Your scouts are starting…";

  return (
    <div className="panel mt-6 w-full p-4 sm:p-5">
      <div className="flex items-center gap-3">
        <span aria-hidden className="relative flex h-3 w-3 shrink-0">
          <span className="es-radar-ring absolute inset-0 rounded-full bg-accent" />
          <span className="relative h-3 w-3 rounded-full bg-accent" />
        </span>
        <p key={text} className="es-fade min-w-0 flex-1 truncate text-sm font-semibold" aria-live="polite">
          {text}
        </p>
        <span className="text-sm font-bold tabular-nums text-muted">{pct}%</span>
      </div>
      <div
        role="progressbar"
        aria-label="Scan progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-surface-2"
      >
        <div className="es-bar-fill h-full rounded-full bg-accent transition-[width] duration-1000 ease-out" style={{ width: `${pct}%` }} />
      </div>
      <ol className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {STEPS.map((s, i) => {
          const ok = done || (cur >= 0 && i < cur) || server?.stage === "done";
          const now = !ok && i === cur;
          return (
            <li key={s.label} className={now ? "font-bold text-ink" : ok ? "text-ink" : "text-muted"} aria-current={now ? "step" : undefined}>
              <span aria-hidden>{ok ? "✓" : now ? "●" : "○"}</span> {s.label}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
