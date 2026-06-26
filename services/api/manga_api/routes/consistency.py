from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from manga_api.db import get_session
from manga_api.reference_pack import ReferencePackBuilder
from manga_api.schemas import PageReferencePacksRead, ReferencePackRead

router = APIRouter(tags=["consistency"])


@router.get("/panels/{panel_id}/reference-pack", response_model=ReferencePackRead)
def get_panel_reference_pack(panel_id: uuid.UUID, session: Session = Depends(get_session)) -> dict:
    try:
        return ReferencePackBuilder(session).build_for_panel(panel_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/pages/{page_id}/reference-packs", response_model=PageReferencePacksRead)
def get_page_reference_packs(page_id: uuid.UUID, session: Session = Depends(get_session)) -> dict:
    try:
        return ReferencePackBuilder(session).build_page_summary(page_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
