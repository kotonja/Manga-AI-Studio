from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from manga_api.config import get_settings
from manga_api.db import get_session
from manga_api.models import Chapter, GenerationJob, Page, Panel, Project, ProjectExport, QAReport, Render
from manga_api.schemas import (
    PageCreate,
    PageRead,
    PageWithPanels,
    PanelCreate,
    PanelRead,
    ProjectCreate,
    ProjectDetail,
    ProjectRead,
    ProjectWorkspaceSummary,
)
from manga_api.versioning import VersioningService

router = APIRouter(tags=["projects"])


def touch(row) -> None:
    row.updated_at = datetime.now(timezone.utc)


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, session: Session = Depends(get_session)) -> Project:
    settings = get_settings()
    project = Project(
        name=payload.name,
        description=payload.description,
        style_prompt=payload.style_prompt,
        allow_training=payload.allow_training if payload.allow_training is not None else settings.default_project_allow_training,
        allow_product_improvement=payload.allow_product_improvement
        if payload.allow_product_improvement is not None
        else settings.default_project_allow_product_improvement,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    VersioningService(session).create_snapshot(project, label="Project created", reason="project_create")
    session.commit()
    return project


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(session: Session = Depends(get_session)) -> list[Project]:
    return list(session.exec(select(Project).order_by(Project.created_at.desc())).all())


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: uuid.UUID, session: Session = Depends(get_session)) -> ProjectDetail:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    pages = list(
        session.exec(
            select(Page)
            .where(Page.project_id == project_id)
            .order_by(Page.page_number.asc(), Page.created_at.asc())
        ).all()
    )
    panels_by_page: dict[uuid.UUID, list[Panel]] = {page.id: [] for page in pages}
    if pages:
        panels = session.exec(
            select(Panel)
            .where(Panel.page_id.in_([page.id for page in pages]))
            .order_by(Panel.created_at.asc())
        ).all()
        for panel in panels:
            panels_by_page.setdefault(panel.page_id, []).append(panel)

    project_read = ProjectRead.model_validate(project)
    return ProjectDetail(
        **project_read.model_dump(),
        pages=[
            PageWithPanels(
                **PageRead.model_validate(page).model_dump(),
                panels=[PanelRead.model_validate(panel) for panel in panels_by_page.get(page.id, [])],
            )
            for page in pages
        ],
    )


@router.get("/projects/{project_id}/workspace-summary", response_model=ProjectWorkspaceSummary)
def get_project_workspace_summary(project_id: uuid.UUID, session: Session = Depends(get_session)) -> ProjectWorkspaceSummary:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    pages = list(session.exec(select(Page).where(Page.project_id == project_id)).all())
    page_ids = [page.id for page in pages]
    panels = (
        list(session.exec(select(Panel).where(Panel.page_id.in_(page_ids))).all())
        if page_ids
        else []
    )
    panel_ids = [panel.id for panel in panels]
    rendered_panel_ids = set(
        render.panel_id
        for render in (
            session.exec(select(Render).where(Render.panel_id.in_(panel_ids))).all()
            if panel_ids
            else []
        )
    )
    latest_project_qa = session.exec(
        select(QAReport)
        .where(QAReport.target_type == "project", QAReport.target_id == project_id)
        .order_by(QAReport.created_at.desc(), QAReport.id.desc())
    ).first()
    latest_export = session.exec(
        select(ProjectExport)
        .where(ProjectExport.project_id == project_id)
        .order_by(ProjectExport.created_at.desc(), ProjectExport.id.desc())
    ).first()
    active_chapter = session.exec(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number.asc(), Chapter.created_at.asc())
    ).first()
    active_job_count = session.exec(
        select(func.count(GenerationJob.id))
        .where(GenerationJob.project_id == project_id, GenerationJob.status.in_(["queued", "running"]))
    ).one() or 0
    rendered_count = len(rendered_panel_ids)
    panel_count = len(panels)
    return ProjectWorkspaceSummary(
        project_id=project_id,
        active_chapter_title=active_chapter.title if active_chapter else None,
        page_count=len(pages),
        panel_count=panel_count,
        rendered_panel_count=rendered_count,
        render_progress=rendered_count / panel_count if panel_count else 0,
        qa_score=latest_project_qa.overall_score if latest_project_qa else None,
        qa_blocking=bool(latest_project_qa.blocking) if latest_project_qa else False,
        export_status=latest_export.status if latest_export else None,
        active_job_count=int(active_job_count),
        status_chip=workspace_status_chip(project, active_job_count, latest_project_qa, latest_export, len(pages), rendered_count, panel_count),
    )


@router.post("/projects/{project_id}/pages", response_model=PageRead, status_code=status.HTTP_201_CREATED)
def create_page(project_id: uuid.UUID, payload: PageCreate, session: Session = Depends(get_session)) -> Page:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    page_number = payload.page_number
    if page_number is None:
        max_page_number = session.exec(
            select(func.max(Page.page_number)).where(Page.project_id == project_id)
        ).one()
        page_number = (max_page_number or 0) + 1

    page = Page(
        project_id=project_id,
        page_number=page_number,
        width=payload.width,
        height=payload.height,
    )
    touch(project)
    session.add(page)
    session.add(project)
    session.commit()
    session.refresh(page)
    versioning = VersioningService(session)
    versioning.create_snapshot(page, label=f"Page {page.page_number} created", reason="page_create")
    versioning.create_snapshot(page, entity_type="layout", label=f"Page {page.page_number} layout", reason="page_create")
    session.commit()
    return page


@router.post("/pages/{page_id}/panels", response_model=PanelRead, status_code=status.HTTP_201_CREATED)
def create_panel(page_id: uuid.UUID, payload: PanelCreate, session: Session = Depends(get_session)) -> Panel:
    page = session.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")

    reading_order = payload.reading_order
    if reading_order is None:
        max_order = session.exec(
            select(func.max(Panel.reading_order)).where(Panel.page_id == page_id)
        ).one()
        reading_order = (max_order or 0) + 1

    polygon = [
        {"x": payload.x, "y": payload.y},
        {"x": payload.x + payload.width, "y": payload.y},
        {"x": payload.x + payload.width, "y": payload.y + payload.height},
        {"x": payload.x, "y": payload.y + payload.height},
    ]

    panel = Panel(
        page_id=page_id,
        x=payload.x,
        y=payload.y,
        width=payload.width,
        height=payload.height,
        polygon=polygon,
        reading_order=reading_order,
        prompt=payload.prompt,
    )
    touch(page)
    session.add(panel)
    session.add(page)
    session.commit()
    session.refresh(panel)
    versioning = VersioningService(session)
    versioning.create_snapshot(panel, label=f"Panel {panel.reading_order} created", reason="panel_create")
    versioning.create_snapshot(page, entity_type="layout", label=f"Page {page.page_number} layout", reason="panel_create")
    session.commit()
    return panel


def workspace_status_chip(
    project: Project,
    active_job_count: int,
    latest_project_qa: QAReport | None,
    latest_export: ProjectExport | None,
    page_count: int,
    rendered_count: int,
    panel_count: int,
) -> str:
    if latest_export and latest_export.status == "succeeded":
        return "Exported"
    if latest_project_qa and latest_project_qa.overall_score >= 80 and not latest_project_qa.blocking:
        return "QA Passed"
    if latest_project_qa and latest_project_qa.blocking:
        return "Needs Review"
    if active_job_count or (panel_count and rendered_count < panel_count):
        return "Rendering"
    if page_count:
        return "Planning"
    return project.status.title() if project.status else "Draft"
