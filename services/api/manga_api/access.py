from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from manga_api.auth import UserPrincipal, current_principal
from manga_api.config import get_settings
from manga_api.models import (
    Asset,
    Bubble,
    CharacterCard,
    CharacterReferenceAsset,
    CharacterState,
    Chapter,
    CommandHistory,
    GenerationFeedback,
    GenerationJob,
    KeyObject,
    LayoutTemplate,
    Location,
    Page,
    PagePlan,
    Panel,
    PanelPlan,
    Project,
    ProjectExport,
    QAReport,
    Render,
    RightsDeclaration,
    SFXElement,
    Scene,
    StoryBible,
    StyleBible,
    StyleSampleAsset,
)


LOCAL_DEV_USER_ID = "local-dev"


class AccessDeniedError(HTTPException):
    pass


def get_effective_principal(principal: UserPrincipal | None = None) -> UserPrincipal:
    if principal is not None:
        return principal
    existing = current_principal()
    if existing is not None:
        return existing
    settings = get_settings()
    if settings.is_local_unlocked:
        return UserPrincipal(user_id=LOCAL_DEV_USER_ID, auth_mode="disabled")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_project_access(
    session: Session,
    project_id: uuid.UUID | str,
    principal: UserPrincipal | None = None,
) -> Project:
    project = session.get(Project, uuid.UUID(str(project_id)))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return require_project_row_access(session, project, principal)


def require_project_row_access(
    session: Session,
    project: Project,
    principal: UserPrincipal | None = None,
) -> Project:
    actor = get_effective_principal(principal)
    if not getattr(project, "owner_user_id", None):
        project.owner_user_id = LOCAL_DEV_USER_ID
        session.add(project)
        session.flush()
    if actor.is_admin or project.owner_user_id == actor.user_id:
        return project
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")


def project_filter_for_principal(principal: UserPrincipal | None = None):
    actor = get_effective_principal(principal)
    if actor.is_admin:
        return None
    return Project.owner_user_id == actor.user_id


def require_page_access(session: Session, page_id: uuid.UUID | str, principal: UserPrincipal | None = None) -> Page:
    page = session.get(Page, uuid.UUID(str(page_id)))
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    require_project_access(session, page.project_id, principal)
    return page


def require_panel_access(session: Session, panel_id: uuid.UUID | str, principal: UserPrincipal | None = None) -> tuple[Panel, Page]:
    panel = session.get(Panel, uuid.UUID(str(panel_id)))
    if panel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Panel not found")
    page = require_page_access(session, panel.page_id, principal)
    return panel, page


def require_bubble_access(session: Session, bubble_id: uuid.UUID | str, principal: UserPrincipal | None = None) -> Bubble:
    bubble = session.get(Bubble, uuid.UUID(str(bubble_id)))
    if bubble is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bubble not found")
    require_panel_access(session, bubble.panel_id, principal)
    return bubble


def require_sfx_access(session: Session, sfx_id: uuid.UUID | str, principal: UserPrincipal | None = None) -> SFXElement:
    element = session.get(SFXElement, uuid.UUID(str(sfx_id)))
    if element is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SFX element not found")
    require_page_access(session, element.page_id, principal)
    return element


def require_job_access(session: Session, job_id: uuid.UUID | str, principal: UserPrincipal | None = None) -> GenerationJob:
    job = session.get(GenerationJob, uuid.UUID(str(job_id)))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.project_id is not None:
        require_project_access(session, job.project_id, principal)
    elif job.page_id is not None:
        require_page_access(session, job.page_id, principal)
    elif job.panel_id is not None:
        require_panel_access(session, job.panel_id, principal)
    elif not get_effective_principal(principal).is_admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def require_export_access(session: Session, export_id: uuid.UUID | str, principal: UserPrincipal | None = None) -> ProjectExport:
    export = session.get(ProjectExport, uuid.UUID(str(export_id)))
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    require_project_access(session, export.project_id, principal)
    return export


