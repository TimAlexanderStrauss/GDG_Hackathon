"use client";

import { useState } from "react";
import { SOCIALS, type Social } from "@/lib/session";
import { BrandIcon } from "./BrandIcon";

/** Demo "Connect" step: adding a social only records the choice; no OAuth happens. */
export function SocialsStep({ initial, onDone }: { initial: Social[]; onDone: (socials: Social[]) => void }) {
  const [added, setAdded] = useState<Social[]>(initial);
  const toggle = (s: Social) => setAdded((a) => (a.includes(s) ? a.filter((x) => x !== s) : [...a, s]));

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-10 sm:px-6 lg:py-16">
      <section className="panel p-6 sm:p-8" aria-labelledby="soc-title">
        <p className="eyebrow">Step 1 of 2</p>
        <h1 id="soc-title" className="mt-2 text-2xl font-medium tracking-tight sm:text-3xl">
          Add your socials
        </h1>
        <p className="mt-2 text-muted">
          Pick the networks you use. Instagram and TikTok also become scan sources. You can change this later.
        </p>

        <ul className="mt-6 divide-y divide-line rounded-[var(--es-radius-m)] border border-line">
          {SOCIALS.map((s) => {
            const on = added.includes(s.id);
            return (
              <li key={s.id} className="flex items-center gap-3 px-4 py-3">
                <BrandIcon icon={s.icon} size={24} />
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{s.label}</p>
                  <p className="text-xs text-muted">
                    {s.scanned ? "Public posts scanned for events" : "Not scanned yet"}
                  </p>
                </div>
                {on ? (
                  <button
                    type="button"
                    className="btn btn-secondary min-w-32 border-ok text-ok"
                    onClick={() => toggle(s.id)}
                    aria-label={`${s.label} added (demo). Remove`}
                  >
                    ✓ Added (demo)
                  </button>
                ) : (
                  <button type="button" className="btn btn-secondary min-w-32" onClick={() => toggle(s.id)}>
                    Connect
                  </button>
                )}
              </li>
            );
          })}
        </ul>

        <p className="mt-3 text-xs text-muted">
          Demo: Connect only saves your choice in this tab. No account login and no access to your private data.
        </p>

        <div className="mt-7 flex flex-wrap gap-3">
          <button type="button" className="btn btn-primary" onClick={() => onDone(added)}>
            Continue
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => onDone([])}>
            Skip for now
          </button>
        </div>
      </section>
    </div>
  );
}
