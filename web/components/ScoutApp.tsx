"use client";

import { CopilotKitProvider } from "@copilotkit/react-core/v2";
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

// Flow: demo sign-in -> add socials (demo) -> preferences -> dashboard.
export function ScoutApp() {
  const [loaded, setLoaded] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [editing, setEditing] = useState(false);
  const [scanRequest, setScanRequest] = useState(0);

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

  const finishSocials = (socials: Social[]) => session && updateSession({ ...session, socials, socialsDone: true });

  const submit = (d: ProfileDraft) => {
    const p = toProfile(d, profile?.user_id ?? sessionUserId());
    saveProfile(p);
    setProfile(p);
    setEditing(false);
    setScanRequest((n) => n + 1);
  };

  const signOut = () => {
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
  if (!loaded) view = null;
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
  else view = <Dashboard profile={profile} scanRequest={scanRequest} onEdit={() => setEditing(true)} />;

  return (
    <CopilotKitProvider runtimeUrl={RUNTIME_PATH} enableInspector={false} showIntelligenceIndicator={false}>
      <div className="flex min-h-full flex-col">
        <header className="sticky top-0 z-10 border-b border-line bg-bg/90 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-[1500px] items-center justify-between gap-3 px-4 sm:px-6">
            {/* eslint-disable-next-line @next/next/no-img-element -- static SVG logo */}
            <img src="/sidequest-logo.svg" alt="Sidequest" width={132} height={30} className="h-[30px] w-auto" />
            {session ? (
              <div className="flex items-center gap-3">
                <p className="hidden text-sm text-muted sm:block">
                  Signed in with {providerLabel(session.provider)} (demo)
                </p>
                <button type="button" className="btn btn-secondary min-h-9 px-3 text-sm" onClick={signOut}>
                  Sign out
                </button>
              </div>
            ) : (
              <p className="hidden text-sm text-muted sm:block">Events from public posts, booked only on your click</p>
            )}
          </div>
        </header>
        {view}
      </div>
    </CopilotKitProvider>
  );
}
