import { NextResponse } from "next/server";

import { alphaSessionCookieName, createAlphaSessionCookieValue } from "@/lib/alpha-session";

function truthy(value: string | undefined) {
  return value === "true" || value === "1" || value === "yes";
}

export async function POST(request: Request) {
  const authEnabled = truthy(process.env.ALPHA_AUTH_ENABLED);
  const sessionSecret = process.env.ALPHA_SESSION_SECRET ?? "";
  const sharedPassword = process.env.ALPHA_SHARED_PASSWORD ?? "";
  const adminToken = process.env.ALPHA_ADMIN_TOKEN ?? "";
  const userTokens = parseUserTokens(process.env.ALPHA_USER_TOKENS ?? "");
  const body = (await request.json().catch(() => ({}))) as { password?: string };
  const password = body.password ?? "";

  if (authEnabled && !sessionSecret) {
    return NextResponse.json({ detail: "ALPHA_SESSION_SECRET is required for browser login" }, { status: 500 });
  }

  let principal = authEnabled ? resolveLoginPrincipal(password, userTokens, sharedPassword, adminToken) : { userId: "local-dev", isAdmin: false };
  if (!principal) {
    return NextResponse.json({ detail: "Invalid alpha password" }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true, auth_enabled: authEnabled });
  const cookieValue = authEnabled
    ? await createAlphaSessionCookieValue({
        userId: principal.userId,
        isAdmin: principal.isAdmin,
        secret: sessionSecret
      })
    : "dev-disabled";
  response.cookies.set(alphaSessionCookieName, cookieValue, {
    httpOnly: true,
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 14
  });
  return response;
}

export async function DELETE() {
  const response = NextResponse.json({ ok: true });
  response.cookies.delete(alphaSessionCookieName);
  return response;
}

function resolveLoginPrincipal(
  password: string,
  userTokens: Map<string, string>,
  sharedPassword: string,
  adminToken: string
) {
  for (const [userId, token] of userTokens.entries()) {
    if (constantEqual(password, token) || constantEqual(password, `${userId}:${token}`)) {
      return { userId, isAdmin: false };
    }
  }
  if (adminToken && constantEqual(password, adminToken)) {
    return { userId: "admin", isAdmin: true };
  }
  if (sharedPassword && constantEqual(password, sharedPassword)) {
    return { userId: "alpha-user", isAdmin: false };
  }
  return null;
}

function parseUserTokens(value: string) {
  const tokens = new Map<string, string>();
  for (const item of value.split(",")) {
    const [userId, ...rest] = item.split(":");
    const token = rest.join(":");
    if (userId?.trim() && token.trim()) {
      tokens.set(userId.trim(), token.trim());
    }
  }
  return tokens;
}

function constantEqual(a: string, b: string) {
  let result = a.length ^ b.length;
  const maxLength = Math.max(a.length, b.length);
  for (let index = 0; index < maxLength; index += 1) {
    result |= (a.charCodeAt(index) || 0) ^ (b.charCodeAt(index) || 0);
  }
  return result === 0;
}
