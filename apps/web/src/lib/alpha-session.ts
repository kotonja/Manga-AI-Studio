export const alphaSessionCookieName = "manga_alpha_session";

const version = "v1";
const ttlSeconds = 60 * 60 * 24 * 14;
const encoder = new TextEncoder();

export type AlphaSessionPayload = {
  user_id: string;
  is_admin: boolean;
  iat: number;
  exp: number;
};

export async function createAlphaSessionCookieValue(input: {
  userId: string;
  isAdmin: boolean;
  secret: string;
  now?: number;
}) {
  const issuedAt = input.now ?? Math.floor(Date.now() / 1000);
  const payload: AlphaSessionPayload = {
    user_id: input.userId,
    is_admin: input.isAdmin,
    iat: issuedAt,
    exp: issuedAt + ttlSeconds
  };
  const payloadSegment = base64UrlEncode(encoder.encode(stableStringify(payload)));
  const signature = await sign(payloadSegment, input.secret);
  return `${version}.${payloadSegment}.${signature}`;
}

export async function verifyAlphaSessionCookieValue(value: string | undefined, secret: string | undefined) {
  if (!value || !secret) {
    return null;
  }
  const [cookieVersion, payloadSegment, signature, extra] = value.split(".");
  if (cookieVersion !== version || !payloadSegment || !signature || extra !== undefined) {
    return null;
  }
  const expected = await sign(payloadSegment, secret);
  if (!constantTimeEqual(signature, expected)) {
    return null;
  }
  try {
    const payload = JSON.parse(new TextDecoder().decode(base64UrlDecode(payloadSegment))) as AlphaSessionPayload;
    if (!validPayload(payload)) {
      return null;
    }
    if (payload.exp < Math.floor(Date.now() / 1000)) {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

async function sign(payloadSegment: string, secret: string) {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const digest = await crypto.subtle.sign("HMAC", key, encoder.encode(payloadSegment));
  return base64UrlEncode(new Uint8Array(digest));
}

function stableStringify(payload: AlphaSessionPayload) {
  return JSON.stringify({
    exp: payload.exp,
    iat: payload.iat,
    is_admin: payload.is_admin,
    user_id: payload.user_id
  });
}

function validPayload(payload: AlphaSessionPayload) {
  return (
    typeof payload === "object" &&
    typeof payload.user_id === "string" &&
    payload.user_id.trim().length > 0 &&
    typeof payload.is_admin === "boolean" &&
    Number.isInteger(payload.iat) &&
    Number.isInteger(payload.exp) &&
    payload.exp >= payload.iat
  );
}

function base64UrlEncode(bytes: Uint8Array) {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function base64UrlDecode(value: string) {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(value.length / 4) * 4, "=");
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function constantTimeEqual(a: string, b: string) {
  let result = a.length ^ b.length;
  const maxLength = Math.max(a.length, b.length);
  for (let index = 0; index < maxLength; index += 1) {
    result |= (a.charCodeAt(index) || 0) ^ (b.charCodeAt(index) || 0);
  }
  return result === 0;
}
