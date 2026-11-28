"use client";

import { useHumanInTheLoop } from "@copilotkit/react-core/v2";
import { useEffect } from "react";
import { z } from "zod";
import { answerChoice, offerChoice, useChoice, withdrawChoice } from "@/lib/choice-store";
import { AGENT_ID } from "@/lib/config";
import type { AgentState, ChooseEventResponse, Event } from "@/lib/types";

// Loose schema: the agent's Event objects are validated by P2/P3 against shared/schemas.py.
const params = z.object({
  events: z.array(z.record(z.string(), z.unknown())).describe("Ranked Event objects (shared/schemas.py Event)"),
});

/**
 * Registers the `choose_event` frontend tool once. The concierge calls it with the
 * ranked events; it resolves only when the user clicks Enroll me (or Skip) on a card,
 * with { event_id, approved_at } as the approval record.
 */
export function ChooseEventTool({ state, consent }: { state: AgentState; consent: boolean }) {
  useHumanInTheLoop(
    {
      name: "choose_event",
      agentId: AGENT_ID,
      description:
        "Show the ranked events to the user as cards and wait for them to pick one. " +
        "Returns {event_id, approved_at} after the user's click, or {event_id: null, declined: true}.",
      parameters: params,
      render: (props) => {
        const events = (props.args.events ?? []) as unknown as Event[];
        return (
          <ChoiceInChat
            toolCallId={props.toolCallId}
            events={events}
            respond={props.respond}
            done={props.status === "complete"}
          />
        );
      },
    },
    [state, consent],
  );
  return null;
}

function ChoiceInChat({
  toolCallId,
  events,
  respond,
  done,
}: {
  toolCallId: string;
  events: Event[];
  respond?: (r: unknown) => Promise<void>;
  done: boolean;
}) {
  const { answered } = useChoice();
  const answer = answered[toolCallId];

  useEffect(() => {
    if (respond && events.length) offerChoice({ toolCallId, events, respond: (r: ChooseEventResponse) => respond(r) });
    return () => withdrawChoice(toolCallId);
  }, [toolCallId, respond, events]);

  if (!events.length) return <p className="text-sm text-muted">Preparing event cards…</p>;

  const picked = answer?.event_id ? events.find((e) => e.id === answer.event_id) : null;

  return (
    <div className="my-2 space-y-2">
      {done || answer ? (
        <p className="text-sm text-muted">
          {picked ? (
            <>
              You chose <strong className="text-ink">{picked.title}</strong>.
            </>
          ) : answer ? (
            "You skipped these events."
          ) : (
            "Choice recorded."
          )}
        </p>
      ) : (
        <>
          <p className="text-sm text-muted">
            Found {events.length} event{events.length === 1 ? "" : "s"} – pick one in the Events panel.
          </p>
          <button
            type="button"
            className="btn btn-secondary w-full"
            onClick={() => answerChoice(toolCallId, { event_id: null, approved_at: null, declined: true })}
          >
            None of these
          </button>
        </>
      )}
    </div>
  );
}
