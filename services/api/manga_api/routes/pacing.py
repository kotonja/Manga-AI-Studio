from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from manga_api.access import require_chapter_access, require_project_access
from manga_api.auth import require_alpha_user
from manga_api.db import get_session
from manga_api.models import Chapter, Project
from manga_api.pacing import PacingAnalyzer
from manga_api.schemas import PacingAnalysisResult, PacingRebalanceResult

router = APIRouter(tags=["pacing"], dependencies=[Depends(require_alpha_user)])


@router.post("/projects/{project_id}/pacing/analyze", response_model=PacingAnalysisResult, status_code=status.HTTP_201_CREATED)
def analyze_project_pacing(project_id: uuid.UUID, session: Session = Depends(get_session)) -> PacingAnalysisResult:
    project = require_project_access(session, project_id)
    return PacingAnalyzer(session).analyze_project(project.id, persist=True)


@router.post("/chapters/{chapter_id}/pacing/rebalance", response_model=PacingRebalanceResult, status_code=status.HTTP_201_CREATED)
def rebalance_chapter_pacing(chapter_id: uuid.UUID, session: Session = Depends(get_session)) -> PacingRebalanceResult:
    chapter = require_chapter_access(session, chapter_id)
    try:
        return PacingAnalyzer(session).rebalance_chapter(chapter.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
