import { cookies } from "next/headers";

import { alphaSessionCookieName, verifyAlphaSessionCookieValue } from "@/lib/alpha-session";

export async function isAdminAccessAllowed() {
  if (isDevAdminEnabled()) {
    return true;
  }
  const cookieStore = await cookies();
  const session = await verifyAlphaSessionCookieValue(
    cookieStore.get(alphaSessionCookieName)?.value,
    process.env.ALPHA_SESSION_SECRET
  );
  return Boolean(session?.is_admin);
}

function isDevAdminEnabled() {
  return (
    process.env.APP_ENV !== "production" &&
    (
      process.env.NEXT_PUBLIC_ENABLE_DEV_ADMIN === "true" ||
      process.env.ENABLE_DEV_ADMIN === "true" ||
      (process.env.NODE_ENV === "development" && process.env.NEXT_PUBLIC_ENABLE_DEV_ADMIN === "local")
    )
  );
}
