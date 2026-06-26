from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from manga_api.db import get_session
from manga_api.evaluation import EVALUATION_SCENARIOS, MangaEvaluationRunner
from manga_api.models import EvalMetricSnapshot, EvalRun
from manga_api.schemas import EvalRunReport, EvalRunRequest, EvalScenarioRead
from manga_api.storage import ObjectStorage, get_object_storage

router = APIRouter(prefix="/eval", tags=["evaluation"])


@router.get("/scenarios", response_model=list[EvalScenarioRead])
def list_eval_scenarios() -> list[dict]:
    return [
        {
            **asdict(scenario),
            "expected_panel_count": scenario.expected_panel_count,
        }
        for scenario in EVALUATION_SCENARIOS
    ]


@router.post("/run", response_model=EvalRunReport, status_code=status.HTTP_201_CREATED)
def run_evaluation(
    payload: EvalRunRequest,
    session: Session = Depends(get_session),
    storage: ObjectStorage = Depends(get_object_storage),
) -> dict:
    try:
        report = MangaEvaluationRunner(session, storage).run(
            scenario=payload.scenario,
            provider=payload.provider,
            quality_mode=payload.quality_mode,
            write_reports=payload.write_reports,
        )
        persist_eval_report(session, payload, report)
        return report
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def persist_eval_report(session: Session, payload: EvalRunRequest, report: dict) -> None:
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    eval_run = EvalRun(
        name=f"{payload.scenario}:{payload.provider}:{payload.quality_mode}",
        scenario=payload.scenario,
        provider=payload.provider,
        status="succeeded",
        metrics=metrics,
        report_path="eval_reports/latest.json" if payload.write_reports else None,
    )
    session.add(eval_run)
    session.flush()
    for metric_name, metric_value in metrics.items():
        if isinstance(metric_value, (int, float)):
            session.add(
                EvalMetricSnapshot(
                    eval_run_id=eval_run.id,
                    metric_name=metric_name,
                    metric_value=float(metric_value),
                    dimensions={"scenario": payload.scenario, "provider": payload.provider, "quality_mode": payload.quality_mode},
                )
            )
    session.commit()
