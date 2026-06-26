from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from contextvars import ContextVar
from contextvars import Token
import secrets
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.base import BaseHTTPMiddleware

from manga_api.config import get_settings

ALPHA_SESSION_COOKIE_NAME = "manga_alpha_session"
ALPHA_SESSION_VERSION = "v1"
ALPHA_SESSION_TTL_SECONDS = 60 * 60 * 24 * 14


@dataclass(frozen=True)
class UserPrincipal:
    user_id: str
    auth_mode: str
    is_admin: bool = False


AlphaPrincipal = UserPrincipal
_current_principal: ContextVar[UserPrincipal | None] = ContextVar("current_user_principal", default=None)


def set_current_principal(principal: UserPrincipal | None) -> Token[UserPrincipal | None]:
    return _current_principal.set(principal)


def remember_current_principal(principal: UserPrincipal) -> UserPrincipal:
    set_current_principal(principal)
    return principal


def clear_current_principal() -> Token[UserPrincipal | None]:
    return set_current_principal(None)


def reset_current_principal(token: Token[UserPrincipal | None]) -> None:
    _current_principal.reset(token)


def current_principal() -> UserPrincipal | None:
    return _current_principal.get()


def resolve_alpha_user(request: Request) -> UserPrincipal:
    settings = get_settings()
    if settings.is_local_unlocked:
        return UserPrincipal(user_id="local-dev", auth_mode="disabled")
    return authenticate_request(request, admin=False)


async def require_alpha_user(request: Request) -> UserPrincipal:
    return remember_current_principal(resolve_alpha_user(request))


def get_current_principal(principal: UserPrincipal = Depends(require_alpha_user)) -> UserPrincipal:
    return principal


async def require_sensitive_access(request: Request) -> UserPrincipal:
    settings = get_settings()
    if settings.is_local_unlocked:
        return remember_current_principal(UserPrincipal(user_id="local-dev", auth_mode="disabled"))
    return remember_current_principal(authenticate_request(request, admin=False))


async def require_admin_access(request: Request) -> UserPrincipal:
    settings = get_settings()
    if settings.enable_dev_admin and not settings.is_production:
        return remember_current_principal(UserPrincipal(user_id="dev-admin", auth_mode="dev-admin", is_admin=True))
    if settings.is_local_unlocked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin routes are disabled")
    return remember_current_principal(authenticate_request(request, admin=True))


def authenticate_request(request: Request, *, admin: bool) -> UserPrincipal:
    settings = get_settings()
    mode = settings.auth_provider_mode.lower().strip()

    if mode != "local":
        forwarded_user = request.headers.get(settings.auth_forwarded_user_header)
        if forwarded_user:
            if not settings.trust_external_auth_headers:
                raise unauthorized("External auth headers are disabled unless TRUST_EXTERNAL_AUTH_HEADERS=true")
            forwarded_admin = request.headers.get("X-Authenticated-Admin", "").lower() in {"1", "true", "yes"}
            if admin and not forwarded_admin:
                token = token_from_request(request)
                if token and settings.alpha_admin_token and secrets.compare_digest(token, settings.alpha_admin_token):
                    return UserPrincipal(user_id=forwarded_user, auth_mode=mode, is_admin=True)
                raise unauthorized("Admin authentication required")
            return UserPrincipal(user_id=forwarded_user, auth_mode=mode, is_admin=forwarded_admin)

    token = token_from_request(request)
    if token and settings.alpha_admin_token and secrets.compare_digest(token, settings.alpha_admin_token):
        return UserPrincipal(user_id="admin", auth_mode=mode, is_admin=True)

    if not admin:
        for user_id, allowed in settings.parsed_alpha_user_tokens.items():
            if token and secrets.compare_digest(token, allowed):
                return UserPrincipal(user_id=user_id, auth_mode=mode, is_admin=False)

        if token and settings.alpha_shared_password and secrets.compare_digest(token, settings.alpha_shared_password):
            return UserPrincipal(user_id="alpha-user", auth_mode=mode, is_admin=False)

    session_cookie = request.cookies.get(ALPHA_SESSION_COOKIE_NAME)
    if session_cookie:
        principal = principal_from_alpha_session_cookie(session_cookie, settings.alpha_session_secret)
        if principal is not None:
            if admin and not principal.is_admin:
                raise unauthorized("Admin authentication required")
            return principal
        raise unauthorized("Invalid alpha session")

    if admin:
        raise unauthorized("Admin authentication required")

    if mode != "local":
        detail = f"{settings.auth_provider_name} did not authenticate this request"
    elif not any([settings.alpha_shared_password, settings.alpha_admin_token, settings.alpha_session_secret, settings.parsed_alpha_user_tokens]):
        detail = "Alpha authentication is not configured"
    else:
        detail = "Authentication required"
    raise unauthorized(detail)


