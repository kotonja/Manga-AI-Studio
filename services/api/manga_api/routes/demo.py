from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from manga_api.config import get_settings
from manga_api.db import get_session
from manga_api.demo_pipeline import DemoPipelineError, create_full_demo_project
from manga_api.founder_demo import FounderDemoRunner, create_founder_demo_job
from manga_api.queue import enqueue_founder_demo_run
from manga_api.schemas import DemoPipelineResult, FounderDemoRunRequest, FounderDemoRunResponse, ProjectRead
from manga_api.storage import ObjectStorage, get_object_storage

router = APIRouter(tags=["demo"])


@router.post("/demo/create-full-project", response_model=DemoPipelineResult, status_code=status.HTTP_201_CREATED)
def create_demo_full_project(
    session: Session = Depends(get_session),
    storage: ObjectStorage = Depends(get_object_storage),
) -> DemoPipelineResult:
    try:
        result = create_full_demo_project(session, storage)
    except DemoPipelineError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return DemoPipelineResult(
        project=ProjectRead.model_validate(result.project),
        story_bible_id=result.story_bible_id,
        chapter_id=result.chapter_id,
        page_ids=result.page_ids,
        panel_ids=result.panel_ids,
        render_job_ids=result.render_job_ids,
        composite_asset_ids=result.composite_asset_ids,
        qa_report_ids=result.qa_report_ids,
        exports=result.exports,
    )


@router.post("/demo/founder-run", response_model=FounderDemoRunResponse, status_code=status.HTTP_202_ACCEPTED)
def create_founder_demo_run(
    payload: FounderDemoRunRequest,
    session: Session = Depends(get_session),
    storage: ObjectStorage = Depends(get_object_storage),
) -> FounderDemoRunResponse:
    try:
        job = create_founder_demo_job(session, payload)
        if get_settings().enable_background_jobs:
            enqueue_founder_demo_run(str(job.id))
        else:
            job = FounderDemoRunner(session, storage).run(job.id)
    except DemoPipelineError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    if job.project_id is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Founder Demo job did not create a project")
    return FounderDemoRunResponse(job_id=job.id, project_id=job.project_id)
