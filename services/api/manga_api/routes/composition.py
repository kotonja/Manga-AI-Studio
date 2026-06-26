from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from manga_api.compositor import PageCompositor, StorageClient, get_latest_composite_asset
from manga_api.db import get_session
from manga_api.models import Asset, Page
from manga_api.schemas import CompositePageRead
from manga_api.storage import get_object_storage

router = APIRouter(tags=["composition"])


@router.post("/pages/{page_id}/compose", response_model=CompositePageRead, status_code=status.HTTP_201_CREATED)
def compose_page(
    page_id: uuid.UUID,
    session: Session = Depends(get_session),
    storage: StorageClient = Depends(get_object_storage),
) -> CompositePageRead:
    page = session.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")

    try:
        result = PageCompositor(session, storage).compose_page(page_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return composite_read(result.asset, page, result.public_url)


@router.get("/pages/{page_id}/composite", response_model=CompositePageRead)
def get_page_composite(
    page_id: uuid.UUID,
    session: Session = Depends(get_session),
    storage: StorageClient = Depends(get_object_storage),
) -> CompositePageRead:
    page = session.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")

    asset = get_latest_composite_asset(session, page_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Composite page not found")
    public_url = asset.metadata_json.get("public_url") or storage.public_url(asset.storage_key)
    return composite_read(asset, page, str(public_url) if public_url else None)


def composite_read(asset: Asset, page: Page, public_url: str | None) -> CompositePageRead:
    metadata = asset.metadata_json or {}
    return CompositePageRead(
        id=asset.id,
        page_id=page.id,
        project_id=asset.project_id,
        filename=asset.filename,
        storage_key=asset.storage_key,
        public_url=public_url,
        content_type=asset.content_type,
        size_bytes=asset.size_bytes,
        width=int(metadata.get("width", page.width)),
        height=int(metadata.get("height", page.height)),
        reading_direction=str(metadata.get("reading_direction", (page.layout_json or {}).get("reading_direction", "rtl"))),
        metadata_json=metadata,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )
