from __future__ import annotations

import base64
import binascii
import secrets
from dataclasses import dataclass

from fastapi import HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param

from manga_api.config import get_settings


@dataclass(frozen=True)
class AlphaPrincipal:
    user_id: str
    auth_mode: str
    is_admin: bool = False


def require_alpha_user(request: Request) -> AlphaPrincipal:
    settings = get_settings()
    if not settings.alpha_auth_enabled and not settings.is_production:
        return AlphaPrincipal(user_id="local-dev", auth_mode="disabled")
    return authenticate_request(request, admin=False)


def require_sensitive_access(request: Request) -> AlphaPrincipal:
    settings = get_settings()
    if not settings.alpha_auth_enabled and not settings.is_production:
        return AlphaPrincipal(user_id="local-dev", auth_mode="disabled")
    return authenticate_request(request, admin=False)


def require_admin_access(request: Request) -> AlphaPrincipal:
    settings = get_settings()
    if settings.enable_dev_admin and not settings.is_production:
        return AlphaPrincipal(user_id="dev-admin", auth_mode="dev-admin", is_admin=True)
    if not settings.alpha_auth_enabled and not settings.is_production:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin routes are disabled")
    return authenticate_request(request, admin=True)


def authenticate_request(request: Request, *, admin: bool) -> AlphaPrincipal:
    settings = get_settings()
    mode = settings.auth_provider_mode.lower().strip()

    if mode != "local":
        forwarded_user = request.headers.get(settings.auth_forwarded_user_header)
        if forwarded_user:
            return AlphaPrincipal(user_id=forwarded_user, auth_mode=mode, is_admin=admin)

    token = token_from_request(request)
    allowed_tokens = []
    if admin and settings.alpha_admin_token:
        allowed_tokens.append(settings.alpha_admin_token)
    if settings.alpha_shared_password:
        allowed_tokens.append(settings.alpha_shared_password)
    if settings.alpha_admin_token and not allowed_tokens:
        allowed_tokens.append(settings.alpha_admin_token)

    if token and any(secrets.compare_digest(token, allowed) for allowed in allowed_tokens if allowed):
        return AlphaPrincipal(user_id="alpha-user", auth_mode=mode, is_admin=admin)

    if mode != "local":
        detail = f"{settings.auth_provider_name} did not authenticate this request"
    elif not allowed_tokens:
        detail = "Alpha authentication is not configured"
    else:
        detail = "Authentication required"
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
