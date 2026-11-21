"use client";

import { CopilotChat, useAgent, useCopilotKit } from "@copilotkit/react-core/v2";
import { useCallback, useEffect, useRef, useState } from "react";
import { useChoice } from "@/lib/choice-store";
import { AGENT_ID } from "@/lib/config";
import { PLATFORMS, type AgentState, type UserProfile } from "@/lib/types";
import { ChooseEventTool } from "./ChooseEventTool";
import { EventCards } from "./EventCards";
import { ScanPanel } from "./ScanPanel";

type Props = {
  profile: UserProfile;
  /** Increments each time the user saves the form, to start a fresh scan. */
  scanRequest: number;
  onEdit: () => void;
};

export function Dashboard({ profile, scanRequest, onEdit }: Props) {
  const { agent, isReady } = useAgent({ agentId: AGENT_ID });
  const { copilotkit } = useCopilotKit();
  const { pending } = useChoice();
  const [error, setError] = useState<string | null>(null);
  const [hasRun, setHasRun] = useState(false);
  const handled = useRef(0);

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
        "My full profile is in the shared state under `profile`.",
    });
    setHasRun(true);
    try {
      await copilotkit.runAgent({ agent });
    } catch (e) {
      setError(e instanceof Error ? e.message : "The concierge did not respond.");
    }
  }, [agent, copilotkit, profile]);

  // Start a scan once per form save, as soon as the agent is connected.
  useEffect(() => {
    if (isReady && !isRunning && scanRequest > handled.current) {
      handled.current = scanRequest;
      void scan();
    }
  }, [isReady, isRunning, scanRequest, scan]);

  const events = state.events?.length ? state.events : (pending?.events ?? []);

  return (
    <div className="mx-auto grid w-full max-w-[1500px] gap-5 px-4 py-6 sm:px-6 lg:grid-cols-[300px_minmax(0,1fr)] xl:grid-cols-[300px_minmax(0,1fr)_400px]">
      <ChooseEventTool state={state} consent={profile.consent_enrollment} />

      <aside className="order-3 flex flex-col gap-5 lg:order-1 lg:row-span-2 xl:row-span-1">
        <ProfileSummary profile={profile} onEdit={onEdit} />
        <ScanPanel state={state} isRunning={isRunning} />
      </aside>

      <main className="order-1 min-w-0 lg:order-2" aria-labelledby="events-title">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 id="events-title" className="text-2xl font-medium tracking-tight">
              Events in {profile.city}{events.length > 0 && <span className="text-muted"> · {events.length}</span>}
            </h1>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => void scan()}
            disabled={!isReady || isRunning}
          >
            {isRunning ? "Scanning…" : hasRun ? "Scan again" : "Find events"}
          </button>
        </div>

        {error && (
          <div role="alert" className="mb-4 rounded-[var(--es-radius-m)] border border-bad bg-bad-soft p-4 text-sm">
            <p className="font-semibold text-bad">The scan could not run.</p>
            <p className="mt-1 text-ink">{error}</p>
            <p className="mt-1 text-muted">Check that the concierge is running (see web/README.md), then scan again.</p>
          </div>
        )}

        {events.length > 0 ? (
          <>
            {pending && (
              <p className="mb-3 text-sm text-muted" role="status">
                The concierge is waiting for your pick. Nothing is booked until you click.
              </p>
            )}
            <EventCards events={events} enrollments={state.enrollments} consent={profile.consent_enrollment} />
          </>
        ) : isRunning ? (
          <div aria-live="polite">
            <p className="text-sm text-muted">Scouts are reading posts. Cards appear here when the curator is done.</p>
            <div className="mt-4 grid gap-4 md:grid-cols-2" aria-hidden>
              {[0, 1].map((i) => (
                <div key={i} className="panel h-44 animate-pulse bg-surface-2" />
              ))}
            </div>
          </div>
        ) : !isReady ? (
          <Empty title="Connecting to the concierge…" body="The agent runtime is starting." />
        ) : hasRun && !error ? (
          <Empty
            title="No matching events found"
            body={`Nothing in ${profile.city} for the next ${profile.days_ahead} days matched. Try more interests or a longer range.`}
          />
        ) : !error ? (
          <Empty title="Ready to scan" body="Find events reads public posts for your city and ranks them for you." />
        ) : null}
      </main>

      <section
        className="panel order-2 h-[70vh] min-h-[480px] overflow-hidden lg:order-3 lg:col-start-2 xl:sticky xl:top-20 xl:col-start-3 xl:row-start-1 xl:h-[calc(100vh-6.5rem)]"
        aria-label="Chat with the concierge"
      >
        <div className="scout-chat">
          <CopilotChat
            agentId={AGENT_ID}
            labels={{
              chatInputPlaceholder: "Ask about events, e.g. “anything free this weekend?”",
            }}
          />
        </div>
      </section>
    </div>
  );
}

function ProfileSummary({ profile, onEdit }: { profile: UserProfile; onEdit: () => void }) {
  return (
    <section className="panel p-5" aria-labelledby="prof-title">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="prof-title" className="font-medium tracking-tight">
            {profile.display_name}
          </h2>
        </div>
        <button type="button" className="btn btn-secondary min-h-9 px-3 text-sm" onClick={onEdit}>
          Edit
        </button>
      </div>
      <p className="mt-2 text-sm text-muted">
        {profile.city} · next {profile.days_ahead} days
      </p>
      <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="Interests">
        {profile.interests.map((i) => (
          <li key={i} className="rounded-full bg-surface-2 px-2.5 py-1 text-xs font-medium">
            {i}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-muted">
        Sources: {profile.platforms.map((p) => PLATFORMS.find((x) => x.id === p)?.label ?? p).join(", ")}
      </p>
      <p className="mt-1 text-xs text-muted">
        {profile.consent_enrollment
          ? "May enroll you after your click."
          : "Enrollment off: you get sign-up steps instead."}
      </p>
    </section>
  );
}

function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="panel flex min-h-56 flex-col items-center justify-center p-8 text-center">
      <p className="font-semibold">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-muted">{body}</p>
    </div>
  );
}
