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
    imported.includes(k) ? <span className="ml-2 text-xs font-semibold text-muted">Imported</span> : null;

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6 sm:py-16">
      <header className="text-center">
        <p className="eyebrow">{isEdit ? "Your preferences" : "Step 2 of 2"}</p>
        <h1 className="mt-3 text-4xl leading-[1.05] text-balance sm:text-6xl">Less scrolling. More going.</h1>
        <p className="mx-auto mt-4 max-w-xl text-lg text-muted">
          Pick a few interests so we can find local events you&apos;ll actually love. Nothing is booked without your
          click.
        </p>
      </header>

      <ImportPanel onApply={applyImport} />

      <form onSubmit={submit} noValidate className="panel mt-6 p-6 sm:p-10" aria-label="Your preferences">
        {missing.length > 0 && (
          <p role="status" className="mb-8 rounded-[12px] bg-accent-soft px-4 py-3 text-sm">
            Imported {imported.length} {imported.length === 1 ? "field" : "fields"}. Still needed:{" "}
            <strong>{missing.join(", ")}</strong>.
          </p>
        )}

        <fieldset aria-describedby={errors.interests ? "e-interests" : undefined}>
          <legend className="text-2xl font-extrabold tracking-tight">
            What are you into? {mark("interests")}
          </legend>
          <p className="mt-1 text-sm text-muted">
            {d.interests.length} of {MAX_INTERESTS} picked
          </p>
          <div id="f-interests" tabIndex={-1} className="mt-5 flex flex-wrap gap-3">
            {chipSet.map((i) => (
              <button
                key={i}
                type="button"
                className="chip chip-lg"
                aria-pressed={d.interests.includes(i)}
                onClick={() => toggleInterest(i)}
                disabled={!d.interests.includes(i) && d.interests.length >= MAX_INTERESTS}
              >
                {i}
              </button>
            ))}
          </div>
          <div className="mt-4 flex max-w-md gap-2">
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

        <hr className="my-10 border-line" />

        <div className="grid gap-6 sm:grid-cols-2">
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
              <p id="h-email" className="mt-2 text-xs text-muted">
                Only shared with the enrollment agent after you click Enroll me.
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
            <div className="flex min-h-12 items-center gap-4">
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
              <span className="w-20 text-right font-bold tabular-nums">{d.days_ahead} days</span>
            </div>
            <FieldError id="e-days_ahead" msg={errors.days_ahead} />
          </div>
        </div>

        <fieldset className="mt-8" aria-describedby="h-platforms">
          <legend className="label">Where should your scouts look? {mark("platforms")}</legend>
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
                {p.label} <span className="text-xs">soon</span>
              </button>
            ))}
          </div>
          <p id="h-platforms" className="mt-2 text-xs text-muted">
            Public posts only, no account login. X and Facebook are not in today&apos;s demo.
          </p>
          <FieldError id="e-platforms" msg={errors.platforms} />
        </fieldset>

        <label className="mt-8 flex cursor-pointer items-start gap-3 rounded-[12px] bg-surface-2 p-4">
          <input
            id="f-consent_enrollment"
            type="checkbox"
            className="mt-0.5 h-5 w-5 shrink-0 accent-[var(--es-accent)]"
            checked={d.consent_enrollment}
            onChange={(e) => set("consent_enrollment", e.target.checked)}
          />
          <span>
            <span className="font-bold">May enroll me after my click</span>
            <span className="mt-0.5 block text-sm text-muted">
              Lets the enrollment agent fill a sign-up form when you click Enroll me on an event. It never signs you up
              for anything you didn&apos;t click.
            </span>
          </span>
        </label>

        <div className="mt-10 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          {onCancel && (
            <button type="button" className="btn btn-secondary" onClick={onCancel}>
              Cancel
            </button>
          )}
          <button type="submit" className="btn btn-primary sm:min-w-56">
            Find my events
          </button>
        </div>
      </form>
    </div>
  );
}

function FieldError({ id, msg }: { id: string; msg?: string }) {
  if (!msg) return null;
  return (
    <p id={id} className="mt-2 text-sm font-semibold text-bad">
      {msg}
    </p>
  );
}