def require_asset_access(session: Session, asset_id: uuid.UUID | str, principal: UserPrincipal | None = None) -> Asset:
    asset = session.get(Asset, uuid.UUID(str(asset_id)))
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    if asset.project_id is None:
        if get_effective_principal(principal).is_admin:
            return asset
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    require_project_access(session, asset.project_id, principal)
    return asset


def require_chapter_access(session: Session, chapter_id: uuid.UUID | str, principal: UserPrincipal | None = None) -> Chapter:
    chapter = session.get(Chapter, uuid.UUID(str(chapter_id)))
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    require_project_access(session, chapter.project_id, principal)
    return chapter


def require_scene_access(session: Session, scene_id: uuid.UUID | str, principal: UserPrincipal | None = None) -> Scene:
    scene = session.get(Scene, uuid.UUID(str(scene_id)))
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")
    require_chapter_access(session, scene.chapter_id, principal)
    return scene


def require_character_card_access(session: Session, character_id: uuid.UUID | str, principal: UserPrincipal | None = None) -> CharacterCard:
    card = session.get(CharacterCard, uuid.UUID(str(character_id)))
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character card not found")
    require_project_access(session, card.project_id, principal)
    return card


def require_style_bible_access(session: Session, style_bible_id: uuid.UUID | str, principal: UserPrincipal | None = None) -> StyleBible:
    style_bible = session.get(StyleBible, uuid.UUID(str(style_bible_id)))
    if style_bible is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Style bible not found")
    require_project_access(session, style_bible.project_id, principal)
    return style_bible


def require_layout_template_access(session: Session, template_id: uuid.UUID | str, principal: UserPrincipal | None = None) -> LayoutTemplate:
    template = session.get(LayoutTemplate, uuid.UUID(str(template_id)))
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layout template not found")
    require_project_access(session, template.project_id, principal)
    return template


def require_qa_report_access(session: Session, report_id: uuid.UUID | str, principal: UserPrincipal | None = None) -> QAReport:
    report = session.get(QAReport, uuid.UUID(str(report_id)))
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA report not found")
    if report.page_id is not None:
        require_page_access(session, report.page_id, principal)
    elif report.panel_id is not None:
        require_panel_access(session, report.panel_id, principal)
    elif report.target_type == "project":
        require_project_access(session, report.target_id, principal)
    elif report.target_type == "page":
        require_page_access(session, report.target_id, principal)
    elif report.target_type == "panel":
        require_panel_access(session, report.target_id, principal)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA report not found")
    return report


def require_render_access(session: Session, render_id: uuid.UUID | str, principal: UserPrincipal | None = None) -> Render:
    render = session.get(Render, uuid.UUID(str(render_id)))
    if render is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Render not found")
    require_panel_access(session, render.panel_id, principal)
    return render


def project_id_for_feedback_target(session: Session, target_type: str, target_id: uuid.UUID) -> uuid.UUID | None:
    normalized = target_type.lower().strip()
    if normalized in {"page", "page_layout"}:
        page = session.get(Page, target_id)
        return page.project_id if page else None
    if normalized in {"panel", "panel_render"}:
        panel = session.get(Panel, target_id)
        if panel is None:
            return None
        page = session.get(Page, panel.page_id)
        return page.project_id if page else None
    if normalized == "export":
        export = session.get(ProjectExport, target_id)
        return export.project_id if export else None
    if normalized == "story":
        story = session.get(StoryBible, target_id)
        return story.project_id if story else None
    if normalized == "character":
        character = session.get(CharacterCard, target_id)
        return character.project_id if character else None
    if normalized == "style":
        style = session.get(StyleBible, target_id)
        return style.project_id if style else None
    return None


def require_feedback_target_access(
    session: Session,
    *,
    target_type: str,
    target_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    principal: UserPrincipal | None = None,
) -> Project | None:
    resolved_project_id = project_id or project_id_for_feedback_target(session, target_type, target_id)
    if resolved_project_id is None:
        return None
    return require_project_access(session, resolved_project_id, principal)


def require_version_project_access(session: Session, version: Any, principal: UserPrincipal | None = None) -> None:
    project_id = getattr(version, "project_id", None)
    if project_id is not None:
        require_project_access(session, project_id, principal)

