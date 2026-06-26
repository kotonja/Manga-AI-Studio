from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from manga_api.db import build_engine
from manga_api.director import MangaDirectorOrchestrator
from manga_api.founder_demo import FounderDemoRunner
from manga_api.models import GenerationJob
from manga_api.rendering import RenderOrchestrator
from manga_worker.celery_app import celery_app
from manga_worker.storage import ObjectStorage

engine = build_engine()
logger = logging.getLogger("manga_worker.jobs")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def mark_failed(job_id: uuid.UUID, error: str) -> None:
    with Session(engine) as session:
        job = session.get(GenerationJob, job_id)
        if job is None:
            return
        job.status = "failed"
        job.error_message = error[:4000]
        job.updated_at = utc_now()
        session.add(job)
        session.commit()
        logger.warning("job marked failed", extra={"job_id": str(job_id)})


def run_render_job(job_id: str) -> dict[str, Any]:
    parsed_job_id = uuid.UUID(job_id)
    try:
        logger.info("render job started", extra={"job_id": job_id})
        with Session(engine) as session:
            job = session.get(GenerationJob, parsed_job_id)
            if job is None:
                return {"status": "missing", "job_id": job_id}
            if job.panel_id is None:
                raise ValueError("Render job does not reference a panel")

            options = job.input_payload.get("options", {}) if isinstance(job.input_payload, dict) else {}
            if not isinstance(options, dict):
                options = {}

            orchestrator = RenderOrchestrator(session, ObjectStorage())
            rendered_job = orchestrator.render_panel(
                job.panel_id,
                job.provider,
                options=options,
                job=job,
            )
            if rendered_job.status == "failed":
                logger.warning("render job failed cleanly", extra={"job_id": job_id})
                return {
                    "status": rendered_job.status,
                    "job_id": job_id,
                    "error_message": rendered_job.error_message,
                    "error_metadata": rendered_job.output_payload.get("error_metadata")
                    if isinstance(rendered_job.output_payload, dict)
                    else None,
                }
            logger.info("render job succeeded", extra={"job_id": job_id})
            return {
                "status": rendered_job.status,
                "job_id": job_id,
                "storage_key": rendered_job.output_payload.get("storage_key"),
            }
    except Exception as exc:
        mark_failed(parsed_job_id, str(exc))
        logger.exception("render job failed", extra={"job_id": job_id})
        return {"status": "failed", "job_id": job_id, "error_message": str(exc)[:1000]}


@celery_app.task(name="manga_worker.render_panel")
def render_panel(job_id: str) -> dict[str, Any]:
    return run_render_job(job_id)


@celery_app.task(name="manga_worker.mock_render_panel")
def mock_render_panel(job_id: str) -> dict[str, Any]:
    return run_render_job(job_id)


@celery_app.task(name="manga_worker.director_generate_draft")
def director_generate_draft(job_id: str) -> dict[str, Any]:
    parsed_job_id = uuid.UUID(job_id)
    logger.info("director job started", extra={"job_id": job_id})
    with Session(engine) as session:
        job = MangaDirectorOrchestrator(session, ObjectStorage()).generate_draft(parsed_job_id)
        if job.status == "failed":
            logger.warning("director job failed", extra={"job_id": job_id})
            raise RuntimeError(job.error_message or "Director draft generation failed")
        logger.info("director job succeeded", extra={"job_id": job_id, "project_id": str(job.project_id)})
        return {"status": job.status, "job_id": job_id, "project_id": str(job.project_id)}


@celery_app.task(name="manga_worker.founder_demo_run")
def founder_demo_run(job_id: str) -> dict[str, Any]:
    parsed_job_id = uuid.UUID(job_id)
    logger.info("founder demo job started", extra={"job_id": job_id})
    with Session(engine) as session:
        job = FounderDemoRunner(session, ObjectStorage()).run(parsed_job_id)
        if job.status == "failed":
            logger.warning("founder demo job failed", extra={"job_id": job_id})
            raise RuntimeError(job.error_message or "Founder Demo generation failed")
        logger.info("founder demo job succeeded", extra={"job_id": job_id, "project_id": str(job.project_id)})
        return {"status": job.status, "job_id": job_id, "project_id": str(job.project_id)}
