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
      text: `Filled ${r.filled.length} ${r.filled.length === 1 ? "field" : "fields"}. Review them in the form.`,
    });
  };

  return (
    <aside className="panel h-fit p-5 sm:p-6" aria-labelledby="imp-title">
      <p className="eyebrow">Optional</p>
      <h2 id="imp-title" className="mt-2 text-lg font-medium tracking-tight">
        Import from your AI assistant
      </h2>
      <p className="mt-1.5 text-sm text-muted">
        Ask ChatGPT, Claude or Grok what it knows about your tastes, then paste the answer here.
      </p>

      <ol className="mt-5 space-y-5 text-sm">
        <li>
          <p className="font-semibold">1. Copy this prompt into your assistant</p>
          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-[var(--es-radius-s)] border border-line bg-surface-2 p-3 font-mono text-xs leading-relaxed text-muted">
            {IMPORT_PROMPT}
          </pre>
          <button type="button" className="btn btn-secondary mt-2 w-full" onClick={copy}>
            {copied ? "Copied" : "Copy prompt"}
          </button>
        </li>
        <li>
          <label htmlFor="imp-text" className="font-semibold">
            2. Paste its reply
          </label>
          <textarea
            id="imp-text"
            className="field mt-2 min-h-32 py-2.5 font-mono text-xs"
            placeholder='{"display_name": "Lea", "city": "Münster", ...}'
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setMsg(null);
            }}
          />
          <button type="button" className="btn btn-primary mt-2 w-full" onClick={apply} disabled={!text.trim()}>
            Fill the form
          </button>
        </li>
      </ol>

      {msg && (
        <p role="status" className={`mt-4 text-sm ${msg.kind === "ok" ? "text-ok" : "text-bad"}`}>
          {msg.text}
        </p>
      )}
      <p className="mt-4 text-xs text-muted">
        Imported text only fills in preferences. It can&apos;t give enrollment consent or sign you up for anything.
      </p>
    </aside>
  );
}
