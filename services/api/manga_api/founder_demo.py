from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from sqlmodel import Session

from manga_api.demo_pipeline import DEMO_PREMISE, DemoPipelineError, create_full_demo_project
from manga_api.models import GenerationJob, JobEvent, Project
from manga_api.schemas import FounderDemoRunRequest


class FounderDemoStorage(Protocol):
    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        """Persist bytes to object storage."""

    def get_bytes(self, key: str) -> bytes:
        """Read bytes from object storage."""

    def public_url(self, key: str) -> str:
        """Return a browser-accessible URL for a stored object."""


FOUNDER_DEMO_STYLE_OPTIONS: dict[str, dict[str, Any]] = {
    "ruined_ink_elegy": {
        "project_name": "Ghost Lantern",
        "name": "Ruined Ink Elegy",
        "style_name": "Ruined Ink Elegy",
        "style_intent": "A quiet, original dark-fantasy manga look built around rain, ruins, silhouettes, and lantern-white hope.",
        "prompt_style_positive": "Original black-and-white manga, ruined samurai city, rain texture, crisp ink, restrained faces, luminous lantern contrast.",
        "prompt_style_negative": "copied artist style, named franchise look, muddy grayscale, soft painterly color, unreadable text.",
        "visual_style": "High-contrast supernatural samurai manga with detailed ruins and luminous lantern contrast.",
        "linework": "Sharp brush contours with dry, broken texture on ruins.",
        "screentone": "Soft rain tone in skies, heavier dot tone in alleys.",
        "hatching": "Thin crosshatching for stone, bold slashes for sword motion.",
        "black_white_balance": "Large black ruins contrasted with white lantern glow and clean silhouettes.",
        "panel_rhythm": "Quiet wide panels punctuated by narrow sword-action cuts.",
        "positive_prompt_fragments": ["original black-and-white manga", "ruined samurai city", "rain texture", "lantern contrast"],
    },
    "moonlit_screentone_noir": {
        "project_name": "Ghost Lantern",
        "name": "Moonlit Screentone Noir",
        "style_name": "Moonlit Screentone Noir",
        "style_intent": "A moody original noir-manga treatment with pale mist, strong silhouettes, and soft ghostly negative space.",
        "prompt_style_positive": "Original monochrome manga noir, moonlit ruins, mist layers, elegant screentone gradients, quiet ghost-story emotion.",
        "prompt_style_negative": "copied artist style, named franchise look, photorealism, glossy color, cluttered panels.",
        "visual_style": "Atmospheric monochrome ghost-story manga with mist, tall shadows, and clean readable figures.",
        "linework": "Elegant thin contours with heavier silhouette accents.",
        "screentone": "Layered moonlit dot tone and mist gradients.",
        "hatching": "Sparse hatching, mostly reserved for cracked stone and old wood.",
        "black_white_balance": "Soft pale fields interrupted by tall pools of black.",
        "panel_rhythm": "Slow cinematic reveals with intimate close-ups.",
        "positive_prompt_fragments": ["original manga noir", "moonlit ruins", "mist layers", "soft ghostly negative space"],
    },
    "kinetic_ash_action": {
        "project_name": "Ghost Lantern",
        "name": "Kinetic Ash Action",
        "style_name": "Kinetic Ash Action",
        "style_intent": "A bold original action-manga language with ash bursts, sharp motion cuts, and muscular page rhythm.",
        "prompt_style_positive": "Original black-and-white action manga, ash bursts, bold speed lines, cracked impact frames, clean heroic silhouettes.",
        "prompt_style_negative": "copied artist style, named franchise look, muddy anatomy, unreadable action, busy bubble placement.",
        "visual_style": "Dynamic supernatural action manga with aggressive diagonals, white gutters, and bold impact timing.",
        "linework": "Heavy foreground brush lines with razor-thin speed accents.",
        "screentone": "Low-density tone so action silhouettes stay readable.",
        "hatching": "Directional blade hatching and broken ash textures.",
        "black_white_balance": "Strong black action shapes with white speed-line cuts.",
        "panel_rhythm": "Fast diagonal panels with one calm emotional anchor per page.",
        "positive_prompt_fragments": ["original action manga", "ash bursts", "bold speed lines", "cracked impact frames"],
    },
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_founder_demo_job(session: Session, payload: FounderDemoRunRequest) -> GenerationJob:
    style = founder_style_profile(payload.style_option)
    project = Project(
        name=str(style.get("project_name", "Ghost Lantern")),
        description=payload.premise,
        style_prompt=str(style.get("prompt_style_positive", "")),
    )
    session.add(project)
    session.flush()

    job = GenerationJob(
        project_id=project.id,
        provider=payload.render_provider,
        job_type="founder_demo_run",
        status="queued",
        input_payload={
            "request": payload.model_dump(mode="json"),
            "style_profile": style,
        },
        output_payload={
            "founder_state": {
                "project_id": str(project.id),
                "style_option": payload.style_option,
                "premise": payload.premise,
            }
        },
    )
    session.add(job)
    session.flush()
    session.add(
        JobEvent(
            job_id=job.id,
            event_type="queued",
            message="Founder Demo manga generation queued.",
            payload={"project_id": str(project.id)},
        )
    )
    session.commit()
    session.refresh(job)
    return job


def founder_style_profile(style_option: str) -> dict[str, Any]:
    return dict(FOUNDER_DEMO_STYLE_OPTIONS.get(style_option, FOUNDER_DEMO_STYLE_OPTIONS["ruined_ink_elegy"]))


class FounderDemoRunner:
    def __init__(self, session: Session, storage: FounderDemoStorage) -> None:
        self.session = session
        self.storage = storage

    def run(self, job_id: uuid.UUID | str) -> GenerationJob:
        job = self._require_job(job_id)
        request = FounderDemoRunRequest.model_validate((job.input_payload or {}).get("request", {}))
        style = dict((job.input_payload or {}).get("style_profile") or founder_style_profile(request.style_option))
        job.status = "running"
        job.error_message = None
        job.updated_at = utc_now()
        self._save_job(job)

        try:
            result = create_full_demo_project(
                self.session,
                self.storage,
                project_id=job.project_id,
                premise=request.premise or DEMO_PREMISE,
                page_count=request.page_count,
                reading_direction=request.reading_direction,
                render_provider=request.render_provider,
                allow_mock_assets=request.allow_mock_assets,
                style_profile=style,
                event_callback=lambda event_type, message, payload: self._emit(job, event_type, message, payload),
            )
            founder_state = {
                "project_id": str(result.project.id),
                "story_bible_id": str(result.story_bible_id),
                "chapter_id": str(result.chapter_id),
                "page_ids": [str(page_id) for page_id in result.page_ids],
                "panel_ids": [str(panel_id) for panel_id in result.panel_ids],
                "render_job_ids": [str(render_job_id) for render_job_id in result.render_job_ids],
                "composite_asset_ids": [str(asset_id) for asset_id in result.composite_asset_ids],
                "qa_report_ids": [str(report_id) for report_id in result.qa_report_ids],
                "exports": {key: str(value) for key, value in result.exports.items()},
                "style_option": request.style_option,
                "premise": request.premise,
            }
            output = dict(job.output_payload or {})
            output["founder_state"] = founder_state
            job.output_payload = output
            job.status = "succeeded"
            job.updated_at = utc_now()
            self._save_job(job)
            self._emit(job, "complete", "Founder Demo manga is ready to inspect.", founder_state)
            return job
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)[:4000]
            job.updated_at = utc_now()
            self._save_job(job)
            self._emit(job, "failed", str(exc)[:1000], {"project_id": str(job.project_id) if job.project_id else None})
            return job

    def _require_job(self, job_id: uuid.UUID | str) -> GenerationJob:
        job = self.session.get(GenerationJob, uuid.UUID(str(job_id)))
        if job is None:
            raise DemoPipelineError("Founder Demo job not found")
        return job

    def _save_job(self, job: GenerationJob) -> None:
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)

    def _emit(self, job: GenerationJob, event_type: str, message: str, payload: dict[str, Any] | None = None) -> None:
        self.session.add(
            JobEvent(
                job_id=job.id,
                event_type=event_type,
                message=message,
                payload=payload or {},
            )
        )
        self.session.commit()
