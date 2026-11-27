import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime, createCopilotRuntimeHandler } from "@copilotkit/runtime/v2";
import { auth } from "@/auth";
import { AGENT_ID, RUNTIME_PATH } from "@/lib/config";

// Self-hosted CopilotKit runtime: proxies AG-UI runs to P3's ADK concierge.
// No CopilotKit Cloud / Intelligence account needed.
const CONCIERGE_URL = process.env.CONCIERGE_URL ?? "http://localhost:8000/";

// The user id comes from the Auth.js session on the server, never from the browser. It is set as an
// agent header on every request (also "demo_user"); the runtime lets server-configured headers win
// over forwarded browser headers of the same name, so a browser-sent X-Sidequest-User is dropped.
// shortcut: the concierge trusts any caller on its port; when hosted, add a shared secret header here
// and check it in the concierge.
async function handle(req: Request) {
  const email = (await auth())?.user?.email?.trim().toLowerCase();
  const userId = email ? `google:${email}` : "demo_user";
  const runtime = new CopilotRuntime({
    agents: { [AGENT_ID]: new HttpAgent({ url: CONCIERGE_URL, headers: { "X-Sidequest-User": userId } }) },
  });
  return createCopilotRuntimeHandler({ runtime, basePath: RUNTIME_PATH })(req);
}

export const GET = handle;
export const POST = handle;
