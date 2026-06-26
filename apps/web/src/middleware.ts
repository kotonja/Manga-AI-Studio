import { NextResponse, type NextRequest } from "next/server";

const cookieName = "manga_alpha_session";

function truthy(value: string | undefined) {
  return value === "true" || value === "1" || value === "yes";
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  const alphaAuthEnabled = truthy(process.env.ALPHA_AUTH_ENABLED);
  const expectedSession = process.env.ALPHA_SESSION_SECRET ?? process.env.ALPHA_SHARED_PASSWORD ?? "";
  const hasSession = request.cookies.get(cookieName)?.value === expectedSession;

  if (alphaAuthEnabled && (!expectedSession || !hasSession)) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/onboarding";
    loginUrl.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(loginUrl);
  }

  if (pathname.startsWith("/admin") && !truthy(process.env.NEXT_PUBLIC_ENABLE_DEV_ADMIN) && !hasSession) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/onboarding";
    loginUrl.searchParams.set("admin", "required");
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
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
