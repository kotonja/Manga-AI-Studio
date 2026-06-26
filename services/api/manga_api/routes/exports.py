from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from manga_api.db import get_session
from manga_api.exporting import ExportError, ProjectExporter
from manga_api.models import Asset, Project, ProjectExport
from manga_api.publishing import (
    ExportReadinessService,
    default_metadata_from_project,
    get_export_preset,
    get_project_publishing_metadata,
    list_export_presets,
    upsert_project_publishing_metadata,
)
from manga_api.schemas import (
    AssetRead,
    ExportCreate,
    ExportCreateAdvanced,
    ExportPresetRead,
    ExportPreviewResult,
    ExportRead,
    ExportReadinessResult,
    ProjectPublishingMetadataRead,
    ProjectPublishingMetadataUpsert,
)
from manga_api.storage import ObjectStorage, get_object_storage

router = APIRouter(tags=["exports"])


@router.get("/export-presets", response_model=list[ExportPresetRead])
def get_export_presets() -> list[ExportPresetRead]:
    return list_export_presets()


@router.get("/projects/{project_id}/publishing-metadata", response_model=ProjectPublishingMetadataRead)
def get_publishing_metadata(project_id: uuid.UUID, session: Session = Depends(get_session)) -> ProjectPublishingMetadataRead:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    metadata = get_project_publishing_metadata(session, project.id)
    if metadata is None:
        metadata = upsert_project_publishing_metadata(session, project, default_metadata_from_project(project))
        session.commit()
        session.refresh(metadata)
    return ProjectPublishingMetadataRead.model_validate(metadata)


@router.put("/projects/{project_id}/publishing-metadata", response_model=ProjectPublishingMetadataRead)
def update_publishing_metadata(
    project_id: uuid.UUID,
    payload: ProjectPublishingMetadataUpsert,
    session: Session = Depends(get_session),
) -> ProjectPublishingMetadataRead:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    metadata = upsert_project_publishing_metadata(session, project, payload)
    session.commit()
    session.refresh(metadata)
    return ProjectPublishingMetadataRead.model_validate(metadata)


@router.get("/projects/{project_id}/export-readiness", response_model=ExportReadinessResult)
def get_export_readiness(
    project_id: uuid.UUID,
    preset_id: str = "archive_package",
    session: Session = Depends(get_session),
) -> ExportReadinessResult:
    try:
        return ExportReadinessService(session).readiness(project_id, preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/projects/{project_id}/exports/preview", response_model=ExportPreviewResult)
def preview_project_export(
    project_id: uuid.UUID,
    payload: ExportCreateAdvanced | None = None,
    session: Session = Depends(get_session),
) -> ExportPreviewResult:
    payload = payload or ExportCreateAdvanced()
    try:
        return ExportReadinessService(session).preview(project_id, payload.preset_id, payload.options)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/projects/{project_id}/exports/create", response_model=ExportRead, status_code=status.HTTP_201_CREATED)
def create_project_export_advanced(
    project_id: uuid.UUID,
    payload: ExportCreateAdvanced,
    session: Session = Depends(get_session),
    storage: ObjectStorage = Depends(get_object_storage),
) -> ExportRead:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if payload.metadata is not None:
        upsert_project_publishing_metadata(session, project, payload.metadata)
        session.commit()

    try:
        preset = get_export_preset(payload.preset_id)
        readiness = ExportReadinessService(session).readiness(project.id, preset.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not payload.force and not readiness.ready:
        failed = [item.message for item in readiness.checklist if not item.passed and item.severity == "blocking"]
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"message": "Export readiness failed", "issues": failed})

    export = ProjectExporter(session, storage).export_project(
        project.id,
        preset.file_format,
        force=payload.force,
        options={**preset.options, **payload.options, "preset_id": preset.id, "source": "publishing_room"},
    )
    return export_read(session, export)


@router.post("/projects/{project_id}/exports", response_model=ExportRead, status_code=status.HTTP_201_CREATED)
def create_project_export(
    project_id: uuid.UUID,
    payload: ExportCreate,
    session: Session = Depends(get_session),
    storage: ObjectStorage = Depends(get_object_storage),
) -> ExportRead:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        export = ProjectExporter(session, storage).export_project(
            project_id,
            str(payload.format),
            force=payload.force,
            options=payload.options,
        )
    except ExportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return export_read(session, export)


@router.get("/exports/{export_id}", response_model=ExportRead)
def get_export(export_id: uuid.UUID, session: Session = Depends(get_session)) -> ExportRead:
    export = session.get(ProjectExport, export_id)
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    return export_read(session, export)


@router.get("/exports/{export_id}/download")
def download_export(
    export_id: uuid.UUID,
    session: Session = Depends(get_session),
    storage: ObjectStorage = Depends(get_object_storage),
) -> Response:
    export = session.get(ProjectExport, export_id)
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    if export.file_asset_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Export file is not available")
    asset = session.get(Asset, export.file_asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export asset not found")

    data = storage.get_bytes(asset.storage_key)
    return Response(
        content=data,
        media_type=asset.content_type,
        headers={"Content-Disposition": f'attachment; filename="{asset.filename}"'},
    )


def export_read(session: Session, export: ProjectExport) -> ExportRead:
    asset = session.get(Asset, export.file_asset_id) if export.file_asset_id else None
    return ExportRead(
        id=export.id,
        project_id=export.project_id,
        format=export.format,
        status=export.status,
        file_asset_id=export.file_asset_id,
        options=export.options,
        error_message=export.error_message,
        created_at=export.created_at,
        updated_at=export.updated_at,
        file_asset=AssetRead.model_validate(asset) if asset is not None else None,
    )
