from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from manga_api.access import require_bubble_access, require_layout_template_access, require_page_access, require_panel_access, require_project_access
from manga_api.auth import require_alpha_user
from manga_api.db import get_session
from manga_api.layout_planner import LayoutPlanner, LayoutValidationError, validate_panel_inputs
from manga_api.models import Bubble, LayoutTemplate, Page, PagePlan, Panel, Project, StyleBible
from manga_api.schemas import (
    BubbleCreate,
    BubbleRead,
    BubbleUpdate,
    LayoutPoint,
    LayoutSuggestRequest,
    LayoutSuggestionRead,
    LayoutTemplateCreate,
    LayoutTemplateRead,
    PageLayoutRead,
    PageLayoutUpdate,
    PanelLayoutInput,
    PanelLayoutRead,
)
from manga_api.versioning import VersioningService

router = APIRouter(tags=["layout"], dependencies=[Depends(require_alpha_user)])


def touch(row) -> None:
    row.updated_at = datetime.now(timezone.utc)


@router.get("/pages/{page_id}/layout", response_model=PageLayoutRead)
def get_page_layout(page_id: uuid.UUID, session: Session = Depends(get_session)) -> PageLayoutRead:
    page = require_page_access(session, page_id)
    return build_page_layout(session, page)


@router.post("/pages/{page_id}/layout/suggest", response_model=LayoutSuggestionRead)
def suggest_page_layout(
    page_id: uuid.UUID,
    payload: LayoutSuggestRequest,
    session: Session = Depends(get_session),
) -> LayoutSuggestionRead:
    page = require_page_access(session, page_id)
    project = session.get(Project, page.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    template = None
    if payload.template_id is not None:
        template = require_layout_template_access(session, payload.template_id)
        if template.project_id != project.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Layout template does not belong to project")

    page_plan = session.exec(
        select(PagePlan)
        .where(PagePlan.project_id == project.id, PagePlan.page_number == page.page_number)
        .order_by(PagePlan.created_at.desc())
    ).first()
    style_bible = None
    if project.active_style_bible_id is not None:
        style_bible = session.get(StyleBible, project.active_style_bible_id)
    if style_bible is None:
        style_bible = session.exec(
            select(StyleBible)
            .where(StyleBible.project_id == project.id)
            .order_by(StyleBible.created_at.desc())
        ).first()

    locked_panels = load_locked_panels(session, page_id, payload.locked_panel_ids)
    try:
        return LayoutPlanner(session).generate_layout(
            page_plan,
            style_bible,
            payload.reading_direction or (page.layout_json or {}).get("reading_direction", "rtl"),
            page=page,
            page_type=payload.page_type,
            template=template,
            locked_panels=locked_panels,
            safe_margin=payload.safe_margin,
            bleed=payload.bleed,
            min_gutter=payload.min_gutter,
        )
    except LayoutValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[issue.model_dump() for issue in exc.issues],
        ) from exc


@router.put("/pages/{page_id}/layout", response_model=PageLayoutRead)
def update_page_layout(
    page_id: uuid.UUID,
    payload: PageLayoutUpdate,
    session: Session = Depends(get_session),
) -> PageLayoutRead:
    page = require_page_access(session, page_id)

    VersioningService(session).create_snapshot(
        page,
        entity_type="layout",
        label=f"Page {page.page_number} layout",
        reason="before_page_layout_update",
    )
    validate_panel_layouts(payload.panels, payload.width, payload.height)

    page.width = payload.width
    page.height = payload.height
    page.layout_json = {
        "bleed": payload.bleed,
        "safe_margin": payload.safe_margin,
        "reading_direction": payload.reading_direction,
        "qa_overlay_enabled": payload.qa_overlay_enabled,
    }
    touch(page)
    session.add(page)

    for panel_payload in payload.panels:
        panel = session.get(Panel, panel_payload.id) if panel_payload.id is not None else None
        if panel_payload.id is not None and panel is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Panel not found")
        if panel is not None and panel.page_id != page_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Panel does not belong to page")

        if panel is None:
            panel = Panel(page_id=page_id)

        panel.x = panel_payload.x
        panel.y = panel_payload.y
        panel.width = panel_payload.width
        panel.height = panel_payload.height
        panel.polygon = [point.model_dump() for point in panel_payload.polygon]
        panel.reading_order = panel_payload.reading_order
        panel.prompt = panel_payload.prompt
        touch(panel)
        session.add(panel)

    session.commit()
    session.refresh(page)
    return build_page_layout(session, page)


