import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

// Reads AUTH_GOOGLE_ID, AUTH_GOOGLE_SECRET and AUTH_SECRET from the environment. Scopes: identity only.
export const { handlers, auth } = NextAuth({
  providers: [Google({ authorization: { params: { scope: "openid email profile" } } })],
});
