from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from manga_api.config import get_settings
from manga_api.db import get_session
from manga_api.director import MangaDirectorOrchestrator
from manga_api.models import GenerationJob, JobEvent, Project
from manga_api.queue import enqueue_director_generate_draft
from manga_api.schemas import DirectorGenerateDraftRequest, DirectorGenerateDraftResponse
from manga_api.storage import ObjectStorage, get_object_storage

router = APIRouter(tags=["director"])


@router.post(
    "/projects/{project_id}/director/generate-draft",
    response_model=DirectorGenerateDraftResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_director_draft(
    project_id: uuid.UUID,
    payload: DirectorGenerateDraftRequest,
    session: Session = Depends(get_session),
    storage: ObjectStorage = Depends(get_object_storage),
) -> DirectorGenerateDraftResponse:
    project = session.get(Project, project_id)
    if project is None:
        project = Project(
            id=project_id,
            name=project_name_from_premise(payload.premise),
            description=payload.premise,
            style_prompt=f"{', '.join(payload.genre)} manga, {payload.tone}",
        )
    else:
        project.description = payload.premise
        project.style_prompt = project.style_prompt or f"{', '.join(payload.genre)} manga, {payload.tone}"
    session.add(project)
    session.commit()
    session.refresh(project)

    job = GenerationJob(
        project_id=project.id,
        provider=payload.render_provider,
        job_type="director_generate_draft",
        status="queued",
        input_payload={"request": payload.model_dump(mode="json")},
        output_payload={"director_state": {"project_id": str(project.id)}},
    )
    session.add(job)
    session.flush()
    session.add(
        JobEvent(
            job_id=job.id,
            event_type="queued",
            message="Director draft generation queued.",
            payload={"project_id": str(project.id)},
        )
    )
    session.commit()
    session.refresh(job)

    if get_settings().enable_background_jobs:
        enqueue_director_generate_draft(str(job.id))
    else:
        MangaDirectorOrchestrator(session, storage).generate_draft(job.id)

    return DirectorGenerateDraftResponse(job_id=job.id, project_id=project.id)


def project_name_from_premise(premise: str) -> str:
    words = [word.strip(".,:;!?").title() for word in premise.split() if word.strip(".,:;!?")]
    if not words:
        return "Director Draft Manga"
    return " ".join(words[:4])[:160]