@router.post(
    "/projects/{project_id}/layout-templates",
    response_model=LayoutTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
def create_layout_template(
    project_id: uuid.UUID,
    payload: LayoutTemplateCreate,
    session: Session = Depends(get_session),
) -> LayoutTemplate:
    project = require_project_access(session, project_id)
    template = LayoutTemplate(project_id=project.id, **payload.model_dump())
    touch(project)
    session.add(template)
    session.add(project)
    session.commit()
    session.refresh(template)
    return template


@router.get("/projects/{project_id}/layout-templates", response_model=list[LayoutTemplateRead])
def list_layout_templates(project_id: uuid.UUID, session: Session = Depends(get_session)) -> list[LayoutTemplate]:
    project = require_project_access(session, project_id)
    return list(
        session.exec(
            select(LayoutTemplate)
            .where(LayoutTemplate.project_id == project.id)
            .order_by(LayoutTemplate.created_at.desc())
        ).all()
    )


@router.post("/panels/{panel_id}/bubbles", response_model=BubbleRead, status_code=status.HTTP_201_CREATED)
def create_bubble(
    panel_id: uuid.UUID,
    payload: BubbleCreate,
    session: Session = Depends(get_session),
) -> Bubble:
    panel, _page_for_access = require_panel_access(session, panel_id)

    page = session.get(Page, panel.page_id)
    if page is not None:
        VersioningService(session).create_snapshot(
            page,
            entity_type="lettering",
            label=f"Page {page.page_number} lettering",
            reason="before_bubble_create",
        )
    bubble_type = payload.bubble_type or payload.kind
    bubble = Bubble(
        panel_id=panel_id,
        kind=bubble_type,
        bubble_type=bubble_type,
        speaker_character_id=payload.speaker_character_id,
        x=payload.x,
        y=payload.y,
        width=payload.width,
        height=payload.height,
        text=payload.text,
        language=payload.language,
        reading_direction=payload.reading_direction,
        shape=payload.shape,
        position=payload.position or {"x": payload.x, "y": payload.y},
        size=payload.size or {"width": payload.width, "height": payload.height},
        tail_target=payload.tail_target,
        font_family=payload.font_family,
        font_size=payload.font_size,
        font_weight=payload.font_weight,
        text_align=payload.text_align,
        vertical_text=payload.vertical_text,
        z_index=payload.z_index,
        locked=payload.locked,
    )
    session.add(bubble)
    session.commit()
    session.refresh(bubble)
    return bubble


@router.put("/bubbles/{bubble_id}", response_model=BubbleRead)
def update_bubble(
    bubble_id: uuid.UUID,
    payload: BubbleUpdate,
    session: Session = Depends(get_session),
) -> Bubble:
    bubble = require_bubble_access(session, bubble_id)

    panel = session.get(Panel, bubble.panel_id)
    page = session.get(Page, panel.page_id) if panel is not None else None
    if page is not None:
        VersioningService(session).create_snapshot(
            page,
            entity_type="lettering",
            label=f"Page {page.page_number} lettering",
            reason="before_bubble_update",
        )
    updates = payload.model_dump(exclude_unset=True)
    if "bubble_type" in updates and "kind" not in updates:
        updates["kind"] = updates["bubble_type"]
    if "kind" in updates and "bubble_type" not in updates:
        updates["bubble_type"] = updates["kind"]
    next_x = updates.get("x", bubble.x)
    next_y = updates.get("y", bubble.y)
    next_width = updates.get("width", bubble.width)
    next_height = updates.get("height", bubble.height)
    if any(field in updates for field in ["x", "y"]) and "position" not in updates:
        updates["position"] = {"x": next_x, "y": next_y}
    if any(field in updates for field in ["width", "height"]) and "size" not in updates:
        updates["size"] = {"width": next_width, "height": next_height}
    for field, value in updates.items():
        setattr(bubble, field, value)
    touch(bubble)
    session.add(bubble)
    session.commit()
    session.refresh(bubble)
    return bubble


def validate_panel_layouts(panels: list[PanelLayoutInput], page_width: int, page_height: int) -> None:
    issues = validate_panel_inputs(panels, page_width, page_height)
    blocking = [issue for issue in issues if issue.severity == "error"]
    if blocking:
        detail = "; ".join(issue.message for issue in blocking)
        raise HTTPException(status_code=422, detail=detail)


def load_locked_panels(session: Session, page_id: uuid.UUID, locked_panel_ids: list[uuid.UUID]) -> list[Panel]:
    locked_panels: list[Panel] = []
    for panel_id in locked_panel_ids:
        panel, _page = require_panel_access(session, panel_id)
        if panel.page_id != page_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Locked panel does not belong to page")
        locked_panels.append(panel)
    return locked_panels


def build_page_layout(session: Session, page: Page) -> PageLayoutRead:
    layout = page.layout_json or {}
    panels = session.exec(
        select(Panel)
        .where(Panel.page_id == page.id)
        .order_by(Panel.reading_order.asc(), Panel.created_at.asc())
    ).all()
    panel_ids = [panel.id for panel in panels]
    bubbles_by_panel: dict[uuid.UUID, list[Bubble]] = {panel.id: [] for panel in panels}
    if panel_ids:
        bubbles = session.exec(
            select(Bubble)
            .where(Bubble.panel_id.in_(panel_ids))
            .order_by(Bubble.created_at.asc())
        ).all()
        for bubble in bubbles:
            bubbles_by_panel.setdefault(bubble.panel_id, []).append(bubble)

    return PageLayoutRead(
        page_id=page.id,
        width=page.width,
        height=page.height,
        bleed=int(layout.get("bleed", 0)),
        safe_margin=int(layout.get("safe_margin", 80)),
        reading_direction=layout.get("reading_direction", "rtl"),
        qa_overlay_enabled=bool(layout.get("qa_overlay_enabled", False)),
        panels=[
            PanelLayoutRead(
                id=panel.id,
                page_id=panel.page_id,
                x=panel.x,
                y=panel.y,
                width=panel.width,
                height=panel.height,
                polygon=panel_points(panel),
                reading_order=panel.reading_order,
                prompt=panel.prompt,
                bubbles=[BubbleRead.model_validate(bubble) for bubble in bubbles_by_panel.get(panel.id, [])],
            )
            for panel in panels
        ],
    )


def panel_points(panel: Panel) -> list[LayoutPoint]:
    points = panel.polygon or [
        {"x": panel.x, "y": panel.y},
        {"x": panel.x + panel.width, "y": panel.y},
        {"x": panel.x + panel.width, "y": panel.y + panel.height},
        {"x": panel.x, "y": panel.y + panel.height},
    ]
    return [LayoutPoint.model_validate(point) for point in points]
