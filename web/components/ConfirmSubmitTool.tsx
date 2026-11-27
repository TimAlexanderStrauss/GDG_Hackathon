"use client";

import { useHumanInTheLoop } from "@copilotkit/react-core/v2";
import { useState } from "react";
import { z } from "zod";
import { AGENT_ID } from "@/lib/config";

const params = z.object({
  event_id: z.string(),
  title: z.string(),
  preview: z.string().describe("Planned form values as text"),
  link: z.string(),
});

/**
 * Registers the `confirm_submit` frontend tool. The concierge calls it with the sign-up
 * preview; it resolves only on the user's click: {event_id, confirmed_at} or {event_id, declined: true}.
 */
export function ConfirmSubmitTool() {
  useHumanInTheLoop({
    name: "confirm_submit",
    agentId: AGENT_ID,
    description:
      "Show the planned sign-up form values to the user and wait for confirmation. " +
      "Returns {event_id, confirmed_at} on Submit, or {event_id, declined: true} on Cancel.",
    parameters: params,
    render: (props) => (
      <ConfirmInChat
        eventId={props.args.event_id ?? ""}
        title={props.args.title ?? ""}
        preview={props.args.preview ?? ""}
        link={props.args.link ?? ""}
        respond={props.respond}
        done={props.status === "complete"}
      />
    ),
  });
  return null;
}

function ConfirmInChat({
  eventId,
  title,
  preview,
  link,
  respond,
  done,
}: {
  eventId: string;
  title: string;
  preview: string;
  link: string;
  respond?: (r: unknown) => Promise<void>;
  done: boolean;
}) {
  const [answer, setAnswer] = useState<"submitted" | "cancelled" | null>(null);
  const disabled = !respond || done || answer !== null;

  const send = (ok: boolean) => {
    setAnswer(ok ? "submitted" : "cancelled");
    void respond?.(ok ? { event_id: eventId, confirmed_at: new Date().toISOString() } : { event_id: eventId, declined: true });
  };

  return (
    <div className="my-2 space-y-2 rounded-lg border border-line p-3">
      <p className="text-sm font-semibold text-ink">{title}</p>
      <pre className="whitespace-pre-wrap font-sans text-sm text-ink">{preview}</pre>
      {link && (
        <a href={link} target="_blank" rel="noopener noreferrer" className="block break-all text-sm underline">
          Open the sign-up page
        </a>
      )}
      <div className="flex gap-2">
        <button type="button" className="btn btn-primary" disabled={disabled} onClick={() => send(true)}>
          Submit sign-up
        </button>
        <button type="button" className="btn btn-secondary" disabled={disabled} onClick={() => send(false)}>
          Cancel
        </button>
      </div>
      <p className="text-sm text-muted" aria-live="polite">
        {answer === "submitted" && "You confirmed the sign-up."}
        {answer === "cancelled" && "You cancelled the sign-up."}
        {!answer && done && "Answer recorded."}
      </p>
    </div>
  );
}
