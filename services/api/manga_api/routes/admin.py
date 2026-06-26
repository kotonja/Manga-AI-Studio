from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, select

from manga_api.ai_tasks import PromptRegistry, list_recent_ai_task_runs
from manga_api.auth import require_admin_access
from manga_api.db import get_session
from manga_api.models import AITaskRun, FeedbackItem, GenerationFeedback, GenerationJob, Project, ProjectExport, PromptTemplate, QAReport
from manga_api.schemas import AlphaDashboardMetric, AlphaDashboardRead, AITaskRunRead, FeedbackRead, FeedbackTriageUpdate, GenerationJobRead, ImprovementReportRead, PromptTemplateRead, QAReportRead

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_access)])


@router.get("/ai-task-runs", response_model=list[AITaskRunRead])
def get_ai_task_runs(
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[AITaskRun]:
    return list_recent_ai_task_runs(session, limit)


@router.get("/prompt-templates", response_model=list[PromptTemplateRead])
def get_prompt_templates(session: Session = Depends(get_session)) -> list[PromptTemplate]:
    registry = PromptRegistry()
    for template in registry.load_all():
        row = session.get(PromptTemplate, template.id)
        if row is None:
            row = PromptTemplate(id=template.id)
        row.name = template.name
        row.version = template.version
        row.task_type = template.task_type
        row.system_prompt = template.system_prompt
        row.user_prompt_template = template.user_prompt_template
        row.output_schema_name = template.output_schema_name
        row.default_options = template.default_options
        row.safety_notes = template.safety_notes
        row.changelog = template.changelog
        session.add(row)
    session.commit()
    return list(
        session.exec(
            select(PromptTemplate).order_by(PromptTemplate.task_type.asc(), PromptTemplate.version.desc())
        ).all()
    )


@router.get("/alpha-dashboard", response_model=AlphaDashboardRead)
def get_alpha_dashboard(session: Session = Depends(get_session)) -> AlphaDashboardRead:
    failed_jobs = list(
        session.exec(
            select(GenerationJob)
            .where(GenerationJob.status == "failed")
            .order_by(GenerationJob.updated_at.desc(), GenerationJob.id.desc())
            .limit(10)
        ).all()
    )
    provider_errors = [
        job
        for job in failed_jobs
        if isinstance(job.output_payload, dict) and job.output_payload.get("error_metadata")
    ][:10]
    feedback_items = list(
        session.exec(
            select(FeedbackItem)
            .order_by(FeedbackItem.created_at.desc(), FeedbackItem.id.desc())
            .limit(10)
        ).all()
    )
    recent_qa_failures = list(
        session.exec(
            select(QAReport)
            .where(QAReport.blocking == True)  # noqa: E712
            .order_by(QAReport.created_at.desc(), QAReport.id.desc())
            .limit(10)
        ).all()
    )
    project_count = count_rows(session, Project.id)
    export_count = count_rows(session, ProjectExport.id)
    failed_job_count = count_rows(session, GenerationJob.id, GenerationJob.status == "failed")
    open_feedback_count = count_rows(session, FeedbackItem.id, FeedbackItem.status.in_(["new", "open"]))
    provider_error_count = len(provider_errors)
    blocking_qa_count = count_rows(session, QAReport.id, QAReport.blocking == True)  # noqa: E712
    return AlphaDashboardRead(
        metrics=[
            AlphaDashboardMetric(label="Projects", value=project_count, detail="Total tester workspaces"),
            AlphaDashboardMetric(label="Exports", value=export_count, detail="Created export records"),
            AlphaDashboardMetric(label="Failed jobs", value=failed_job_count, detail="Jobs needing retry or triage"),
            AlphaDashboardMetric(label="Provider errors", value=provider_error_count, detail="Recent safe provider failures"),
            AlphaDashboardMetric(label="Open feedback", value=open_feedback_count, detail="Tester reports awaiting review"),
            AlphaDashboardMetric(label="Blocking QA", value=blocking_qa_count, detail="Recent publish blockers"),
        ],
        failed_jobs=[GenerationJobRead.model_validate(job) for job in failed_jobs],
        provider_errors=[GenerationJobRead.model_validate(job) for job in provider_errors],
        feedback_items=[FeedbackRead.model_validate(item) for item in feedback_items],
        recent_qa_failures=[QAReportRead.model_validate(report) for report in recent_qa_failures],
    )


@router.get("/feedback", response_model=list[FeedbackRead])
def get_feedback_items(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[FeedbackItem]:
    statement = select(FeedbackItem).order_by(FeedbackItem.created_at.desc(), FeedbackItem.id.desc()).limit(limit)
    if status_filter:
        statement = statement.where(FeedbackItem.status == status_filter)
    return list(session.exec(statement).all())


@router.patch("/feedback/{feedback_id}", response_model=FeedbackRead)
def update_feedback_item(
    feedback_id: uuid.UUID,
    payload: FeedbackTriageUpdate,
    session: Session = Depends(get_session),
) -> FeedbackItem:
    item = session.get(FeedbackItem, feedback_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback item not found")
    if payload.status is not None:
        item.status = "new" if payload.status == "open" else payload.status
    if payload.severity is not None:
        item.severity = "blocker" if payload.severity == "blocking" else payload.severity
    if payload.internal_notes is not None:
        item.internal_notes = payload.internal_notes.strip()
    item.updated_at = datetime.now(timezone.utc)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("/improvement-report", response_model=ImprovementReportRead)
def get_improvement_report(session: Session = Depends(get_session)) -> ImprovementReportRead:
    jobs = list(session.exec(select(GenerationJob)).all())
    exports = list(session.exec(select(ProjectExport)).all())
    qa_reports = list(session.exec(select(QAReport)).all())
    allowed_feedback = list(
        session.exec(
            select(GenerationFeedback)
            .where(GenerationFeedback.allow_use_for_product_improvement == True)  # noqa: E712
            .order_by(GenerationFeedback.created_at.desc())
        ).all()
    )

    total_jobs = len(jobs)
    succeeded_jobs = sum(1 for job in jobs if job.status == "succeeded")
    failed_jobs = sum(1 for job in jobs if job.status == "failed")
    retry_jobs = sum(1 for job in jobs if job_was_retry(job))
    generation_success_rate = ratio(succeeded_jobs, total_jobs)
    retry_rate = ratio(retry_jobs, total_jobs)

    provider_totals = Counter(job.provider for job in jobs)
    provider_failures = Counter(job.provider for job in jobs if job.status == "failed")
    provider_failure_rate = {
        provider: ratio(provider_failures[provider], provider_totals[provider])
        for provider in sorted(provider_totals)
    }
    provider_reliability = [
        {
            "provider": provider,
            "success_rate": round(1 - provider_failure_rate[provider], 4),
            "failed": provider_failures[provider],
            "total": provider_totals[provider],
        }
        for provider in sorted(provider_totals)
    ]

    qa_category_counts = Counter()
    page_scores: list[int] = []
    blocking_qa_count = 0
    for report in qa_reports:
        if report.blocking:
            blocking_qa_count += 1
        if report.target_type == "page":
            page_scores.append(report.overall_score)
        if report.issue_category:
            qa_category_counts[str(report.issue_category)] += 1
        for issue in report.issues or []:
            category = issue.get("category") or issue.get("issue_category") or issue.get("code")
            if category:
                qa_category_counts[str(category)] += 1

    export_success_rate = ratio(sum(1 for export in exports if export.status == "succeeded"), len(exports))
    preset_rates = export_preset_success_rates(exports)
    feedback_failures = Counter(
        feedback.issue_type or "unspecified"
        for feedback in allowed_feedback
        if feedback.rating < 0 or feedback.issue_type
    )
    most_common_failures = [
        {"issue_type": issue_type, "count": count}
        for issue_type, count in feedback_failures.most_common(8)
    ]

    stage_scores = {
        "generation": generation_success_rate,
        "provider": 1 - ratio(sum(provider_failures.values()), sum(provider_totals.values())),
        "qa": 1 - ratio(blocking_qa_count, len(qa_reports)),
        "export": export_success_rate,
    }
    worst_stage = min(stage_scores, key=stage_scores.get) if stage_scores else "insufficient data"
    return ImprovementReportRead(
        generated_at=datetime.now(timezone.utc),
        privacy_note="Aggregates only. Private prompts, story text, images, and corrections are excluded unless explicitly opted in.",
        generation_success_rate=round(generation_success_rate, 4),
        retry_rate=round(retry_rate, 4),
        provider_failure_rate={key: round(value, 4) for key, value in provider_failure_rate.items()},
        qa_failure_categories=dict(qa_category_counts.most_common(12)),
        average_page_qa_score=round(sum(page_scores) / len(page_scores), 2) if page_scores else None,
        export_success_rate=round(export_success_rate, 4),
        most_common_failures=most_common_failures,
        worst_performing_pipeline_stage=worst_stage,
        best_performing_style_or_preset=best_preset(preset_rates),
        qa_trends={
            "blocking_report_count": blocking_qa_count,
            "page_report_count": len(page_scores),
            "latest_page_scores": page_scores[-12:],
        },
        provider_reliability=provider_reliability,
        recommended_engineering_priorities=recommend_priorities(worst_stage, feedback_failures, qa_category_counts, provider_failure_rate),
    )


def count_rows(session: Session, column, *criteria) -> int:
    statement = select(func.count(column))
    for criterion in criteria:
        statement = statement.where(criterion)
    return int(session.exec(statement).one())


def ratio(numerator: int | float, denominator: int | float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def job_was_retry(job: GenerationJob) -> bool:
    payload = job.input_payload if isinstance(job.input_payload, dict) else {}
    options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    return bool(options.get("retry_of_job_id") or options.get("retry_from_provider"))


def export_preset_success_rates(exports: list[ProjectExport]) -> dict[str, dict[str, int]]:
    rates: dict[str, dict[str, int]] = {}
    for export in exports:
        options = export.options if isinstance(export.options, dict) else {}
        preset = str(options.get("preset_id") or options.get("preset") or export.format or "unknown")
        row = rates.setdefault(preset, {"total": 0, "succeeded": 0})
        row["total"] += 1
        if export.status == "succeeded":
            row["succeeded"] += 1
    return rates


def best_preset(rates: dict[str, dict[str, int]]) -> str | None:
    if not rates:
        return None
    preset, values = max(rates.items(), key=lambda item: (ratio(item[1]["succeeded"], item[1]["total"]), item[1]["total"]))
    return f"{preset} ({values['succeeded']}/{values['total']} succeeded)"


def recommend_priorities(
    worst_stage: str,
    feedback_failures: Counter[str],
    qa_category_counts: Counter[str],
    provider_failure_rate: dict[str, float],
) -> list[str]:
    priorities: list[str] = []
    if worst_stage != "insufficient data":
        priorities.append(f"Improve the {worst_stage} stage first; it is currently the weakest aggregate signal.")
    if feedback_failures:
        issue, count = feedback_failures.most_common(1)[0]
        priorities.append(f"Address tester-reported '{issue}' issues; {count} opted-in reports mention this failure.")
    if qa_category_counts:
        category, count = qa_category_counts.most_common(1)[0]
        priorities.append(f"Reduce QA failures in '{category}'; it appears {count} times in deterministic reports.")
    provider_failures = [(provider, rate) for provider, rate in provider_failure_rate.items() if rate > 0]
    if provider_failures:
        provider, rate = max(provider_failures, key=lambda item: item[1])
        priorities.append(f"Harden {provider} provider handling; failure rate is {rate:.0%}.")
    if not priorities:
        priorities.append("Collect more opted-in ratings and eval snapshots before prioritizing larger product changes.")
    return priorities[:5]
