from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from manga_api.config import get_settings
from manga_api.db import get_session
from manga_api.models import GenerationJob, JobEvent, Page, Panel, Render
from manga_api.queue import enqueue_render_panel
from manga_api.rendering import ObjectStore, RenderOrchestrator
from manga_api.schemas import (
    GenerationJobDetail,
    GenerationJobRead,
    GenerationJobRetryResult,
    JobEventRead,
    JobRetryRequest,
    MockRenderPanelRequest,
    RenderPanelRequest,
    RenderRead,
)
from manga_api.storage import get_object_storage

router = APIRouter(tags=["jobs"])


@router.post("/jobs/mock-render-panel", response_model=GenerationJobRead, status_code=status.HTTP_202_ACCEPTED)
def create_mock_render_job(
    payload: MockRenderPanelRequest,
    session: Session = Depends(get_session),
    storage: ObjectStore = Depends(get_object_storage),
) -> GenerationJob:
    return create_render_job_for_panel(payload.panel_id, "mock", {}, session, storage)


@router.post("/jobs/render-panel", response_model=GenerationJobRead, status_code=status.HTTP_202_ACCEPTED)
def create_render_job(
    payload: RenderPanelRequest,
    session: Session = Depends(get_session),
    storage: ObjectStore = Depends(get_object_storage),
) -> GenerationJob:
    return create_render_job_for_panel(payload.panel_id, payload.provider_name, payload.options, session, storage)


def create_render_job_for_panel(
    panel_id: uuid.UUID,
    provider_name: str,
    options: dict[str, Any],
    session: Session,
    storage: ObjectStore | None = None,
) -> GenerationJob:
    provider_name = provider_name.lower().strip()
    panel = session.get(Panel, panel_id)
    if panel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Panel not found")

    page = session.get(Page, panel.page_id)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")

    job = GenerationJob(
        project_id=page.project_id,
        page_id=page.id,
        panel_id=panel.id,
        provider=provider_name,
        job_type="render_panel",
        status="queued",
        input_payload={
            "panel_id": str(panel.id),
            "page_id": str(page.id),
            "provider": provider_name,
            "options": options,
        },
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    if get_settings().enable_background_jobs:
        enqueue_render_panel(str(job.id))
    else:
        job = RenderOrchestrator(session, storage).render_panel(
            panel.id,
            provider_name,
            options=options,
            job=job,
        )

    return job


@router.get("/jobs/{job_id}", response_model=GenerationJobDetail)
def get_job(job_id: uuid.UUID, session: Session = Depends(get_session)) -> GenerationJobDetail:
    job = session.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    render = session.exec(select(Render).where(Render.job_id == job_id)).first()
    job_read = GenerationJobRead.model_validate(job)
    return GenerationJobDetail(
        **job_read.model_dump(),
        render=RenderRead.model_validate(render) if render is not None else None,
    )


@router.post("/jobs/{job_id}/retry", response_model=GenerationJobRetryResult, status_code=status.HTTP_202_ACCEPTED)
def retry_failed_job(
    job_id: uuid.UUID,
    payload: JobRetryRequest | None = None,
    session: Session = Depends(get_session),
    storage: ObjectStore = Depends(get_object_storage),
) -> GenerationJobRetryResult:
    payload = payload or JobRetryRequest()
    source_job = session.get(GenerationJob, job_id)
    if source_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if source_job.status != "failed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only failed jobs can be retried")
    if source_job.job_type != "render_panel" or source_job.panel_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only failed panel render jobs can be retried in alpha")

    source_options = {}
    if isinstance(source_job.input_payload, dict):
        raw_options = source_job.input_payload.get("options")
        if isinstance(raw_options, dict):
            source_options.update(raw_options)
    provider_name = (payload.provider_name or ("mock" if payload.use_mock_fallback else source_job.provider)).lower().strip()
    retry_options = {
        **source_options,
        **payload.options,
        "retry_of_job_id": str(source_job.id),
        "retry_from_provider": source_job.provider,
    }
    retry_job = create_render_job_for_panel(source_job.panel_id, provider_name, retry_options, session, storage)
    return GenerationJobRetryResult(
        source_job_id=source_job.id,
        job=GenerationJobRead.model_validate(retry_job),
        message="Retry started with mock provider." if provider_name == "mock" else f"Retry started with {provider_name}.",
    )


@router.get("/jobs/{job_id}/events", response_model=list[JobEventRead])
def get_job_events(job_id: uuid.UUID, session: Session = Depends(get_session)) -> list[JobEvent]:
    job = session.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return list(
        session.exec(
            select(JobEvent)
            .where(JobEvent.job_id == job_id)
            .order_by(JobEvent.created_at.asc(), JobEvent.id.asc())
        ).all()
    )
