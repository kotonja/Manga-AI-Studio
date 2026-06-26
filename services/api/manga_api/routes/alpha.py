from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis import Redis
from sqlalchemy import text
from sqlmodel import Session

from manga_api.access import require_page_access, require_panel_access, require_project_access
from manga_api.auth import public_alpha_auth_info, require_admin_access, require_alpha_user, resolve_alpha_user
from manga_api.config import get_settings
from manga_api.db import get_session
from manga_api.provider_registry import list_provider_summaries
from manga_api.queue import make_celery_client
from manga_api.models import FeedbackItem
from manga_api.schemas import AlphaOnboardingInfo, AlphaReadinessCheck, AlphaReadinessResult, FeedbackCreate, FeedbackRead
from manga_api.storage import ObjectStorage, get_object_storage

router = APIRouter(tags=["alpha"])


@router.get("/alpha/onboarding", response_model=AlphaOnboardingInfo)
def get_alpha_onboarding() -> AlphaOnboardingInfo:
    return AlphaOnboardingInfo(
        auth=public_alpha_auth_info(),
        welcome_title="Welcome to Manga AI Studio Alpha",
        welcome_message=(
            "This private alpha focuses on the complete manga workflow: premise to story, pages, "
            "render drafts, lettering, QA, provenance, and exports."
        ),
        first_demo_premise="A lonely swordsman protects a ghost child in a ruined city.",
        provider_modes=[
            {
                "id": "mock",
                "name": "Mock mode",
                "description": "Deterministic local placeholders. No paid API calls and safest for smoke testing.",
                "cost_risk": "none",
            },
            {
                "id": "real",
                "name": "Real provider mode",
                "description": "Uses configured image/LLM providers. Dry-run first and expect external cost/latency.",
                "cost_risk": "possible",
            },
        ],
        suggested_first_steps=[
            "Run the Founder Demo once to understand the full pipeline.",
            "Create a small original project with 1-4 pages.",
            "Complete rights declaration before uploading references or exporting.",
            "Use mock providers until a real provider is explicitly configured.",
            "Submit feedback from the in-app feedback button when anything feels confusing or broken.",
        ],
        safety_rules=[
            "Only upload assets you own or are licensed to use.",
            "Do not ask the app to copy a living artist, named franchise, or exact protected style.",
            "Review every AI-assisted page before publishing or sharing externally.",
            "Keep private alpha projects non-commercial unless rights and provider terms are confirmed.",
        ],
        docs=[
            {"label": "Alpha testing guide", "href": "/docs/ALPHA_TESTING.md"},
            {"label": "Provider setup", "href": "/docs/PROVIDERS.md"},
            {"label": "Creator rights", "href": "/docs/SECURITY_CHECKLIST.md"},
        ],
    )


