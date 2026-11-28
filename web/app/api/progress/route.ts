import { auth } from "@/auth";

const CONCIERGE_URL = process.env.CONCIERGE_URL ?? "http://localhost:8000/";
const IDLE = { active: false, pct: 0, stage: "idle", text: "" };

// Scan progress of the signed-in user. The user id comes from the session, never from the browser.
export async function GET() {
  try {
    const email = (await auth())?.user?.email?.trim().toLowerCase();
    const res = await fetch(new URL("progress", CONCIERGE_URL), {
      headers: { "X-Sidequest-User": email ? `google:${email}` : "demo_user" },
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) return Response.json(IDLE);
    return Response.json(await res.json(), { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json(IDLE);
  }
}
