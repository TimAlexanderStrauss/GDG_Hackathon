"use client";

import { useState } from "react";
import { IMPORT_PROMPT, parseImport, type ImportResult } from "@/lib/profile";

/** Prefill the form from ChatGPT, Claude, Grok or any assistant that knows the user. */
export function ImportPanel({ onApply }: { onApply: (r: ImportResult) => void }) {
  const [copied, setCopied] = useState(false);
  const [text, setText] = useState("");
  const [msg, setMsg] = useState<{ kind: "ok" | "bad"; text: string } | null>(null);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(IMPORT_PROMPT);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setMsg({ kind: "bad", text: "Copy failed. Select the prompt and copy it by hand." });
    }
  };

  const apply = () => {
    const r = parseImport(text);
    if (!r) {
      setMsg({ kind: "bad", text: "No preferences found. Paste the assistant's JSON reply." });
      return;
    }
    onApply(r);
    setMsg({
      kind: "ok",
      text: `Filled ${r.filled.length} ${r.filled.length === 1 ? "field" : "fields"}. Review them below.`,
    });
  };

  return (
    <details className="panel group mt-10">
      <summary className="flex min-h-16 cursor-pointer list-none items-center justify-between gap-4 px-6 py-4 [&::-webkit-details-marker]:hidden">
        <span>
          <span className="block font-bold">Already told ChatGPT, Claude or Grok what you like?</span>
          <span className="block text-sm text-muted">Import your preferences in two steps.</span>
        </span>
        <svg
          aria-hidden
          viewBox="0 0 24 24"
          width={20}
          height={20}
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          className="shrink-0 transition-transform group-open:rotate-180"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </summary>

      <div className="grid gap-6 border-t border-line px-6 py-6 sm:grid-cols-2">
        <div>
          <p className="text-sm font-bold">1. Copy this prompt into your assistant</p>
          <pre className="mt-2 max-h-44 overflow-auto rounded-[12px] border border-line bg-surface-2 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-muted">
            {IMPORT_PROMPT}
          </pre>
          <button type="button" className="btn btn-secondary btn-sm mt-3 w-full" onClick={copy}>
            {copied ? "Copied" : "Copy prompt"}
          </button>
        </div>
        <div className="flex flex-col">
          <label htmlFor="imp-text" className="text-sm font-bold">
            2. Paste its reply
          </label>
          <textarea
            id="imp-text"
            className="field mt-2 min-h-44 flex-1 py-3 font-mono text-xs"
            placeholder='{"display_name": "Lea", "city": "Münster", ...}'
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setMsg(null);
            }}
          />
          <button type="button" className="btn btn-primary btn-sm mt-3 w-full" onClick={apply} disabled={!text.trim()}>
            Fill the form
          </button>
        </div>
        {msg && (
          <p role="status" className={`text-sm font-semibold sm:col-span-2 ${msg.kind === "ok" ? "text-ok" : "text-bad"}`}>
            {msg.text}
          </p>
        )}
        <p className="text-xs text-muted sm:col-span-2">
          Imported text only fills in preferences. It can&apos;t give enrollment consent or sign you up for anything.
        </p>
      </div>
    </details>
  );
}
