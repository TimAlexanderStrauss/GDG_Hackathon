"use client";

import { useState } from "react";
import { SOCIALS, type Social } from "@/lib/session";
import { BrandIcon } from "./BrandIcon";

/** Demo "Connect" step: adding a social only records the choice; no OAuth happens. */
export function SocialsStep({ initial, onDone }: { initial: Social[]; onDone: (socials: Social[]) => void }) {
  const [added, setAdded] = useState<Social[]>(initial);
  const toggle = (s: Social) => setAdded((a) => (a.includes(s) ? a.filter((x) => x !== s) : [...a, s]));

  return (
    <div className="flex-1 bg-surface-2">
    <div className="mx-auto w-full max-w-2xl px-4 py-10 sm:px-6 lg:py-16">
      <section className="panel p-6 sm:p-10" aria-labelledby="soc-title">
        <p className="eyebrow">Step 1 of 2</p>
        <h1 id="soc-title" className="mt-2 text-4xl leading-[1.05]">
          Add your socials
        </h1>
        <p className="mt-3 text-lg text-muted">
          Pick the networks you use. Instagram and TikTok also become scan sources. Soon, the accounts you follow there will tune your recommendations too.
        </p>

        <ul className="mt-8 divide-y divide-line rounded-[16px] border border-line">
          {SOCIALS.map((s) => {
            const on = added.includes(s.id);
            return (
              <li key={s.id} className="flex items-center gap-4 px-5 py-4">
                <BrandIcon icon={s.icon} size={24} />
                <div className="min-w-0 flex-1">
                  <p className="font-bold">{s.label}</p>
                  <p className="text-xs text-muted">
                    {s.scanned ? "Public posts scanned for events" : "Not scanned yet"}
                  </p>
                </div>
                {on ? (
                  <button
                    type="button"
                    className="btn btn-sm min-w-36 bg-accent-soft"
                    onClick={() => toggle(s.id)}
                    aria-label={`${s.label} added (demo). Remove`}
                  >
                    ✓ Added (demo)
                  </button>
                ) : (
                  <button type="button" className="btn btn-secondary btn-sm min-w-36" onClick={() => toggle(s.id)}>
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

        <div className="mt-10 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button type="button" className="btn btn-secondary" onClick={() => onDone([])}>
            Skip for now
          </button>
          <button type="button" className="btn btn-primary sm:min-w-48" onClick={() => onDone(added)}>
            Continue
          </button>
        </div>
      </section>
    </div>
    </div>
  );
}
