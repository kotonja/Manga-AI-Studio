from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from manga_api.config import get_settings
from manga_api.db import get_session
from manga_api.models import Asset, GenerationJob, Page, Panel, PanelRenderPrompt, Render
from manga_api.panel_render_director import PanelRenderDirector
from manga_api.provider_registry import estimate_image_cost, provider_summary, validate_provider_request
from manga_api.queue import enqueue_render_panel
from manga_api.rendering import ObjectStore, RenderOrchestrator, stable_seed
from manga_api.schemas import (
    AssetRead,
    GenerationJobRead,
    PanelRenderDryRunResult,
    PanelRenderHistoryItem,
    PanelRenderPromptRead,
    PanelRenderRequest,
    PanelRenderStartResult,
    PanelRerenderRequest,
    RenderRead,
)
from manga_api.storage import get_object_storage
from manga_api.versioning import VersioningService

router = APIRouter(tags=["panel-render"])


@router.post("/panels/{panel_id}/render", response_model=PanelRenderStartResult, status_code=status.HTTP_202_ACCEPTED)
def render_panel(
    panel_id: uuid.UUID,
    payload: PanelRenderRequest,
    session: Session = Depends(get_session),
    storage: ObjectStore = Depends(get_object_storage),
) -> PanelRenderStartResult:
    panel, page = require_panel_page(session, panel_id)
    director = PanelRenderDirector(session)
    prompt = director.build_prompt(
        panel.id,
        provider_name=payload.provider_name,
        render_mode=payload.render_mode,
        seed=payload.seed,
        advanced_prompt_override=payload.advanced_prompt_override,
        additional_user_instruction=payload.additional_user_instruction,
        preserve_layout=True,
    )
    job = start_render_job(session, storage, page, panel, prompt, payload.provider_name, payload.render_mode, payload.provider_options)
    return PanelRenderStartResult(
        job=GenerationJobRead.model_validate(job),
        prompt=PanelRenderPromptRead.model_validate(prompt),
    )


@router.post("/panels/{panel_id}/render-dry-run", response_model=PanelRenderDryRunResult)
def render_panel_dry_run(
    panel_id: uuid.UUID,
    payload: PanelRenderRequest,
    session: Session = Depends(get_session),
) -> PanelRenderDryRunResult:
    panel, _page = require_panel_page(session, panel_id)
    provider_name = payload.provider_name.lower().strip()
    try:
        provider = provider_summary(provider_name)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    director = PanelRenderDirector(session)
    prompt = director.build_prompt(
        panel.id,
        provider_name=provider_name,
        render_mode=payload.render_mode,
        seed=payload.seed,
        advanced_prompt_override=payload.advanced_prompt_override,
        additional_user_instruction=payload.additional_user_instruction,
        preserve_layout=True,
    )
    warnings = validate_provider_request(provider_name, prompt.size)
    estimated_cost = estimate_image_cost(provider_name, prompt.size, prompt.quality_mode)
    cost_metadata = {
        "provider": provider_name,
        "model": provider.get("model_name"),
        "requested_size": prompt.size,
        "quality_mode": prompt.quality_mode,
        "estimated_cost": estimated_cost,
        "actual_usage": None,
        "started_at": None,
        "completed_at": None,
        "dry_run": True,
    }
    can_render = bool(provider["configured"]) and not any("exceeds" in warning.lower() for warning in warnings)
    return PanelRenderDryRunResult(
        panel_id=panel.id,
        provider=provider,
        provider_configured=bool(provider["configured"]),
        can_render=can_render,
        requested_size=prompt.size,
        quality_mode=prompt.quality_mode,
        estimated_cost=estimated_cost,
        cost_metadata=cost_metadata,
        warnings=warnings,
        prompt=PanelRenderPromptRead.model_validate(prompt),
    )


@router.post("/panels/{panel_id}/rerender", response_model=PanelRenderStartResult, status_code=status.HTTP_202_ACCEPTED)
def rerender_panel(
    panel_id: uuid.UUID,
    payload: PanelRerenderRequest,
    session: Session = Depends(get_session),
    storage: ObjectStore = Depends(get_object_storage),
) -> PanelRenderStartResult:
    panel, page = require_panel_page(session, panel_id)
    latest_prompt = latest_panel_prompt(session, panel.id)
    seed = resolve_rerender_seed(panel.id, payload, latest_prompt)
    camera_instruction = payload.camera_instruction
    expression_instruction = payload.expression_instruction
    additional_instruction = payload.additional_user_instruction
    preserve_layout = payload.control in {"same_seed", "new_seed", "preserve_layout", "additional_instruction"}
    if payload.control == "change_camera" and not camera_instruction:
        camera_instruction = "Change the internal camera angle while preserving the panel polygon, story beat, characters, and continuity."
    if payload.control == "change_expression" and not expression_instruction:
        expression_instruction = "Change facial expression/acting while preserving identity anchors, outfit, layout, and story beat."
    if payload.control == "additional_instruction" and not additional_instruction:
        additional_instruction = "Apply the user-requested creative adjustment while preserving continuity."

    director = PanelRenderDirector(session)
    prompt = director.build_prompt(
        panel.id,
        provider_name=payload.provider_name,
        render_mode=payload.render_mode,
        seed=seed,
        advanced_prompt_override=payload.advanced_prompt_override,
        additional_user_instruction=additional_instruction,
        camera_instruction=camera_instruction,
        expression_instruction=expression_instruction,
        preserve_layout=preserve_layout,
    )
    provider_options = {
        **payload.provider_options,
        "rerender_control": payload.control,
        "camera_instruction": camera_instruction,
        "expression_instruction": expression_instruction,
        "additional_user_instruction": additional_instruction,
        "preserve_layout": preserve_layout,
    }
    job = start_render_job(session, storage, page, panel, prompt, payload.provider_name, payload.render_mode, provider_options)
    return PanelRenderStartResult(
        job=GenerationJobRead.model_validate(job),
        prompt=PanelRenderPromptRead.model_validate(prompt),
    )


