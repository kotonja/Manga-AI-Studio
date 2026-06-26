from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from manga_api.auth import require_sensitive_access
from manga_api.provider_registry import list_provider_summaries, provider_health
from manga_api.schemas import ProviderHealthRead, ProviderRead

router = APIRouter(tags=["providers"])


@router.get("/providers", response_model=list[ProviderRead])
def list_providers(_access=Depends(require_sensitive_access)) -> list[dict]:
    return list_provider_summaries()


@router.get("/providers/{name}/health", response_model=ProviderHealthRead)
def get_provider_health(name: str, _access=Depends(require_sensitive_access)) -> dict:
    try:
        return provider_health(name)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