def unauthorized(detail: str) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def token_from_request(request: Request) -> str | None:
    explicit = request.headers.get("X-Alpha-Token")
    if explicit:
        return explicit.strip()
    authorization = request.headers.get("Authorization")
    scheme, param = get_authorization_scheme_param(authorization)
    if not scheme or not param:
        return None
    if scheme.lower() == "bearer":
        return param.strip()
    if scheme.lower() == "basic":
        try:
            decoded = base64.b64decode(param).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return None
        _username, separator, password = decoded.partition(":")
        return password if separator else None
    return None


def create_alpha_session_cookie(
    *,
    user_id: str,
    is_admin: bool,
    secret: str,
    now: int | None = None,
    ttl_seconds: int = ALPHA_SESSION_TTL_SECONDS,
) -> str:
    issued_at = int(now if now is not None else time.time())
    payload = {
        "user_id": user_id,
        "is_admin": bool(is_admin),
        "iat": issued_at,
        "exp": issued_at + ttl_seconds,
    }
    payload_segment = base64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = sign_alpha_session_payload(payload_segment, secret)
    return f"{ALPHA_SESSION_VERSION}.{payload_segment}.{signature}"


def principal_from_alpha_session_cookie(cookie_value: str, secret: str | None) -> UserPrincipal | None:
    if not secret:
        return None
    parts = cookie_value.split(".")
    if len(parts) != 3:
        return None
    version, payload_segment, provided_signature = parts
    if version != ALPHA_SESSION_VERSION or not payload_segment or not provided_signature:
        return None
    expected_signature = sign_alpha_session_payload(payload_segment, secret)
    if not hmac.compare_digest(provided_signature, expected_signature):
        return None
    try:
        payload = json.loads(base64url_decode(payload_segment).decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not valid_session_payload(payload):
        return None
    if int(payload["exp"]) < int(time.time()):
        return None
    return UserPrincipal(
        user_id=str(payload["user_id"]),
        auth_mode="session",
        is_admin=bool(payload["is_admin"]),
    )


def valid_session_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    user_id = payload.get("user_id")
    is_admin = payload.get("is_admin")
    issued_at = payload.get("iat")
    expires_at = payload.get("exp")
    return (
        isinstance(user_id, str)
        and bool(user_id.strip())
        and isinstance(is_admin, bool)
        and isinstance(issued_at, int)
        and isinstance(expires_at, int)
        and expires_at >= issued_at
    )


def sign_alpha_session_payload(payload_segment: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_segment.encode("utf-8"), hashlib.sha256).digest()
    return base64url_encode(digest)


def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


class AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        clear_current_principal()
        try:
            return await call_next(request)
        finally:
            clear_current_principal()


def public_alpha_auth_info() -> dict[str, object]:
    settings = get_settings()
    mode = settings.auth_provider_mode.lower().strip()
    return {
        "auth_enabled": settings.alpha_auth_enabled or settings.is_production,
        "auth_provider_mode": settings.auth_provider_mode,
        "auth_provider_name": settings.auth_provider_name,
        "dev_admin_enabled": settings.enable_dev_admin and not settings.is_production,
        "production_requires_external_auth": settings.is_production and mode != "external",
        "external_auth_hook_configured": mode == "external"
        and (
            bool(settings.auth_jwks_url)
            or (settings.trust_external_auth_headers and bool(settings.auth_forwarded_user_header))
        ),
    }