@router.get("/alpha/readiness", response_model=AlphaReadinessResult, dependencies=[Depends(require_admin_access)])
def get_alpha_readiness(
    session: Session = Depends(get_session),
    storage: ObjectStorage = Depends(get_object_storage),
) -> AlphaReadinessResult:
    settings = get_settings()
    checks: list[AlphaReadinessCheck] = []

    def add(name: str, check_status: str, message: str) -> None:
        checks.append(AlphaReadinessCheck(name=name, status=check_status, message=message))

    app_env = settings.app_env.lower().strip()
    add(
        "environment",
        "pass" if app_env in {"alpha", "production"} else "fail",
        "APP_ENV is set for controlled alpha/production." if app_env in {"alpha", "production"} else "APP_ENV must be alpha or production for a controlled tester launch.",
    )
    add(
        "auth enabled",
        "pass" if settings.alpha_auth_enabled else "fail",
        "ALPHA_AUTH_ENABLED is true." if settings.alpha_auth_enabled else "ALPHA_AUTH_ENABLED must be true for private alpha.",
    )
    session_secret = settings.alpha_session_secret or ""
    add(
        "session secret",
        "pass" if len(session_secret) >= 32 else "fail",
        "ALPHA_SESSION_SECRET is configured with sufficient length." if len(session_secret) >= 32 else "ALPHA_SESSION_SECRET should be at least 32 characters and must not be shared with testers.",
    )

    external_configured = settings.auth_provider_mode.lower().strip() == "external" and (
        bool(settings.auth_jwks_url) or settings.trust_external_auth_headers
    )
    has_user_tokens = bool(settings.parsed_alpha_user_tokens)
    add(
        "tester identity",
        "pass" if has_user_tokens or external_configured else "fail",
        "Per-user tester tokens or external auth are configured." if has_user_tokens or external_configured else "Configure ALPHA_USER_TOKENS for multi-user alpha or a trusted external auth provider.",
    )
    add(
        "dev admin disabled",
        "pass" if not (app_env in {"alpha", "production"} and settings.enable_dev_admin) else "fail",
        "ENABLE_DEV_ADMIN is disabled for alpha/production." if not (app_env in {"alpha", "production"} and settings.enable_dev_admin) else "ENABLE_DEV_ADMIN must be false for controlled alpha and production.",
    )
    add(
        "public storage disabled",
        "pass" if not settings.effective_s3_public_read_enabled else "fail",
        "S3_PUBLIC_READ_ENABLED is false/effectively disabled." if not settings.effective_s3_public_read_enabled else "S3_PUBLIC_READ_ENABLED must be false; assets should go through protected proxy downloads.",
    )
    add(
        "asset download mode",
        "pass" if settings.effective_asset_download_mode == "proxy" else "fail",
        "ASSET_DOWNLOAD_MODE resolves to proxy." if settings.effective_asset_download_mode == "proxy" else "ASSET_DOWNLOAD_MODE must resolve to proxy for private alpha.",
    )

    try:
        session.execute(text("SELECT 1")).scalar_one()
        add("database", "pass", "Database responded to SELECT 1.")
    except Exception as exc:
        add("database", "fail", f"Database check failed: {type(exc).__name__}.")

    try:
        Redis.from_url(settings.redis_url, socket_timeout=2).ping()
        add("redis", "pass", "Redis responded to ping.")
    except Exception as exc:
        add("redis", "fail", f"Redis check failed: {type(exc).__name__}.")

    try:
        storage.check()
        add("storage", "pass", "Object storage responded to check.")
    except Exception as exc:
        add("storage", "fail", f"Object storage check failed: {type(exc).__name__}.")

    try:
        worker_response = make_celery_client().control.inspect(timeout=1).ping()
        add(
            "worker",
            "pass" if worker_response else "fail",
            f"Worker responded: {', '.join(sorted(worker_response.keys()))}." if worker_response else "No Celery worker responded to ping.",
        )
    except Exception as exc:
        add("worker", "fail", f"Worker check failed: {type(exc).__name__}.")

    try:
        version = session.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
        add(
            "migrations",
            "pass" if version else "warn",
            f"Alembic reports current revision {version}." if version else "Alembic version table is empty; verify migrations before launch.",
        )
    except Exception:
        add("migrations", "warn", "Could not read alembic_version; test databases may not include migration metadata.")

    providers = list_provider_summaries()
    real_configured = [provider["name"] for provider in providers if provider["name"] != "mock" and provider["configured"]]
    add(
        "real providers",
        "warn" if not real_configured else "pass",
        f"Configured real providers: {', '.join(real_configured)}." if real_configured else "No real image providers configured; alpha can still run in deterministic mock mode.",
    )
    mock = next((provider for provider in providers if provider["name"] == "mock"), None)
    add(
        "mock provider",
        "pass" if mock and mock["configured"] else "fail",
        "Mock provider is available for no-cost deterministic testing." if mock and mock["configured"] else "Mock provider is unavailable; local demo and tests need it.",
    )

    return AlphaReadinessResult(
        ready=all(check.status != "fail" for check in checks),
        checks=checks,
    )


@router.post("/feedback", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    payload: FeedbackCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> FeedbackItem:
    principal = None
    if payload.project_id is not None or payload.page_id is not None or payload.panel_id is not None:
        principal = resolve_alpha_user(request)
        if payload.project_id is not None:
            require_project_access(session, payload.project_id, principal)
        if payload.page_id is not None:
            require_page_access(session, payload.page_id, principal)
        if payload.panel_id is not None:
            require_panel_access(session, payload.panel_id, principal)
    else:
        try:
            principal = resolve_alpha_user(request)
        except HTTPException:
            principal = None
    item = FeedbackItem(
        project_id=payload.project_id,
        page_id=payload.page_id,
        panel_id=payload.panel_id,
        category=payload.category,
        severity="blocker" if payload.severity == "blocking" else payload.severity,
        title=payload.title.strip(),
        description=payload.description.strip(),
        contact_email=payload.contact_email,
        created_by=principal.user_id if principal else None,
        browser_info=safe_json(payload.browser_info),
        context=safe_json(payload.context),
        diagnostic_info=safe_json(payload.diagnostic_info),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def safe_json(value: dict) -> dict:
    scrubbed = dict(value or {})
    for key in list(scrubbed):
        lower = str(key).lower()
        if "secret" in lower or "token" in lower or "password" in lower or "key" in lower:
            scrubbed[key] = "[redacted]"
    return scrubbed
