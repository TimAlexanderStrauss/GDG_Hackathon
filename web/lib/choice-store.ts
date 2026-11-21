"use client";

import { useSyncExternalStore } from "react";
import type { ChooseEventResponse, Event } from "./types";

// Bridges the `choose_event` human-in-the-loop call (rendered inside the chat)
// with the main event-card area, so either place can answer it exactly once.

export type PendingChoice = {
  toolCallId: string;
  events: Event[];
  respond: (r: ChooseEventResponse) => Promise<void>;
};

type Snapshot = { pending: PendingChoice | null; answered: Record<string, ChooseEventResponse> };

let snap: Snapshot = { pending: null, answered: {} };
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export function offerChoice(p: PendingChoice) {
  if (snap.answered[p.toolCallId] || snap.pending?.toolCallId === p.toolCallId) return;
  snap = { ...snap, pending: p };
  emit();
}

export function withdrawChoice(toolCallId: string) {
  if (snap.pending?.toolCallId !== toolCallId) return;
  snap = { ...snap, pending: null };
  emit();
}

/** Answers the pending call once; later clicks are ignored. */
export async function answerChoice(toolCallId: string, r: ChooseEventResponse) {
  const p = snap.pending;
  if (!p || p.toolCallId !== toolCallId || snap.answered[toolCallId]) return;
  snap = { pending: null, answered: { ...snap.answered, [toolCallId]: r } };
  emit();
  await p.respond(r);
}

export function useChoice(): Snapshot {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => snap,
    () => snap,
  );
}
