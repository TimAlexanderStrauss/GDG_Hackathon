"use client";

import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import { signOut as authSignOut, useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { RUNTIME_PATH } from "@/lib/config";
import {
  EMPTY_DRAFT,
  loadSavedProfile,
  saveProfile,
  sessionUserId,
  toProfile,
  type ProfileDraft,
} from "@/lib/profile";
import {
  clearAll,
  loadSession,
  platformsFromSocials,
  providerLabel,
  saveSession,
  type Session,
  type Social,
} from "@/lib/session";
import type { UserProfile } from "@/lib/types";
import { AuthScreen } from "./AuthScreen";
import { Dashboard } from "./Dashboard";
import { Onboarding } from "./Onboarding";
import { SocialsStep } from "./SocialsStep";

// Flow: sign-in (Google real, others demo) -> add socials (demo) -> preferences -> dashboard.
export function ScoutApp() {
  const [loaded, setLoaded] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [editing, setEditing] = useState(false);
  const [scanRequest, setScanRequest] = useState(0);
  const auth = useSession();

  useEffect(() => {
    // Session storage is browser-only, so read it after mount (avoids hydration mismatch).
    /* eslint-disable react-hooks/set-state-in-effect */
    setSession(loadSession());
    setProfile(loadSavedProfile());
    setLoaded(true);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  const updateSession = (s: Session) => {
    saveSession(s);
    setSession(s);
  };

  useEffect(() => {
    // Back from the Google redirect: turn the Auth.js session into our Session (real name and email).
    if (loaded && !session && auth.status === "authenticated") {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      updateSession({
        provider: "google",
        name: auth.data.user?.name ?? undefined,
        email: auth.data.user?.email ?? undefined,
        socials: [],
        socialsDone: false,
      });
    }
  }, [loaded, session, auth.status, auth.data]);

  const finishSocials = (socials: Social[]) => session && updateSession({ ...session, socials, socialsDone: true });

  const submit = (d: ProfileDraft) => {
    const p = toProfile(d, profile?.user_id ?? sessionUserId());
    saveProfile(p);
    setProfile(p);
    setEditing(false);
    setScanRequest((n) => n + 1);
  };

  const signOut = async () => {
    if (session?.provider === "google") await authSignOut({ redirect: false });
    clearAll();
    setSession(null);
    setProfile(null);
    setEditing(false);
  };

  const draft: ProfileDraft = profile
    ? { ...profile }
    : {
        ...EMPTY_DRAFT,
        display_name: session?.name ?? "",
        email: session?.email ?? "",
        platforms: session?.socials.length ? platformsFromSocials(session.socials) : EMPTY_DRAFT.platforms,
      };

  let view: React.ReactNode = null;
  if (!loaded || auth.status === "loading") view = null;
  else if (!session) view = <AuthScreen onSignIn={updateSession} />;
  else if (!session.socialsDone) view = <SocialsStep initial={session.socials} onDone={finishSocials} />;
  else if (!profile || editing)
    view = (
      <Onboarding
        key={profile?.user_id ?? "new"}
        initial={draft}
        isEdit={!!profile}
        onSubmit={submit}
        onCancel={profile ? () => setEditing(false) : undefined}
      />
    );
  else view = <Dashboard profile={profile} socials={session.socials} scanRequest={scanRequest} onEdit={() => setEditing(true)} />;

  return (
    <CopilotKitProvider runtimeUrl={RUNTIME_PATH} enableInspector={false} showIntelligenceIndicator={false}>
      <div className="flex min-h-full flex-col">
        <header className="sticky top-0 z-10 border-b border-line bg-surface">
          <div className="mx-auto flex h-16 max-w-[1600px] items-center justify-between gap-3 px-4 sm:px-8">
            {/* eslint-disable-next-line @next/next/no-img-element -- static SVG logo */}
            <img src="/sidequest-logo.svg" alt="Sidequest" width={140} height={32} className="h-8 w-auto" />
            {session ? (
              <div className="flex items-center gap-2">
                {profile && !editing && session.socialsDone && (
                  <button
                    type="button"
                    onClick={() => setEditing(true)}
                    className="hidden min-h-11 items-center gap-2 rounded-full border border-line px-4 text-sm font-bold hover:border-ink md:inline-flex"
                    aria-label={`Search area: ${profile.city}, next ${profile.days_ahead} days. Change`}
                  >
                    <svg aria-hidden viewBox="0 0 24 24" width={16} height={16} fill="none" stroke="currentColor" strokeWidth={2}>
                      <path d="M12 21s-7-5.5-7-11a7 7 0 1 1 14 0c0 5.5-7 11-7 11z" />
                      <circle cx="12" cy="10" r="2.5" />
                    </svg>
                    {profile.city}
                    <span className="text-line-strong" aria-hidden>|</span>
                    Next {profile.days_ahead} days
                  </button>
                )}
                <span
                  className="grid h-11 w-11 place-items-center rounded-full border border-line font-extrabold"
                  title={`Signed in with ${providerLabel(session.provider)}${session.provider === "google" ? "" : " (demo)"}`}
                  aria-hidden
                >
                  {profile?.display_name || session.name ? (
                    (profile?.display_name || session.name || "").slice(0, 1).toUpperCase()
                  ) : (
                    <svg viewBox="0 0 24 24" width={20} height={20} fill="none" stroke="currentColor" strokeWidth={2}>
                      <circle cx="12" cy="8" r="4" />
                      <path d="M4 21c0-4 3.6-7 8-7s8 3 8 7" />
                    </svg>
                  )}
                </span>
                <span className="sr-only">Signed in with {providerLabel(session.provider)}{session.provider === "google" ? "" : " (demo)"}</span>
                <button type="button" className="btn btn-secondary btn-sm" onClick={signOut}>
                  Sign out
                </button>
              </div>
            ) : (
              <p className="hidden text-sm font-semibold text-muted sm:block">Less scrolling. More going.</p>
            )}
          </div>
        </header>
        {view}
      </div>
    </CopilotKitProvider>
  );
}