@router.get("/panels/{panel_id}/render-prompts", response_model=list[PanelRenderPromptRead])
def list_panel_render_prompts(panel_id: uuid.UUID, session: Session = Depends(get_session)) -> list[PanelRenderPrompt]:
    require_panel_page(session, panel_id)
    return list(
        session.exec(
            select(PanelRenderPrompt)
            .where(PanelRenderPrompt.panel_id == panel_id)
            .order_by(PanelRenderPrompt.created_at.desc(), PanelRenderPrompt.id.desc())
        ).all()
    )


@router.get("/panels/{panel_id}/renders", response_model=list[PanelRenderHistoryItem])
def list_panel_renders(panel_id: uuid.UUID, session: Session = Depends(get_session)) -> list[PanelRenderHistoryItem]:
    require_panel_page(session, panel_id)
    renders = session.exec(
        select(Render)
        .where(Render.panel_id == panel_id)
        .order_by(Render.created_at.desc(), Render.id.desc())
    ).all()
    return [build_history_item(session, render) for render in renders]


@router.post("/renders/{render_id}/approve", response_model=PanelRenderHistoryItem)
def approve_render(render_id: uuid.UUID, session: Session = Depends(get_session)) -> PanelRenderHistoryItem:
    render = session.get(Render, render_id)
    if render is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Render not found")
    panel_renders = session.exec(select(Render).where(Render.panel_id == render.panel_id)).all()
    for panel_render in panel_renders:
        if panel_render.asset_id is None:
            continue
        asset = session.get(Asset, panel_render.asset_id)
        if asset is None:
            continue
        metadata = dict(asset.metadata_json or {})
        metadata["approved"] = panel_render.id == render.id
        if panel_render.id == render.id:
            metadata["approved_at"] = datetime.now(timezone.utc).isoformat()
        asset.metadata_json = metadata
        session.add(asset)
    VersioningService(session).create_snapshot(
        render,
        label="Render approved",
        reason="render_approved",
    )
    session.commit()
    return build_history_item(session, render)


def start_render_job(
    session: Session,
    storage: ObjectStore,
    page: Page,
    panel: Panel,
    prompt: PanelRenderPrompt,
    provider_name: str,
    render_mode: str,
    provider_options: dict[str, Any],
) -> GenerationJob:
    provider_name = provider_name.lower().strip()
    options = PanelRenderDirector.mode_options(
        render_mode,
        {
            **provider_options,
            "panel_render_prompt_id": str(prompt.id),
            "seed": prompt.seed,
            "render_mode": prompt.quality_mode,
            "quality_mode": prompt.quality_mode,
        },
    )
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
            "panel_render_prompt_id": str(prompt.id),
            "render_mode": prompt.quality_mode,
            "options": options,
        },
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    if get_settings().enable_background_jobs:
        enqueue_render_panel(str(job.id))
        return job
    rendered_job = RenderOrchestrator(session, storage).render_panel(panel.id, provider_name, options=options, job=job)
    return rendered_job


def require_panel_page(session: Session, panel_id: uuid.UUID) -> tuple[Panel, Page]:
    panel = session.get(Panel, panel_id)
    if panel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Panel not found")
    page = session.get(Page, panel.page_id)
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    return panel, page


def latest_panel_prompt(session: Session, panel_id: uuid.UUID) -> PanelRenderPrompt | None:
    return session.exec(
        select(PanelRenderPrompt)
        .where(PanelRenderPrompt.panel_id == panel_id)
        .order_by(PanelRenderPrompt.created_at.desc(), PanelRenderPrompt.id.desc())
    ).first()


def resolve_rerender_seed(
    panel_id: uuid.UUID,
    payload: PanelRerenderRequest,
    latest_prompt: PanelRenderPrompt | None,
) -> int | None:
    if payload.seed is not None:
        return payload.seed
    if payload.control == "new_seed":
        return stable_seed(f"{panel_id}:{uuid.uuid4()}")
    if latest_prompt is not None and latest_prompt.seed is not None:
        return latest_prompt.seed
    return None


def build_history_item(session: Session, render: Render) -> PanelRenderHistoryItem:
    job = session.get(GenerationJob, render.job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Render job missing")
    asset = session.get(Asset, render.asset_id) if render.asset_id is not None else None
    prompt = prompt_for_job(session, job)
    return PanelRenderHistoryItem(
        render=RenderRead.model_validate(render),
        job=GenerationJobRead.model_validate(job),
        prompt=PanelRenderPromptRead.model_validate(prompt) if prompt is not None else None,
        asset=AssetRead.model_validate(asset) if asset is not None else None,
        approved=bool((asset.metadata_json or {}).get("approved")) if asset is not None else False,
    )


def prompt_for_job(session: Session, job: GenerationJob) -> PanelRenderPrompt | None:
    prompt_id = None
    if isinstance(job.output_payload, dict):
        prompt_id = job.output_payload.get("panel_render_prompt_id")
    if prompt_id is None and isinstance(job.input_payload, dict):
        prompt_id = job.input_payload.get("panel_render_prompt_id")
        options = job.input_payload.get("options")
        if prompt_id is None and isinstance(options, dict):
            prompt_id = options.get("panel_render_prompt_id")
    if prompt_id is None:
        return None
    return session.get(PanelRenderPrompt, uuid.UUID(str(prompt_id)))
