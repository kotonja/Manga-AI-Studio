import { NextResponse, type NextRequest } from "next/server";

import { alphaSessionCookieName, verifyAlphaSessionCookieValue } from "@/lib/alpha-session";

function truthy(value: string | undefined) {
  return value === "true" || value === "1" || value === "yes";
}

export async function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  const alphaAuthEnabled = truthy(process.env.ALPHA_AUTH_ENABLED) || process.env.APP_ENV === "production";
  const session = await verifyAlphaSessionCookieValue(
    request.cookies.get(alphaSessionCookieName)?.value,
    process.env.ALPHA_SESSION_SECRET
  );
  const hasInvalidSessionCookie = Boolean(request.cookies.get(alphaSessionCookieName)?.value) && !session;
  const devAdminEnabled = isDevAdminEnabled();

  if (pathname.startsWith("/admin")) {
    if (!devAdminEnabled && !session?.is_admin) {
      return redirectToOnboarding(request, `${pathname}${search}`, "required");
    }
    return NextResponse.next();
  }

  if (alphaAuthEnabled && (!process.env.ALPHA_SESSION_SECRET || !session || hasInvalidSessionCookie)) {
    return redirectToOnboarding(request, `${pathname}${search}`);
  }

  return NextResponse.next();
}

function redirectToOnboarding(request: NextRequest, nextPath: string, admin?: string) {
  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = "/onboarding";
  loginUrl.searchParams.set("next", nextPath);
  if (admin) {
    loginUrl.searchParams.set("admin", admin);
  }
  return NextResponse.redirect(loginUrl);
}

function isDevAdminEnabled() {
  return (
    process.env.APP_ENV !== "production" &&
    (
      truthy(process.env.NEXT_PUBLIC_ENABLE_DEV_ADMIN) ||
      truthy(process.env.ENABLE_DEV_ADMIN) ||
      (process.env.NODE_ENV === "development" && process.env.NEXT_PUBLIC_ENABLE_DEV_ADMIN === "local")
    )
  );
}

function isPublicPath(pathname: string) {
  return (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api/alpha-login") ||
    pathname === "/favicon.ico" ||
    pathname === "/onboarding" ||
    pathname === "/demo"
  );
}

export const config = {
  matcher: ["/((?!.*\\..*).*)"]
};
