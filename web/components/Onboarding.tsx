"use client";

import { useState, type FormEvent } from "react";
import {
  DAYS_MAX,
  DAYS_MIN,
  MAX_INTERESTS,
  SUGGESTED_INTERESTS,
  validateDraft,
  type DraftErrors,
  type ImportResult,
  type ProfileDraft,
} from "@/lib/profile";
import { PLANNED_PLATFORMS, PLATFORMS, type Platform } from "@/lib/types";
import { ImportPanel } from "./ImportPanel";

type Props = {
  initial: ProfileDraft;
  isEdit: boolean;
  onSubmit: (draft: ProfileDraft) => void;
  onCancel?: () => void;
};

const FIELD_LABELS: Record<keyof ProfileDraft, string> = {
  display_name: "Name",
  email: "Email",
  city: "City",
  interests: "Interests",
  days_ahead: "Days ahead",
  platforms: "Sources",
  consent_enrollment: "Enrollment consent",
};

export function Onboarding({ initial, isEdit, onSubmit, onCancel }: Props) {
  const [d, setD] = useState<ProfileDraft>(initial);
  const [errors, setErrors] = useState<DraftErrors>({});
  const [custom, setCustom] = useState("");
  const [imported, setImported] = useState<(keyof ProfileDraft)[]>([]);

  const set = <K extends keyof ProfileDraft>(k: K, v: ProfileDraft[K]) => {
    setD((prev) => ({ ...prev, [k]: v }));
    if (errors[k]) setErrors((e) => ({ ...e, [k]: undefined }));
  };

  const toggleInterest = (i: string) =>
    set("interests", d.interests.includes(i) ? d.interests.filter((x) => x !== i) : [...d.interests, i]);

  const addCustom = () => {
    const v = custom.trim().slice(0, 30);
    if (!v) return;
    if (!d.interests.some((x) => x.toLowerCase() === v.toLowerCase())) set("interests", [...d.interests, v]);
    setCustom("");
  };

  const togglePlatform = (p: Platform) =>
    set("platforms", d.platforms.includes(p) ? d.platforms.filter((x) => x !== p) : [...d.platforms, p]);

  const applyImport = (r: ImportResult) => {
    setD((prev) => ({ ...prev, ...r.patch }));
    setImported(r.filled);
    setErrors({});
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const errs = validateDraft(d);
    setErrors(errs);
    const first = Object.keys(errs)[0];
    if (first) {
      document.getElementById(`f-${first}`)?.focus();
      return;
    }
    onSubmit(d);
  };

  const missing = imported.length
    ? (Object.keys(validateDraft(d)) as (keyof ProfileDraft)[]).map((k) => FIELD_LABELS[k])
    : [];
  const chipSet = [...new Set([...SUGGESTED_INTERESTS, ...d.interests])];
  const mark = (k: keyof ProfileDraft) =>
    imported.includes(k) ? <span className="ml-2 text-xs font-medium text-accent">Imported</span> : null;

  return (
    <div className="mx-auto grid w-full max-w-6xl gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[minmax(0,1fr)_380px] lg:py-12">
      <form onSubmit={submit} noValidate className="panel p-5 sm:p-8" aria-labelledby="onb-title">
        <p className="eyebrow">{isEdit ? "Preferences" : "Step 2 of 2"}</p>
        <h1 id="onb-title" className="mt-2 text-2xl font-medium tracking-tight sm:text-3xl">
          {isEdit ? "Edit what Sidequest looks for" : "Tell Sidequest what you like"}
        </h1>
        <p className="mt-2 max-w-prose text-muted">
          Scouts read public posts for your city and rank events against these preferences. Nothing is booked
          without your click.
        </p>

        {missing.length > 0 && (
          <p role="status" className="mt-5 rounded-[var(--es-radius-s)] bg-accent-soft px-4 py-3 text-sm">
            Imported {imported.length} {imported.length === 1 ? "field" : "fields"}. Still needed:{" "}
            <strong>{missing.join(", ")}</strong>.
          </p>
        )}

        <div className="mt-7 grid gap-5 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="f-display_name">
              Name {mark("display_name")}
            </label>
            <input
              id="f-display_name"
              className="field"
              autoComplete="given-name"
              value={d.display_name}
              onChange={(e) => set("display_name", e.target.value)}
              aria-invalid={!!errors.display_name}
              aria-describedby={errors.display_name ? "e-display_name" : undefined}
            />
            <FieldError id="e-display_name" msg={errors.display_name} />
          </div>
          <div>
            <label className="label" htmlFor="f-email">
              Email
            </label>
            <input
              id="f-email"
              className="field"
              type="email"
              autoComplete="email"
              value={d.email}
              onChange={(e) => set("email", e.target.value)}
              aria-invalid={!!errors.email}
              aria-describedby={errors.email ? "e-email" : "h-email"}
            />
            {errors.email ? (
              <FieldError id="e-email" msg={errors.email} />
            ) : (
              <p id="h-email" className="mt-1.5 text-xs text-muted">
                Only sent to the enrollment agent after you click Enroll me.
              </p>
            )}
          </div>
          <div>
            <label className="label" htmlFor="f-city">
              City {mark("city")}
            </label>
            <input
              id="f-city"
              className="field"
              autoComplete="address-level2"
              value={d.city}
              onChange={(e) => set("city", e.target.value)}
              aria-invalid={!!errors.city}
              aria-describedby={errors.city ? "e-city" : undefined}
            />
            <FieldError id="e-city" msg={errors.city} />
          </div>
          <div>
            <label className="label" htmlFor="f-days_ahead">
              Look ahead {mark("days_ahead")}
            </label>
            <div className="flex items-center gap-3">
              <input
                id="f-days_ahead"
                type="range"
                min={DAYS_MIN}
                max={DAYS_MAX}
                value={d.days_ahead}
                onChange={(e) => set("days_ahead", Number(e.target.value))}
                className="h-11 flex-1 accent-[var(--es-accent)]"
                aria-valuetext={`${d.days_ahead} days`}
              />
              <span className="w-16 text-right text-sm font-semibold tabular-nums">{d.days_ahead} days</span>
            </div>
            <FieldError id="e-days_ahead" msg={errors.days_ahead} />
          </div>
        </div>

        <fieldset className="mt-7" aria-describedby={errors.interests ? "e-interests" : undefined}>
          <legend className="label">
            Interests {mark("interests")}
            <span className="ml-2 font-normal text-muted">
              {d.interests.length}/{MAX_INTERESTS}
            </span>
          </legend>
          <div id="f-interests" tabIndex={-1} className="flex flex-wrap gap-2">
            {chipSet.map((i) => (
              <button
                key={i}
                type="button"
                className="chip"
                aria-pressed={d.interests.includes(i)}
                onClick={() => toggleInterest(i)}
                disabled={!d.interests.includes(i) && d.interests.length >= MAX_INTERESTS}
              >
                {i}
              </button>
            ))}
          </div>
          <div className="mt-3 flex max-w-sm gap-2">
            <label htmlFor="f-custom" className="sr-only">
              Add your own interest
            </label>
            <input
              id="f-custom"
              className="field"
              placeholder="Add your own, e.g. Jazz"
              value={custom}
              maxLength={30}
              onChange={(e) => setCustom(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addCustom();
                }
              }}
            />
            <button
              type="button"
              className="btn btn-secondary"
              onClick={addCustom}
              disabled={!custom.trim() || d.interests.length >= MAX_INTERESTS}
            >
              Add
            </button>
          </div>
          <FieldError id="e-interests" msg={errors.interests} />
        </fieldset>

        <fieldset className="mt-7" aria-describedby="h-platforms">
          <legend className="label">Sources to scan {mark("platforms")}</legend>
          <div id="f-platforms" tabIndex={-1} className="flex flex-wrap gap-2">
            {PLATFORMS.map((p) => (
              <button
                key={p.id}
                type="button"
                className="chip"
                aria-pressed={d.platforms.includes(p.id)}
                onClick={() => togglePlatform(p.id)}
              >
                {p.label}
              </button>
            ))}
            {PLANNED_PLATFORMS.map((p) => (
              <button key={p.id} type="button" className="chip" disabled aria-pressed={false}>
                {p.label}
                <span className="text-xs text-muted">soon</span>
              </button>
            ))}
          </div>
          <p id="h-platforms" className="mt-2 text-xs text-muted">
            Scouts read public posts only. No account login is needed. X and Facebook are not in today&apos;s demo.
          </p>
          <FieldError id="e-platforms" msg={errors.platforms} />
        </fieldset>

        <div className="mt-7 rounded-[var(--es-radius-s)] border border-line bg-surface-2 p-4">
          <label className="flex cursor-pointer items-start gap-3">
            <input
              id="f-consent_enrollment"
              type="checkbox"
              className="mt-1 h-5 w-5 shrink-0 accent-[var(--es-accent)]"
              checked={d.consent_enrollment}
              onChange={(e) => set("consent_enrollment", e.target.checked)}
            />
            <span>
              <span className="font-semibold">May enroll me after my click</span>
              <span className="mt-0.5 block text-sm text-muted">
                Lets the enrollment agent fill a sign-up form for an event when you click Enroll me on it. It never
                signs you up for anything you didn&apos;t click.
              </span>
            </span>
          </label>
        </div>

        <div className="mt-8 flex flex-wrap gap-3">
          <button type="submit" className="btn btn-primary">
            {isEdit ? "Save and scan again" : "Save and find events"}
          </button>
          {onCancel && (
            <button type="button" className="btn btn-secondary" onClick={onCancel}>
              Cancel
            </button>
          )}
        </div>
      </form>

      <ImportPanel onApply={applyImport} />
    </div>
  );
}

function FieldError({ id, msg }: { id: string; msg?: string }) {
  if (!msg) return null;
  return (
    <p id={id} className="mt-1.5 text-sm text-bad">
      {msg}
    </p>
  );
}
