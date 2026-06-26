from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from manga_api.access import require_page_access, require_project_access, require_qa_report_access
from manga_api.auth import require_alpha_user
from manga_api.db import get_session
from manga_api.models import Page, Project, QAReport
from manga_api.qa import PageQAService, build_qa_options, get_qa_provider, latest_qa_report
from manga_api.qa_autofix import AutoFixService
from manga_api.schemas import QAAutoFixRequest, QAAutoFixResult, QAProjectRunResult, QAReportRead, QARequest
from manga_api.storage import get_object_storage

router = APIRouter(tags=["qa"], dependencies=[Depends(require_alpha_user)])


@router.post("/pages/{page_id}/qa", response_model=QAReportRead, status_code=status.HTTP_201_CREATED)
def run_page_qa(
    page_id: uuid.UUID,
    payload: QARequest | None = None,
    session: Session = Depends(get_session),
) -> QAReport:
    require_page_access(session, page_id)

    payload = payload or QARequest()
    try:
        provider = get_qa_provider(payload.provider_name)
        options = build_qa_options(
            export_preset=str(payload.export_preset),
            max_bubble_panel_coverage=payload.max_bubble_panel_coverage,
        )
        return PageQAService(session, provider).run_page_qa(page_id, options)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc


@router.get("/pages/{page_id}/qa/latest", response_model=QAReportRead)
def get_latest_page_qa(page_id: uuid.UUID, session: Session = Depends(get_session)) -> QAReport:
    require_page_access(session, page_id)

    report = latest_qa_report(session, "page", page_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA report not found")
    return report


@router.post("/qa/{report_id}/apply-fix", response_model=QAAutoFixResult)
def apply_qa_fix(
    report_id: uuid.UUID,
    payload: QAAutoFixRequest | None = None,
    session: Session = Depends(get_session),
    storage=Depends(get_object_storage),
) -> dict:
    payload = payload or QAAutoFixRequest()
    require_qa_report_access(session, report_id)
    try:
        return AutoFixService(session, storage).apply_report_fix(
            report_id,
            issue_id=payload.issue_id,
            issue_code=payload.issue_code,
            safe_only=payload.safe_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/pages/{page_id}/qa/auto-fix-safe", response_model=QAAutoFixResult)
def auto_fix_page_safe(
    page_id: uuid.UUID,
    session: Session = Depends(get_session),
    storage=Depends(get_object_storage),
) -> dict:
    require_page_access(session, page_id)
    try:
        return AutoFixService(session, storage).auto_fix_page_safe(page_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/projects/{project_id}/qa/run-full", response_model=QAProjectRunResult, status_code=status.HTTP_201_CREATED)
def run_project_qa(
    project_id: uuid.UUID,
    payload: QARequest | None = None,
    session: Session = Depends(get_session),
    storage=Depends(get_object_storage),
) -> dict:
    require_project_access(session, project_id)
    payload = payload or QARequest()
    options = build_qa_options(
        export_preset=str(payload.export_preset),
        max_bubble_panel_coverage=payload.max_bubble_panel_coverage,
    )
    try:
        project_report, page_reports = AutoFixService(session, storage).run_project_full(project_id, options)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"project_report": project_report, "page_reports": page_reports}
