import { NextResponse } from "next/server";

const cookieName = "manga_alpha_session";

function truthy(value: string | undefined) {
  return value === "true" || value === "1" || value === "yes";
}

export async function POST(request: Request) {
  const authEnabled = truthy(process.env.ALPHA_AUTH_ENABLED);
  const sessionSecret = process.env.ALPHA_SESSION_SECRET ?? process.env.ALPHA_SHARED_PASSWORD ?? "";
  const sharedPassword = process.env.ALPHA_SHARED_PASSWORD ?? "";
  const adminToken = process.env.ALPHA_ADMIN_TOKEN ?? "";
  const body = (await request.json().catch(() => ({}))) as { password?: string };
  const password = body.password ?? "";

  if (authEnabled && password !== sharedPassword && password !== adminToken) {
    return NextResponse.json({ detail: "Invalid alpha password" }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true, auth_enabled: authEnabled });
  response.cookies.set(cookieName, authEnabled ? sessionSecret : "dev-disabled", {
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
  response.cookies.delete(cookieName);
  return response;
}
