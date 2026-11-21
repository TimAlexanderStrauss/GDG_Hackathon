"use client";

import { CopilotChat, useAgent, useCopilotKit } from "@copilotkit/react-core/v2";
import { useCallback, useEffect, useRef, useState } from "react";
import { useChoice } from "@/lib/choice-store";
import { AGENT_ID } from "@/lib/config";
import type { AgentState, UserProfile } from "@/lib/types";
import { ActivityPanel, ScanStatusLine } from "./Activity";
import { ChooseEventTool } from "./ChooseEventTool";
import { EventCards } from "./EventCards";

type Props = {
  profile: UserProfile;
  /** Socials added in the demo Connect step; sent as a hint, no account data yet. */
  socials: string[];
  /** Increments each time the user saves the form, to start a fresh scan. */
  scanRequest: number;
  onEdit: () => void;
};

export function Dashboard({ profile, socials, scanRequest, onEdit }: Props) {
  const { agent, isReady } = useAgent({ agentId: AGENT_ID });
  const { copilotkit } = useCopilotKit();
  const { pending } = useChoice();
  const [error, setError] = useState<string | null>(null);
  const [hasRun, setHasRun] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const handled = useRef(0);
  const closeRef = useRef<HTMLButtonElement>(null);

  const state = (agent.state ?? {}) as AgentState;
  const isRunning = agent.isRunning;

  // Keep profile in shared state, preserving everything else the agent wrote.
  useEffect(() => {
    if (!isReady) return;
    const current = (agent.state ?? {}) as AgentState;
    if (JSON.stringify(current.profile) !== JSON.stringify(profile)) agent.setState({ ...current, profile });
  }, [agent, isReady, profile]);

  const scan = useCallback(async () => {
    setError(null);
    const current = (agent.state ?? {}) as AgentState;
    // Profile goes into state before the run starts, so the run input carries it.
    agent.setState({ ...current, profile, progress: [], events: [] });
    agent.addMessage({
      id: crypto.randomUUID(),
      role: "user",
      content:
        `Find events for me in ${profile.city} in the next ${profile.days_ahead} days. ` +
        `Interests: ${profile.interests.join(", ")}. Sources: ${profile.platforms.join(", ")}. ` +
        "My full profile is in the shared state under `profile`." +
        (socials.length ? ` I use ${socials.join(", ")}; prefer events from those communities.` : ""),
    });
    setHasRun(true);
    try {
      await copilotkit.runAgent({ agent });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Your scout did not respond.");
    }
  }, [agent, copilotkit, profile, socials]);

  // Start a scan once per form save, as soon as the agent is connected.
  useEffect(() => {
    if (isReady && !isRunning && scanRequest > handled.current) {
      handled.current = scanRequest;
      void scan();
    }
  }, [isReady, isRunning, scanRequest, scan]);

  // Drawer: Escape closes it, focus moves into it when it opens.
  useEffect(() => {
    if (!chatOpen) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setChatOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [chatOpen]);

  const events = state.events?.length ? state.events : (pending?.events ?? []);

  return (
    <div className="flex-1 bg-surface-2">
      <ChooseEventTool state={state} consent={profile.consent_enrollment} />

      <div className="mx-auto max-w-[1600px] xl:grid xl:grid-cols-[minmax(0,1fr)_400px]">
        <main className="min-w-0 px-4 py-8 pb-28 sm:px-8 xl:pb-10" aria-labelledby="disc-title">
          <h1 id="disc-title" className="text-4xl leading-[1.05] sm:text-5xl">
            Your next plan is out there.
          </h1>
          <p className="mt-2 text-lg text-muted">Events in {profile.city} that match your interests.</p>

          <ul className="mt-5 flex flex-wrap gap-2" aria-label="Your interests">
            {profile.interests.map((i) => (
              <li key={i} className="rounded-full bg-accent-soft px-4 py-2 text-sm font-bold">
                {i}
              </li>
            ))}
          </ul>

          <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
            <ScanStatusLine state={state} isRunning={isRunning} />
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => void scan()}
              disabled={!isReady || isRunning}
            >
              {isRunning ? "Scanning…" : hasRun ? "Scan again" : "Find my events"}
            </button>
          </div>

          {error && (
            <div role="alert" className="mt-4 rounded-[16px] border border-bad bg-bad-soft p-4 text-sm">
              <p className="font-bold text-bad">The scan could not run.</p>
              <p className="mt-1">{error}</p>
              <p className="mt-1 text-muted">Check that the concierge is running (web/README.md), then scan again.</p>
            </div>
          )}

          <div className="mt-5">
            {events.length > 0 ? (
              <>
                {pending && (
                  <p className="mb-3 text-sm font-semibold" role="status">
                    Your scout is waiting for your pick. Nothing is booked until you click.
                  </p>
                )}
                <EventCards events={events} enrollments={state.enrollments} consent={profile.consent_enrollment} />
              </>
            ) : isRunning ? (
              <div aria-live="polite">
                <p className="text-sm text-muted">Reading posts. Cards appear here when the curator is done.</p>
                <div className="mt-4 grid gap-4 sm:grid-cols-2 2xl:grid-cols-3" aria-hidden>
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="panel h-72 motion-safe:animate-pulse" />
                  ))}
                </div>
              </div>
            ) : !isReady ? (
              <Empty title="Connecting to your scout…" body="The agent runtime is starting." />
            ) : hasRun && !error ? (
              <Empty
                title="No matching events yet"
                body={`Nothing in ${profile.city} for the next ${profile.days_ahead} days matched. Try more interests or a longer range.`}
              />
            ) : !error ? (
              <Empty title="Ready when you are" body="Find my events reads public posts for your city and ranks them for you." />
            ) : null}
          </div>

          <p className="mt-5 flex flex-wrap items-center gap-x-2 text-sm text-muted">
            {events.length > 0 && (
              <span>
                Showing {events.length} matching {events.length === 1 ? "event" : "events"} in {profile.city} · Next{" "}
                {profile.days_ahead} days ·
              </span>
            )}
            <button
              type="button"
              onClick={onEdit}
              className="min-h-11 font-semibold text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink"
            >
              Update interests
            </button>
          </p>

          <ActivityPanel state={state} />
        </main>

        {/* Scout chat: beside results on desktop, bottom drawer on smaller screens */}
        {chatOpen && (
          <div className="fixed inset-0 z-30 bg-ink/30 xl:hidden" aria-hidden onClick={() => setChatOpen(false)} />
        )}
        <aside
          id="scout-drawer"
          aria-label="Your scout"
          className={`fixed inset-x-0 bottom-0 z-40 flex h-[85vh] flex-col rounded-t-[20px] border-t border-line bg-surface shadow-2xl transition-transform duration-200 xl:visible xl:sticky xl:top-[65px] xl:z-auto xl:h-[calc(100vh-65px)] xl:translate-y-0 xl:rounded-none xl:border-t-0 xl:border-l xl:shadow-none ${
            chatOpen ? "visible translate-y-0" : "invisible translate-y-full"
          }`}
        >
          <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
            <h2 className="flex min-h-11 items-center gap-2 text-xl">
              <svg aria-hidden viewBox="0 0 24 24" width={22} height={22} fill="none" stroke="var(--es-accent)" strokeWidth={2}>
                <path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4z" />
              </svg>
              Your scout
            </h2>
            <button
              ref={closeRef}
              type="button"
              className="btn btn-secondary btn-sm xl:hidden"
              onClick={() => setChatOpen(false)}
            >
              Close
            </button>
          </div>
          <div className="scout-chat min-h-0 flex-1">
            <CopilotChat agentId={AGENT_ID} labels={{ chatInputPlaceholder: "Ask your scout…" }} />
          </div>
        </aside>
      </div>

      <button
        type="button"
        className="btn btn-primary fixed right-4 bottom-4 z-20 shadow-lg xl:hidden"
        onClick={() => setChatOpen(true)}
        aria-controls="scout-drawer"
        aria-expanded={chatOpen}
      >
        Ask your scout{pending ? " · 1 pick waiting" : ""}
      </button>
    </div>
  );
}

function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="panel flex min-h-64 flex-col items-center justify-center p-8 text-center">
      <p className="text-lg font-bold">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-muted">{body}</p>
    </div>
  );
}
