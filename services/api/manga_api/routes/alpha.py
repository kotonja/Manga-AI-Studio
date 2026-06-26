from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlmodel import Session

from manga_api.auth import public_alpha_auth_info, require_alpha_user
from manga_api.db import get_session
from manga_api.models import FeedbackItem
from manga_api.schemas import AlphaOnboardingInfo, FeedbackCreate, FeedbackRead

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


@router.post("/feedback", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    payload: FeedbackCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> FeedbackItem:
    principal = None
    try:
        principal = require_alpha_user(request)
    except Exception:
        principal = None
    item = FeedbackItem(
        project_id=payload.project_id,
        page_id=payload.page_id,
        panel_id=payload.panel_id,
        category=payload.category,
        severity=payload.severity,
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
