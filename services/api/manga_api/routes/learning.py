from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from manga_api.access import require_feedback_target_access, require_project_access
from manga_api.auth import require_alpha_user
from manga_api.db import get_session
from manga_api.models import (
    CharacterCard,
    ExportRating,
    GenerationFeedback,
    Page,
    PageRating,
    Panel,
    PanelRating,
    Project,
    ProjectExport,
    StoryBible,
    StyleBible,
    UserCorrection,
)
from manga_api.schemas import (
    GenerationFeedbackCreate,
    GenerationFeedbackRead,
    LearningFeedbackOptions,
    LearningIssueOption,
    ProjectDataControlsRead,
    ProjectDataControlsUpdate,
)

router = APIRouter(tags=["product-learning"], dependencies=[Depends(require_alpha_user)])

ISSUE_TAGS = [
    "wrong character",
    "bad hands",
    "bad face",
    "confusing layout",
    "unreadable text",
    "inconsistent style",
    "weak story",
    "wrong tone",
    "export problem",
    "other",
]


@router.get("/learning/feedback-options", response_model=LearningFeedbackOptions)
def get_learning_feedback_options() -> LearningFeedbackOptions:
    return LearningFeedbackOptions(
        issue_tags=[LearningIssueOption(id=tag, label=tag.title()) for tag in ISSUE_TAGS],
        default_allow_use_for_product_improvement=False,
        collection_explanation=(
            "Ratings and corrections are stored for your project. Product-improvement use is off by default "
            "and only enabled when both the project and this feedback item opt in."
        ),
    )


@router.post("/learning/feedback", response_model=GenerationFeedbackRead, status_code=status.HTTP_201_CREATED)
def create_generation_feedback(
    payload: GenerationFeedbackCreate,
    session: Session = Depends(get_session),
) -> GenerationFeedback:
    require_feedback_target_access(
        session,
        target_type=payload.target_type,
        target_id=payload.target_id,
        project_id=payload.project_id,
    )
    project = resolve_feedback_project(session, payload)
    allow_improvement = bool(project and project.allow_product_improvement and payload.allow_use_for_product_improvement)
    feedback = GenerationFeedback(
        project_id=project.id if project else payload.project_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        rating=payload.rating,
        issue_type=payload.issue_type,
        comment=safe_text(payload.comment),
        user_correction=safe_text(payload.user_correction),
        before_snapshot_id=payload.before_snapshot_id,
        after_snapshot_id=payload.after_snapshot_id,
        allow_use_for_product_improvement=allow_improvement,
        metadata_json=safe_json(payload.metadata_json),
    )
    session.add(feedback)
    session.flush()
    create_specialized_rating(session, project, feedback)
    if feedback.user_correction.strip():
        session.add(
            UserCorrection(
                project_id=feedback.project_id,
                feedback_id=feedback.id,
                target_type=feedback.target_type,
                target_id=feedback.target_id,
                correction_text=feedback.user_correction,
                before_snapshot_id=feedback.before_snapshot_id,
                after_snapshot_id=feedback.after_snapshot_id,
                allow_use_for_product_improvement=allow_improvement,
                metadata_json={"issue_type": feedback.issue_type},
            )
        )
    session.commit()
    session.refresh(feedback)
    return feedback


@router.get("/projects/{project_id}/data-controls", response_model=ProjectDataControlsRead)
def get_project_data_controls(project_id: uuid.UUID, session: Session = Depends(get_session)) -> ProjectDataControlsRead:
    project = require_project(session, project_id)
    return data_controls_read(project)


@router.put("/projects/{project_id}/data-controls", response_model=ProjectDataControlsRead)
def update_project_data_controls(
    project_id: uuid.UUID,
    payload: ProjectDataControlsUpdate,
    session: Session = Depends(get_session),
) -> ProjectDataControlsRead:
    project = require_project(session, project_id)
    project.allow_training = payload.allow_training
    project.allow_product_improvement = payload.allow_product_improvement
    project.data_collection_notes = payload.data_collection_notes
    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    session.commit()
    session.refresh(project)
    return data_controls_read(project)


def resolve_feedback_project(session: Session, payload: GenerationFeedbackCreate) -> Project | None:
    if payload.project_id is not None:
        project = session.get(Project, payload.project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return project

    target_type = payload.target_type.lower().strip()
    if target_type in {"page", "page_layout"}:
        page = session.get(Page, payload.target_id)
        return require_project(session, page.project_id) if page else missing_target("Page")
    if target_type in {"panel", "panel_render"}:
        panel = session.get(Panel, payload.target_id)
        if panel is None:
            return missing_target("Panel")
        page = session.get(Page, panel.page_id)
        return require_project(session, page.project_id) if page else missing_target("Page")
    if target_type == "export":
        export = session.get(ProjectExport, payload.target_id)
        return require_project(session, export.project_id) if export else missing_target("Export")
    if target_type == "story":
        story = session.get(StoryBible, payload.target_id)
        return require_project(session, story.project_id) if story else missing_target("Story bible")
    if target_type == "character":
        character = session.get(CharacterCard, payload.target_id)
        return require_project(session, character.project_id) if character else missing_target("Character")
    if target_type == "style":
        style = session.get(StyleBible, payload.target_id)
        return require_project(session, style.project_id) if style else missing_target("Style bible")
    return None


def create_specialized_rating(session: Session, project: Project | None, feedback: GenerationFeedback) -> None:
    if project is None:
        return
    target_type = feedback.target_type.lower().strip()
    if target_type in {"page", "page_layout"}:
        session.add(
            PageRating(
                project_id=project.id,
                page_id=feedback.target_id,
                feedback_id=feedback.id,
                rating=feedback.rating,
                issue_type=feedback.issue_type,
                comment=feedback.comment,
                allow_use_for_product_improvement=feedback.allow_use_for_product_improvement,
            )
        )
    elif target_type in {"panel", "panel_render"}:
        session.add(
            PanelRating(
                project_id=project.id,
                panel_id=feedback.target_id,
                feedback_id=feedback.id,
                rating=feedback.rating,
                issue_type=feedback.issue_type,
                comment=feedback.comment,
                allow_use_for_product_improvement=feedback.allow_use_for_product_improvement,
            )
        )
    elif target_type == "export":
        session.add(
            ExportRating(
                project_id=project.id,
                export_id=feedback.target_id,
                feedback_id=feedback.id,
                rating=feedback.rating,
                issue_type=feedback.issue_type,
                comment=feedback.comment,
                allow_use_for_product_improvement=feedback.allow_use_for_product_improvement,
            )
        )


def require_project(session: Session, project_id: uuid.UUID) -> Project:
    return require_project_access(session, project_id)


def missing_target(label: str):
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")


def data_controls_read(project: Project) -> ProjectDataControlsRead:
    return ProjectDataControlsRead(
        project_id=project.id,
        allow_training=project.allow_training,
        allow_product_improvement=project.allow_product_improvement,
        data_collection_notes=project.data_collection_notes,
        collected_by_default=False,
        explanation=(
            "Private by default. Operational health metrics are aggregated without prompt/story content. "
            "Ratings and corrections are used for product improvement only when this project and the individual feedback item opt in."
        ),
    )


def safe_text(value: str) -> str:
    return value.strip()


def safe_json(value: dict[str, Any]) -> dict[str, Any]:
    scrubbed = dict(value or {})
    for key in list(scrubbed):
        lower = str(key).lower()
        if "secret" in lower or "token" in lower or "password" in lower or "api_key" in lower:
            scrubbed[key] = "[redacted]"
    return scrubbed
