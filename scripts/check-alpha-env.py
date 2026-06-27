#!/usr/bin/env python3
"""Validate a controlled private-alpha environment."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


PLACEHOLDER_PATTERNS = (
    "change-me",
    "changeme",
    "replace-with",
    "example",
    "password",
    "secret",
    "token",
    "minioadmin",
)


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def merged_env(env_file: Path) -> dict[str, str]:
    values = load_env_file(env_file)
    values.update({key: value for key, value in os.environ.items() if value is not None})
    return values


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def empty(value: str | None) -> bool:
    return not str(value or "").strip()


def looks_placeholder(value: str | None) -> bool:
    lowered = str(value or "").strip().lower()
    if not lowered:
        return False
    return any(pattern in lowered for pattern in PLACEHOLDER_PATTERNS)


def token_pairs(value: str | None) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in str(value or "").split(","):
        user, separator, token = item.partition(":")
        if separator and user.strip() and token.strip():
            pairs.append((user.strip(), token.strip()))
    return pairs


def validate(values: dict[str, str]) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []

    app_env = values.get("APP_ENV", "").strip().lower()
    if app_env not in {"alpha", "production"}:
        failures.append("APP_ENV must be alpha or production.")

    if not truthy(values.get("ALPHA_AUTH_ENABLED")):
        failures.append("ALPHA_AUTH_ENABLED must be true.")

    session_secret = values.get("ALPHA_SESSION_SECRET", "")
    if len(session_secret) < 32:
        failures.append("ALPHA_SESSION_SECRET must be at least 32 characters.")
    if looks_placeholder(session_secret):
        failures.append("ALPHA_SESSION_SECRET appears to be a placeholder.")

    auth_mode = values.get("AUTH_PROVIDER_MODE", "local").strip().lower()
    external_auth = auth_mode == "external"
    trust_external = truthy(values.get("TRUST_EXTERNAL_AUTH_HEADERS"))
    forwarded_header = values.get("AUTH_FORWARDED_USER_HEADER", "").strip()
    jwks_url = values.get("AUTH_JWKS_URL", "").strip()
    trusted_forwarded_auth = external_auth and trust_external and bool(forwarded_header)
    pairs = token_pairs(values.get("ALPHA_USER_TOKENS"))
    if not pairs and not trusted_forwarded_auth:
        failures.append(
            "ALPHA_USER_TOKENS is required for multi-user private alpha unless trusted "
            "forwarded headers are deliberately configured."
        )
    for user_id, token in pairs:
        if len(token) < 24:
            failures.append(f"Token for {user_id} is too short; use scripts/create-alpha-token.py.")
        if looks_placeholder(token):
            failures.append(f"Token for {user_id} appears to be a placeholder.")

    shared_password = values.get("ALPHA_SHARED_PASSWORD", "")
    if not empty(shared_password):
        warnings.append("ALPHA_SHARED_PASSWORD is shared-account only and does not isolate testers.")
        if looks_placeholder(shared_password):
            failures.append("ALPHA_SHARED_PASSWORD appears to be a placeholder.")

    admin_token = values.get("ALPHA_ADMIN_TOKEN", "")
    if len(admin_token) < 24:
        failures.append("ALPHA_ADMIN_TOKEN must be set to a strong random value.")
    if looks_placeholder(admin_token):
        failures.append("ALPHA_ADMIN_TOKEN appears to be a placeholder.")

    if truthy(values.get("ENABLE_DEV_ADMIN")):
        failures.append("ENABLE_DEV_ADMIN must be false for alpha/production.")
    if truthy(values.get("NEXT_PUBLIC_ENABLE_DEV_ADMIN")):
        failures.append("NEXT_PUBLIC_ENABLE_DEV_ADMIN must be false for alpha/production.")

    if trust_external and not external_auth:
        failures.append("TRUST_EXTERNAL_AUTH_HEADERS=true is only allowed with AUTH_PROVIDER_MODE=external.")
    if external_auth and trust_external:
        warnings.append(
            "TRUST_EXTERNAL_AUTH_HEADERS=true requires a trusted proxy that strips spoofed "
            "identity/admin headers before forwarding requests."
        )
        if not forwarded_header:
            failures.append("AUTH_FORWARDED_USER_HEADER is required when TRUST_EXTERNAL_AUTH_HEADERS=true.")
        if not pairs:
            warnings.append(
                "Controlled private alpha should use ALPHA_USER_TOKENS by default unless "
                "trusted forwarded headers are intentionally deployed."
            )
    if jwks_url:
        message = "AUTH_JWKS_URL is configured, but JWKS bearer-token validation is not implemented yet."
        if trusted_forwarded_auth:
            warnings.append(message)
        else:
            failures.append(message)
    if external_auth and not pairs and not trusted_forwarded_auth:
        failures.append(
            "External auth is only implemented through trusted forwarded headers right now; "
            "JWKS bearer-token validation is reserved for future work."
        )

    if truthy(values.get("S3_PUBLIC_READ_ENABLED")):
        failures.append("S3_PUBLIC_READ_ENABLED must be false.")
    if values.get("ASSET_DOWNLOAD_MODE", "proxy").strip().lower() != "proxy":
        failures.append("ASSET_DOWNLOAD_MODE must be proxy.")

    for key in ("DATABASE_URL", "REDIS_URL", "S3_ENDPOINT_URL", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "S3_BUCKET_NAME"):
        if empty(values.get(key)):
            failures.append(f"{key} is required.")
    for key in ("S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"):
        if looks_placeholder(values.get(key)):
            failures.append(f"{key} appears to be a placeholder.")

    if values.get("OPENAI_API_KEY") and looks_placeholder(values.get("OPENAI_API_KEY")):
        warnings.append("OPENAI_API_KEY looks like placeholder text; mock mode does not require it.")
    if not values.get("OPENAI_API_KEY") and not values.get("COMFYUI_BASE_URL"):
        warnings.append("No real image provider is configured; alpha will rely on deterministic mock providers.")

    return failures, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate private-alpha launch environment variables.")
    parser.add_argument("--env-file", default=".env", help="Env file to read before process environment. Defaults to .env.")
    args = parser.parse_args()

    values = merged_env(Path(args.env_file))
    failures, warnings = validate(values)

    for warning in warnings:
        print(f"WARN: {warning}")
    for failure in failures:
        print(f"FAIL: {failure}")
    if failures:
        print(f"Alpha environment check failed with {len(failures)} blocking issue(s).")
        return 2
    print("Alpha environment check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
