"use client";

import { useState, type FormEvent } from "react";
import { PROVIDERS, type Session } from "@/lib/session";
import { BrandIcon } from "./BrandIcon";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Demo sign-in: every option creates a local session only. */
export function AuthScreen({ onSignIn }: { onSignIn: (s: Session) => void }) {
  const [mode, setMode] = useState<"register" | "login">("register");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  const viaProvider = (provider: Session["provider"]) =>
    onSignIn({ provider, socials: provider === "instagram" || provider === "x" || provider === "facebook" ? [provider] : [], socialsDone: false });

  const viaEmail = (e: FormEvent) => {
    e.preventDefault();
    if (!EMAIL_RE.test(email.trim())) {
      setError("Enter a valid email address.");
      document.getElementById("auth-email")?.focus();
      return;
    }
    onSignIn({
      provider: "email",
      email: email.trim(),
      name: name.trim() || undefined,
      socials: [],
      socialsDone: false,
    });
  };

  const isRegister = mode === "register";

  return (
    <div className="mx-auto grid w-full max-w-5xl items-center gap-10 px-4 py-10 sm:px-6 lg:min-h-[calc(100vh-3.5rem)] lg:grid-cols-[minmax(0,1fr)_420px] lg:py-16">
      <div className="max-w-xl">
        <p className="eyebrow">Sidequest · Münster</p>
        <h1 className="mt-3 text-3xl font-medium tracking-tight sm:text-5xl">
          The events your feed hides, found and booked on your click.
        </h1>
        <p className="mt-4 text-lg text-muted">
          Scout agents read public Instagram, TikTok and web posts for your city, drop anything that tries to trick an
          AI, and rank the rest against what you like.
        </p>
        <ul className="mt-6 space-y-2 text-sm">
          <li className="flex gap-2">
            <span aria-hidden className="text-accent">●</span> Every tool call shows up in a live audit log.
          </li>
          <li className="flex gap-2">
            <span aria-hidden className="text-accent">●</span> Nothing is booked until you click Enroll me.
          </li>
        </ul>
      </div>

      <section className="panel p-6 sm:p-8" aria-labelledby="auth-title">
        <h2 id="auth-title" className="text-xl font-medium tracking-tight">
          {isRegister ? "Create your account" : "Log in"}
        </h2>
        <p className="mt-1 text-sm text-muted">
          {isRegister ? "Already have one? " : "New here? "}
          <button
            type="button"
            className="min-h-11 font-medium text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink"
            onClick={() => {
              setMode(isRegister ? "login" : "register");
              setError(null);
            }}
          >
            {isRegister ? "Log in" : "Create an account"}
          </button>
        </p>

        <div className="mt-5 grid gap-2.5">
          {PROVIDERS.map((p) => (
            <button key={p.id} type="button" className="btn btn-secondary w-full justify-start" onClick={() => viaProvider(p.id)}>
              <BrandIcon icon={p.icon} />
              <span className="flex-1 text-center">Continue with {p.label}</span>
              <span className="w-5" aria-hidden />
            </button>
          ))}
        </div>

        <div className="my-5 flex items-center gap-3 text-xs text-muted" aria-hidden>
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
              <p id="auth-err" className="mt-1.5 text-sm text-bad">
                {error}
              </p>
            )}
          </div>
          <button type="submit" className="btn btn-primary w-full">
            {isRegister ? "Create account" : "Log in"}
          </button>
        </form>

        <p className="mt-5 rounded-[var(--es-radius-s)] bg-surface-2 px-3 py-2.5 text-xs text-muted">
          <strong className="text-ink">Demo sign-in.</strong> No password and no real Google, Instagram, X or Facebook
          login: your session stays in this browser tab.
        </p>
      </section>
    </div>
  );
}
