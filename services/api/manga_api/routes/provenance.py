from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from manga_api.db import get_session
from manga_api.models import Asset, Project
from manga_api.provenance import ProvenanceService
from manga_api.safety import get_safety_provider
from manga_api.schemas import (
    AssetProvenanceRead,
    AssetProvenanceUpdate,
    ProjectProvenanceRead,
    RightsDeclarationRead,
    RightsDeclarationUpsert,
    SafetyCheckRequest,
    SafetyCheckResult,
)

router = APIRouter(tags=["provenance"])


@router.get("/projects/{project_id}/provenance", response_model=ProjectProvenanceRead)
def get_project_provenance(project_id: uuid.UUID, session: Session = Depends(get_session)) -> ProjectProvenanceRead:
    require_project(session, project_id)
    return ProvenanceService(session).project_provenance(project_id)


@router.get("/projects/{project_id}/rights-declaration", response_model=RightsDeclarationRead | None)
def get_rights_declaration(project_id: uuid.UUID, session: Session = Depends(get_session)) -> RightsDeclarationRead | None:
    require_project(session, project_id)
    declaration = ProvenanceService(session).get_rights_declaration(project_id)
    return RightsDeclarationRead.model_validate(declaration) if declaration else None


@router.put("/projects/{project_id}/rights-declaration", response_model=RightsDeclarationRead)
def upsert_rights_declaration(
    project_id: uuid.UUID,
    payload: RightsDeclarationUpsert,
    session: Session = Depends(get_session),
) -> RightsDeclarationRead:
    require_project(session, project_id)
    declaration = ProvenanceService(session).upsert_rights_declaration(project_id, payload)
    session.commit()
    session.refresh(declaration)
    return RightsDeclarationRead.model_validate(declaration)


@router.get("/assets/{asset_id}/provenance", response_model=AssetProvenanceRead)
def get_asset_provenance(asset_id: uuid.UUID, session: Session = Depends(get_session)) -> AssetProvenanceRead:
    require_asset(session, asset_id)
    provenance = ProvenanceService(session).get_asset_provenance(asset_id)
    if provenance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset provenance not found")
    return AssetProvenanceRead.model_validate(provenance)


@router.put("/assets/{asset_id}/provenance", response_model=AssetProvenanceRead)
def update_asset_provenance(
    asset_id: uuid.UUID,
    payload: AssetProvenanceUpdate,
    session: Session = Depends(get_session),
) -> AssetProvenanceRead:
    asset = require_asset(session, asset_id)
    provenance = ProvenanceService(session).update_asset_provenance(asset, payload)
    session.commit()
    session.refresh(provenance)
    return AssetProvenanceRead.model_validate(provenance)


@router.post("/safety/check", response_model=SafetyCheckResult)
def check_safety(payload: SafetyCheckRequest) -> SafetyCheckResult:
    provider = get_safety_provider("mock")
    if payload.target == "uploaded_image_metadata":
        return provider.check_uploaded_image_metadata(payload.metadata)
    if payload.target == "generated_output_metadata":
        return provider.check_generated_output_metadata(payload.metadata)
    return provider.check_text_prompts(payload.text, payload.metadata)


@router.post("/style/ip-guard", response_model=SafetyCheckResult)
def check_style_ip_guard(payload: SafetyCheckRequest) -> SafetyCheckResult:
    provider = get_safety_provider("mock")
    return provider.check_text_prompts(payload.text, payload.metadata)


def require_project(session: Session, project_id: uuid.UUID) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def require_asset(session: Session, asset_id: uuid.UUID) -> Asset:
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset
