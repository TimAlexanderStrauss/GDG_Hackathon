import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime, createCopilotRuntimeHandler } from "@copilotkit/runtime/v2";
import { AGENT_ID, RUNTIME_PATH } from "@/lib/config";

// Self-hosted CopilotKit runtime: proxies AG-UI runs to P3's ADK concierge.
// No CopilotKit Cloud / Intelligence account needed.
const CONCIERGE_URL = process.env.CONCIERGE_URL ?? "http://localhost:8000/";

const runtime = new CopilotRuntime({
  agents: { [AGENT_ID]: new HttpAgent({ url: CONCIERGE_URL }) },
});

const handler = createCopilotRuntimeHandler({ runtime, basePath: RUNTIME_PATH });

export const GET = (req: Request) => handler(req);
export const POST = (req: Request) => handler(req);
