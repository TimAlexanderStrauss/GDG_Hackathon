"use client";

import { useState, type FormEvent } from "react";
import { PROVIDERS, type Session } from "@/lib/session";
import { BrandIcon } from "./BrandIcon";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const POINTS = [
  "Scouts read public Instagram, TikTok and web posts for your city.",
  "Posts that try to trick an AI are blocked before any model reads them.",
  "Nothing is booked until you click Enroll me.",
];

/** Demo sign-in: every option creates a local session only. */
export function AuthScreen({ onSignIn }: { onSignIn: (s: Session) => void }) {
  const [mode, setMode] = useState<"register" | "login">("register");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  const viaProvider = (provider: Session["provider"]) =>
    onSignIn({
      provider,
      socials: provider === "instagram" || provider === "x" || provider === "facebook" ? [provider] : [],
      socialsDone: false,
    });

  const viaEmail = (e: FormEvent) => {
    e.preventDefault();
    if (!EMAIL_RE.test(email.trim())) {
      setError("Enter a valid email address.");
      document.getElementById("auth-email")?.focus();
      return;
    }
    onSignIn({ provider: "email", email: email.trim(), name: name.trim() || undefined, socials: [], socialsDone: false });
  };

  const isRegister = mode === "register";

  return (
    <div className="flex-1 bg-surface-2">
      <div className="mx-auto grid w-full max-w-6xl items-center gap-10 px-4 py-10 sm:px-8 lg:min-h-[calc(100vh-4rem)] lg:grid-cols-[minmax(0,1fr)_440px] lg:py-16">
        <div className="relative max-w-xl">
          {/* eslint-disable-next-line @next/next/no-img-element -- decorative static SVG */}
          <img src="/sidequest-mark.svg" alt="" aria-hidden width={72} height={72} className="h-[72px] w-[72px]" />
          <h1 className="mt-6 text-5xl leading-[1.02] text-balance sm:text-6xl">Less scrolling. More going.</h1>
          <p className="mt-5 text-xl text-muted">
            Sidequest finds the events in Münster that match your interests, and signs you up when you say so.
          </p>
          <ul className="mt-8 space-y-3">
            {POINTS.map((p) => (
              <li key={p} className="flex gap-3 font-semibold">
                <span
                  aria-hidden
                  className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-accent-soft text-xs"
                >
                  ✓
                </span>
                {p}
              </li>
            ))}
          </ul>
        </div>

        <section className="panel p-6 sm:p-8" aria-labelledby="auth-title">
          <h2 id="auth-title" className="text-2xl">
            {isRegister ? "Create your account" : "Welcome back"}
          </h2>
          <p className="mt-1 text-sm text-muted">
            {isRegister ? "Already have one? " : "New here? "}
            <button
              type="button"
              className="min-h-11 font-bold text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink"
              onClick={() => {
                setMode(isRegister ? "login" : "register");
                setError(null);
              }}
            >
              {isRegister ? "Log in" : "Create an account"}
            </button>
          </p>

          <div className="mt-5 grid gap-3">
            {PROVIDERS.map((p) => (
              <button key={p.id} type="button" className="btn btn-secondary w-full justify-start" onClick={() => viaProvider(p.id)}>
                <BrandIcon icon={p.icon} />
                <span className="flex-1 text-center">Continue with {p.label}</span>
                <span className="w-5" aria-hidden />
              </button>
            ))}
          </div>

          <div className="my-6 flex items-center gap-3 text-xs font-semibold text-muted" aria-hidden>
            <span className="h-px flex-1 bg-line" /> or with email <span className="h-px flex-1 bg-line" />
          </div>

          <form onSubmit={viaEmail} noValidate className="grid gap-4">
            {isRegister && (
              <div>
                <label className="label" htmlFor="auth-name">
                  Name
                </label>
                <input id="auth-name" className="field" autoComplete="given-name" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
            )}
            <div>
              <label className="label" htmlFor="auth-email">
                Email
              </label>
              <input
                id="auth-email"
                className="field"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setError(null);
                }}
                aria-invalid={!!error}
                aria-describedby={error ? "auth-err" : undefined}
              />
              {error && (
                <p id="auth-err" className="mt-2 text-sm font-semibold text-bad">
                  {error}
                </p>
              )}
            </div>
            <button type="submit" className="btn btn-primary w-full">
              {isRegister ? "Create account" : "Log in"}
            </button>
          </form>

          <p className="mt-6 rounded-[12px] bg-surface-2 px-4 py-3 text-xs text-muted">
            <strong className="text-ink">Demo sign-in.</strong> No password and no real Google, Instagram, X or Facebook
            login. Your session stays in this browser tab.
          </p>
        </section>
      </div>
    </div>
  );
}
