from __future__ import annotations

import base64
import binascii
from contextvars import ContextVar
import secrets
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param

from manga_api.config import get_settings


@dataclass(frozen=True)
class UserPrincipal:
    user_id: str
    auth_mode: str
    is_admin: bool = False


AlphaPrincipal = UserPrincipal
_current_principal: ContextVar[UserPrincipal | None] = ContextVar("current_user_principal", default=None)


def set_current_principal(principal: UserPrincipal) -> UserPrincipal:
    _current_principal.set(principal)
    return principal


def current_principal() -> UserPrincipal | None:
    return _current_principal.get()


def resolve_alpha_user(request: Request) -> UserPrincipal:
    settings = get_settings()
    if settings.is_local_unlocked:
        return UserPrincipal(user_id="local-dev", auth_mode="disabled")
    return authenticate_request(request, admin=False)


async def require_alpha_user(request: Request) -> UserPrincipal:
    return set_current_principal(resolve_alpha_user(request))


def get_current_principal(principal: UserPrincipal = Depends(require_alpha_user)) -> UserPrincipal:
    return principal


async def require_sensitive_access(request: Request) -> UserPrincipal:
    settings = get_settings()
    if settings.is_local_unlocked:
        return set_current_principal(UserPrincipal(user_id="local-dev", auth_mode="disabled"))
    return set_current_principal(authenticate_request(request, admin=False))


async def require_admin_access(request: Request) -> UserPrincipal:
    settings = get_settings()
    if settings.enable_dev_admin and not settings.is_production:
        return set_current_principal(UserPrincipal(user_id="dev-admin", auth_mode="dev-admin", is_admin=True))
    if settings.is_local_unlocked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin routes are disabled")
    return set_current_principal(authenticate_request(request, admin=True))


def authenticate_request(request: Request, *, admin: bool) -> UserPrincipal:
    settings = get_settings()
    mode = settings.auth_provider_mode.lower().strip()

    if mode != "local":
        forwarded_user = request.headers.get(settings.auth_forwarded_user_header)
        if forwarded_user:
            forwarded_admin = request.headers.get("X-Authenticated-Admin", "").lower() in {"1", "true", "yes"}
            if admin and not forwarded_admin:
                token = token_from_request(request)
                if token and settings.alpha_admin_token and secrets.compare_digest(token, settings.alpha_admin_token):
                    return UserPrincipal(user_id=forwarded_user, auth_mode=mode, is_admin=True)
                raise unauthorized("Admin authentication required")
            return UserPrincipal(user_id=forwarded_user, auth_mode=mode, is_admin=forwarded_admin)

    token = token_from_request(request)
    if admin:
        if token and settings.alpha_admin_token and secrets.compare_digest(token, settings.alpha_admin_token):
            return UserPrincipal(user_id="admin", auth_mode=mode, is_admin=True)
        raise unauthorized("Admin authentication required")

    for user_id, allowed in settings.parsed_alpha_user_tokens.items():
        if token and secrets.compare_digest(token, allowed):
            return UserPrincipal(user_id=user_id, auth_mode=mode, is_admin=False)

    if token and settings.alpha_admin_token and secrets.compare_digest(token, settings.alpha_admin_token):
        return UserPrincipal(user_id="admin", auth_mode=mode, is_admin=True)

    if token and settings.alpha_shared_password and secrets.compare_digest(token, settings.alpha_shared_password):
        return UserPrincipal(user_id="alpha-user", auth_mode=mode, is_admin=False)

    session_cookie = request.cookies.get("manga_alpha_session")
    if session_cookie and settings.alpha_session_secret and secrets.compare_digest(session_cookie, settings.alpha_session_secret):
        return UserPrincipal(user_id="alpha-user", auth_mode="session", is_admin=False)

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


def public_alpha_auth_info() -> dict[str, object]:
    settings = get_settings()
    mode = settings.auth_provider_mode.lower().strip()
    return {
        "auth_enabled": settings.alpha_auth_enabled or settings.is_production,
        "auth_provider_mode": settings.auth_provider_mode,
        "auth_provider_name": settings.auth_provider_name,
        "dev_admin_enabled": settings.enable_dev_admin and not settings.is_production,
        "production_requires_external_auth": settings.is_production and mode != "external",
        "external_auth_hook_configured": mode == "external" and bool(settings.auth_forwarded_user_header or settings.auth_jwks_url),
    }
