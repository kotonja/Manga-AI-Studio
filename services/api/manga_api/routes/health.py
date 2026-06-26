from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text
from sqlmodel import Session

from manga_api.db import get_session
from manga_api.queue import make_celery_client
from manga_api.storage import ObjectStorage, get_object_storage
from manga_api.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "manga-ai-api",
        "version": "0.1.0",
        "environment": settings.app_env,
        "background_jobs": settings.enable_background_jobs,
        "dev_admin_enabled": settings.enable_dev_admin,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/db")
def health_db(session: Session = Depends(get_session)):
    try:
        session.execute(text("SELECT 1")).scalar_one()
    except Exception as exc:
        return unhealthy("db", exc)
    return {"status": "ok", "service": "db", "database_url_configured": bool(get_settings().database_url)}


@router.get("/health/redis")
def health_redis():
    try:
        Redis.from_url(get_settings().redis_url, socket_timeout=2).ping()
    except Exception as exc:
        return unhealthy("redis", exc)
    return {"status": "ok", "service": "redis", "redis_url_configured": bool(get_settings().redis_url)}


@router.get("/health/storage")
def health_storage(storage: ObjectStorage = Depends(get_object_storage)):
    try:
        storage.check()
    except Exception as exc:
        return unhealthy("storage", exc)
    settings = get_settings()
    return {
        "status": "ok",
        "service": "storage",
        "bucket": settings.s3_bucket_name,
        "endpoint_configured": bool(settings.s3_endpoint_url),
    }


@router.get("/health/worker")
def health_worker():
    try:
        response = make_celery_client().control.inspect(timeout=1).ping()
    except Exception as exc:
        return unhealthy("worker", exc)
    if not response:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "service": "worker",
                "detail": "No Celery workers responded to ping.",
            },
        )
    return {"status": "ok", "service": "worker", "workers": sorted(response.keys())}


def unhealthy(service: str, exc: Exception) -> JSONResponse:
    settings = get_settings()
    return JSONResponse(
        status_code=503,
        content={
            "status": "unavailable",
            "service": service,
            "detail": str(exc) if settings.should_expose_error_details else f"{service} is unavailable",
        },
    )
