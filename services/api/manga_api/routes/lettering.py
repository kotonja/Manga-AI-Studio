from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from manga_api.access import require_page_access, require_panel_access, require_sfx_access
from manga_api.auth import require_alpha_user
from manga_api.db import get_session
from manga_api.lettering import LetteringPlanner, lettering_svg_for_page
from manga_api.models import Page, Panel, SFXElement
from manga_api.schemas import (
    LetteringGenerateResult,
    LetteringPageRead,
    SFXElementCreate,
    SFXElementRead,
    SFXElementUpdate,
)
from manga_api.versioning import VersioningService

router = APIRouter(tags=["lettering"], dependencies=[Depends(require_alpha_user)])


def touch(row) -> None:
    row.updated_at = datetime.now(timezone.utc)


@router.get("/pages/{page_id}/lettering", response_model=LetteringPageRead)
def get_page_lettering(page_id: uuid.UUID, session: Session = Depends(get_session)) -> dict:
    require_page(session, page_id)
    return LetteringPlanner(session).page_lettering(page_id)


@router.post("/pages/{page_id}/lettering/generate", response_model=LetteringGenerateResult, status_code=status.HTTP_201_CREATED)
def generate_page_lettering(page_id: uuid.UUID, session: Session = Depends(get_session)) -> dict:
    page = require_page(session, page_id)
    result = LetteringPlanner(session).generate_for_page(page_id)
    VersioningService(session).create_snapshot(
        page,
        entity_type="lettering",
        label=f"Page {page.page_number} generated lettering",
        reason="lettering_generate",
    )
    session.commit()
    return result


@router.post("/pages/{page_id}/sfx", response_model=SFXElementRead, status_code=status.HTTP_201_CREATED)
def create_sfx(page_id: uuid.UUID, payload: SFXElementCreate, session: Session = Depends(get_session)) -> SFXElement:
    page = require_page(session, page_id)
    if payload.panel_id is not None:
        require_panel_on_page(session, payload.panel_id, page_id)
    validate_sfx_bounds(page, payload.position, payload.size)
    VersioningService(session).create_snapshot(
        page,
        entity_type="lettering",
        label=f"Page {page.page_number} lettering",
        reason="before_sfx_create",
    )
    element = SFXElement(page_id=page_id, **payload.model_dump())
    session.add(element)
    session.commit()
    session.refresh(element)
    return element


@router.put("/sfx/{sfx_id}", response_model=SFXElementRead)
def update_sfx(sfx_id: uuid.UUID, payload: SFXElementUpdate, session: Session = Depends(get_session)) -> SFXElement:
    element = require_sfx_access(session, sfx_id)
    updates = payload.model_dump(exclude_unset=True)
    if "panel_id" in updates and updates["panel_id"] is not None:
        require_panel_on_page(session, updates["panel_id"], element.page_id)
    page = require_page(session, element.page_id)
    validate_sfx_bounds(page, updates.get("position", element.position), updates.get("size", element.size))
    VersioningService(session).create_snapshot(
        page,
        entity_type="lettering",
        label=f"Page {page.page_number} lettering",
        reason="before_sfx_update",
    )
    for field, value in updates.items():
        setattr(element, field, value)
    touch(element)
    session.add(element)
    session.commit()
    session.refresh(element)
    return element


@router.delete("/sfx/{sfx_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sfx(sfx_id: uuid.UUID, session: Session = Depends(get_session)) -> Response:
    element = require_sfx_access(session, sfx_id)
    page = require_page(session, element.page_id)
    VersioningService(session).create_snapshot(
        page,
        entity_type="lettering",
        label=f"Page {page.page_number} lettering",
        reason="before_sfx_delete",
    )
    session.delete(element)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/pages/{page_id}/lettering.svg")
def get_page_lettering_svg(page_id: uuid.UUID, session: Session = Depends(get_session)) -> Response:
    require_page(session, page_id)
    svg = lettering_svg_for_page(session, page_id)
    return Response(content=svg, media_type="image/svg+xml")


def require_page(session: Session, page_id: uuid.UUID) -> Page:
    return require_page_access(session, page_id)


def require_panel_on_page(session: Session, panel_id: uuid.UUID, page_id: uuid.UUID) -> Panel:
    panel, _page = require_panel_access(session, panel_id)
    if panel.page_id != page_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SFX panel does not belong to page")
    return panel


def validate_sfx_bounds(page: Page, position: dict, size: dict) -> None:
    try:
        x = float(position.get("x", 0))
        y = float(position.get("y", 0))
        width = float(size.get("width", 1))
        height = float(size.get("height", 1))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="SFX position and size must be numeric") from exc
    if width <= 0 or height <= 0:
        raise HTTPException(status_code=422, detail="SFX size must be positive")
    if x < 0 or y < 0 or x + width > page.width or y + height > page.height:
        raise HTTPException(status_code=422, detail="SFX element must stay inside page bounds")
