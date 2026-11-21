import { Suspense } from "react";
import { ScoutApp } from "@/components/ScoutApp";

// ScoutApp is browser-only state (session, agent connection), so it streams in
// instead of being prerendered (cacheComponents would flag CopilotKit's Date.now()).
export default function Home() {
  return (
    <Suspense fallback={null}>
      <ScoutApp />
    </Suspense>
  );
}
