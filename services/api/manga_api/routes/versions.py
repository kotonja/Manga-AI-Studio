from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from manga_api.db import get_session
from manga_api.models import Project
from manga_api.schemas import CheckpointCreate, VersionDiffResult, VersionRead, VersionRestoreResult
from manga_api.versioning import VersioningService

router = APIRouter(tags=["versions"])


@router.get("/projects/{project_id}/versions", response_model=list[VersionRead])
def list_project_versions(project_id: uuid.UUID, session: Session = Depends(get_session)) -> list:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return VersioningService(session).list_project_versions(project_id)


@router.post("/projects/{project_id}/checkpoint", response_model=list[VersionRead], status_code=status.HTTP_201_CREATED)
def create_project_checkpoint(
    project_id: uuid.UUID,
    payload: CheckpointCreate,
    session: Session = Depends(get_session),
) -> list:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    try:
        return VersioningService(session).create_checkpoint(
            project_id,
            label=payload.label,
            created_by=payload.created_by,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/versions/{version_id}/restore", response_model=VersionRestoreResult)
def restore_version(version_id: uuid.UUID, session: Session = Depends(get_session)) -> dict:
    try:
        version = VersioningService(session).restore_snapshot(version_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"restored_version": version}


@router.get("/versions/{version_a}/diff/{version_b}", response_model=VersionDiffResult)
def diff_versions(version_a: uuid.UUID, version_b: uuid.UUID, session: Session = Depends(get_session)) -> dict:
    try:
        return VersioningService(session).diff_versions(version_a, version_b)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
