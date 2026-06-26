from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError
from sqlmodel import Session, select

from manga_api.director import MangaDirectorOrchestrator
from manga_api.models import (
    Bubble,
    CharacterCard,
    CharacterState,
    GenerationJob,
    JobEvent,
    KeyObject,
    Location,
    Page,
    PagePlan,
    Panel,
    PanelPlan,
    PanelRenderPrompt,
    Project,
    ProjectExport,
    QAReport,
    Render,
    StoryBible,
)
from manga_api.qa import MockQAProvider, PageQAService, QAOptions, latest_qa_report
from manga_api.schemas import DirectorGenerateDraftRequest, StoryBibleResult


class EvalStorage(Protocol):
    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        """Persist bytes to object storage."""

    def get_bytes(self, key: str) -> bytes:
        """Read bytes from object storage."""

    def public_url(self, key: str) -> str:
        """Return a browser-accessible URL for a stored object."""


@dataclass(frozen=True)
class EvaluationScenario:
    id: str
    name: str
    premise: str
    genre: list[str]
    tone: str
    target_audience: str
    page_count: int
    expected_character_count: int
    expected_location_count: int
    expected_key_beats: list[str]
    expected_page_types: list[str]
    export_requirements: list[str]
    reading_direction: str = "rtl"

    @property
    def expected_panel_count(self) -> int:
        return self.page_count * 2


EVALUATION_SCENARIOS: list[EvaluationScenario] = [
    EvaluationScenario(
        id="dark_fantasy_revenge",
        name="Dark Fantasy Revenge",
        premise="A betrayed knight hunts the cursed monarch who stole her name.",
        genre=["dark fantasy", "revenge"],
        tone="Grim, mythic, and emotionally severe",
        target_audience="Older teen manga readers",
        page_count=8,
        expected_character_count=2,
        expected_location_count=1,
        expected_key_beats=[
            "betrayal wound",
            "cursed monarch",
            "revenge vow",
            "cost of vengeance",
        ],
        expected_page_types=["standard", "reveal_page", "action_sequence", "horror_build"],
        export_requirements=["zip"],
    ),
    EvaluationScenario(
        id="school_romance_confession",
        name="School Romance Confession",
        premise="Two awkward classmates race the closing festival gates to confess before graduation.",
        genre=["school romance", "coming of age"],
        tone="Tender, nervous, and hopeful",
        target_audience="Teen romance manga readers",
        page_count=6,
        expected_character_count=2,
        expected_location_count=1,
        expected_key_beats=[
            "missed chance",
            "festival deadline",
            "mutual confession",
            "quiet acceptance",
        ],
        expected_page_types=["dialogue_scene", "romantic_pause", "reveal_page", "standard"],
        export_requirements=["zip"],
        reading_direction="ltr",
    ),
    EvaluationScenario(
        id="shonen_battle_intro",
        name="Shonen Battle Intro",
        premise="A reckless courier challenges a masked arena champion to save his neighborhood dojo.",
        genre=["shonen battle", "sports action"],
        tone="Energetic, bold, and aspirational",
        target_audience="Teen action manga readers",
        page_count=8,
        expected_character_count=2,
        expected_location_count=1,
        expected_key_beats=[
            "dojo at risk",
            "rival entrance",
            "first clash",
            "heroic resolve",
        ],
        expected_page_types=["standard", "action_sequence", "splash", "reveal_page"],
        export_requirements=["zip"],
    ),
    EvaluationScenario(
        id="horror_shrine_mystery",
        name="Horror Shrine Mystery",
        premise="A shrine caretaker finds names appearing on prayer plaques one hour before each person vanishes.",
        genre=["horror", "mystery"],
        tone="Quiet, eerie, and escalating",
        target_audience="Older teen horror manga readers",
        page_count=6,
        expected_character_count=2,
        expected_location_count=1,
        expected_key_beats=[
            "forbidden plaque",
            "first disappearance",
            "shrine secret",
            "unseen presence",
        ],
        expected_page_types=["horror_build", "silent_page", "reveal_page", "exposition_page"],
        export_requirements=["zip"],
    ),
    EvaluationScenario(
        id="comedy_slice_of_life",
        name="Comedy Slice-of-Life",
        premise="Three roommates accidentally adopt a robotic rice cooker that gives terrible life advice.",
        genre=["comedy", "slice of life"],
        tone="Warm, absurd, and fast-paced",
        target_audience="All-ages comedy manga readers",
        page_count=4,
        expected_character_count=3,
        expected_location_count=1,
        expected_key_beats=[
            "bad advice",
            "roommate chaos",
            "domestic misunderstanding",
            "unexpected kindness",
        ],
        expected_page_types=["comedy_reaction", "dialogue_scene", "standard"],
        export_requirements=["zip"],
        reading_direction="ltr",
    ),
]


def scenario_ids() -> list[str]:
    return [scenario.id for scenario in EVALUATION_SCENARIOS]


def select_scenarios(selector: str) -> list[EvaluationScenario]:
    normalized = selector.strip().lower()
    if normalized in {"", "all"}:
        return list(EVALUATION_SCENARIOS)
    matches = [scenario for scenario in EVALUATION_SCENARIOS if scenario.id == normalized]
    if not matches:
        raise ValueError(f"Unknown eval scenario '{selector}'. Expected one of: all, {', '.join(scenario_ids())}")
    return matches


class MangaEvaluationRunner:
    def __init__(self, session: Session, storage: EvalStorage, reports_dir: Path | str | None = None) -> None:
        self.session = session
        self.storage = storage
        self.reports_dir = Path(reports_dir) if reports_dir is not None else default_reports_dir()

    def run(
        self,
        *,
        scenario: str = "all",
        provider: str = "mock",
        write_reports: bool = True,
        quality_mode: str = "fast",
    ) -> dict[str, Any]:
        selected = select_scenarios(scenario)
        started_at = datetime.now(timezone.utc)
        run_started = time.perf_counter()
        scenario_reports: list[dict[str, Any]] = []

        for item in selected:
            scenario_reports.append(self._run_scenario(item, provider=provider, quality_mode=quality_mode))

        aggregate = aggregate_metrics(scenario_reports)
        report = {
            "run_id": str(uuid.uuid4()),
            "created_at": started_at.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "quality_mode": quality_mode,
            "scenario_selector": scenario,
            "scenario_count": len(scenario_reports),
            "metrics": {
                **aggregate,
                "total_generation_time": round(time.perf_counter() - run_started, 3),
                "estimated_cost": estimate_cost(scenario_reports, provider),
            },
            "scenarios": scenario_reports,
        }
        if write_reports:
            write_eval_reports(report, self.reports_dir)
        return report

    def _run_scenario(self, scenario: EvaluationScenario, *, provider: str, quality_mode: str) -> dict[str, Any]:
        started = time.perf_counter()
        failures: list[str] = []
        project = Project(
            owner_user_id="eval-runner",
            name=f"Eval - {scenario.name}",
            description=scenario.premise,
            style_prompt=f"{', '.join(scenario.genre)} manga, {scenario.tone}",
        )
        self.session.add(project)
        self.session.commit()
        self.session.refresh(project)

        request = DirectorGenerateDraftRequest(
            premise=scenario.premise,
            chapter_count=1,
            page_count=scenario.page_count,
            target_audience=scenario.target_audience,
            genre=scenario.genre,
            tone=scenario.tone,
            reading_direction=scenario.reading_direction,  # type: ignore[arg-type]
            render_provider=provider,
            quality_mode=quality_mode,  # type: ignore[arg-type]
            allow_mock_assets=True,
        )
        job = GenerationJob(
            project_id=project.id,
            provider=provider,
            job_type="eval_director_generate_draft",
            status="queued",
            input_payload={"scenario_id": scenario.id, "request": request.model_dump(mode="json")},
            output_payload={"director_state": {"project_id": str(project.id), "eval_scenario_id": scenario.id}},
        )
        self.session.add(job)
        self.session.flush()
        self.session.add(
            JobEvent(
                job_id=job.id,
                event_type="queued",
                message=f"Eval scenario queued: {scenario.name}",
                payload={"scenario_id": scenario.id},
            )
        )
        self.session.commit()
        self.session.refresh(job)

        final_job = MangaDirectorOrchestrator(self.session, self.storage).generate_draft(job.id)
        if final_job.status != "succeeded":
            failures.append(final_job.error_message or "Director job failed")

        self._run_full_qa(project.id, failures)
        scenario_data = self._collect_scenario_data(project, scenario)
        scores = compute_scenario_scores(scenario, scenario_data)
        failures.extend(scenario_data["failures"])
        duration = round(time.perf_counter() - started, 3)

        return {
            "scenario": asdict(scenario),
            "project_id": str(project.id),
            "job_id": str(final_job.id),
            "status": "passed" if not failures and final_job.status == "succeeded" else "failed",
            "duration_seconds": duration,
            "scores": scores,
            "metrics": scores,
            "counts": scenario_data["counts"],
            "generated": scenario_data["generated"],
            "failures": failures,
            "links": {
                "project": f"/projects/{project.id}",
                "story": f"/projects/{project.id}/story",
                "publishing": f"/projects/{project.id}/publishing",
            },
        }

    def _run_full_qa(self, project_id: uuid.UUID, failures: list[str]) -> None:
        pages = self.session.exec(
            select(Page)
            .where(Page.project_id == project_id)
            .order_by(Page.page_number.asc(), Page.created_at.asc())
        ).all()
        qa = PageQAService(self.session, MockQAProvider())
        for page in pages:
            try:
                qa.run_page_qa(page.id, QAOptions(export_preset="draft"))
            except Exception as exc:
                failures.append(f"QA failed for page {page.page_number}: {exc}")

    def _collect_scenario_data(self, project: Project, scenario: EvaluationScenario) -> dict[str, Any]:
        failures: list[str] = []
        pages = self.session.exec(
            select(Page)
            .where(Page.project_id == project.id)
            .order_by(Page.page_number.asc(), Page.created_at.asc())
        ).all()
        page_ids = [page.id for page in pages]
        panels = self.session.exec(
            select(Panel)
            .where(Panel.page_id.in_(page_ids))
            .order_by(Panel.reading_order.asc(), Panel.created_at.asc())
        ).all() if page_ids else []
        panel_ids = [panel.id for panel in panels]
        character_cards = self.session.exec(select(CharacterCard).where(CharacterCard.project_id == project.id)).all()
        locations = self.session.exec(select(Location).where(Location.project_id == project.id)).all()
        key_objects = self.session.exec(select(KeyObject).where(KeyObject.project_id == project.id)).all()
        renders = self.session.exec(select(Render).where(Render.panel_id.in_(panel_ids))).all() if panel_ids else []
        prompts = self.session.exec(select(PanelRenderPrompt).where(PanelRenderPrompt.panel_id.in_(panel_ids))).all() if panel_ids else []
        reports = self.session.exec(
            select(QAReport)
            .where(QAReport.page_id.in_(page_ids))
            .order_by(QAReport.created_at.asc())
        ).all() if page_ids else []
        exports = self.session.exec(select(ProjectExport).where(ProjectExport.project_id == project.id)).all()
        page_plans = self.session.exec(
            select(PagePlan)
            .where(PagePlan.project_id == project.id)
            .order_by(PagePlan.page_number.asc(), PagePlan.created_at.asc())
        ).all()
        page_plan_ids = [page_plan.id for page_plan in page_plans]
        panel_plans = self.session.exec(
            select(PanelPlan).where(PanelPlan.page_plan_id.in_(page_plan_ids))
        ).all() if page_plan_ids else []
        bubbles = self.session.exec(select(Bubble).where(Bubble.panel_id.in_(panel_ids))).all() if panel_ids else []
        states = self.session.exec(
            select(CharacterState).where(CharacterState.character_id.in_([card.id for card in character_cards]))
        ).all() if character_cards else []
        latest_reports = [latest_qa_report(self.session, "page", page.id) for page in pages]
        latest_reports = [report for report in latest_reports if report is not None]

        story_schema_valid = validate_story_schema(project, self.session, failures)
        page_type_values = [
            str((page.layout_json or {}).get("page_type") or (page.layout_json or {}).get("page_type_hint") or "")
            for page in pages
        ]
        missing_page_types = [
            page_type
            for page_type in scenario.expected_page_types
            if page_type and page_type not in page_type_values
        ]
        if missing_page_types:
            failures.append(f"Expected page type hints not present: {', '.join(missing_page_types)}")

        key_beat_text = " ".join(
            [
                project.description or "",
                *(page_plan.summary for page_plan in page_plans),
                *(panel_plan.story_beat for panel_plan in panel_plans),
                *(panel_plan.visual_notes for panel_plan in panel_plans),
            ]
        ).lower()
        missing_beats = [
            beat
            for beat in scenario.expected_key_beats
            if not beat_present(beat, key_beat_text)
        ]
        if missing_beats:
            failures.append(f"Expected key beats weak or missing: {', '.join(missing_beats)}")

        export_status_by_format = {export.format: export.status for export in exports}
        missing_exports = [
            export_format
            for export_format in scenario.export_requirements
            if export_status_by_format.get(export_format) != "succeeded"
        ]
        if missing_exports:
            failures.append(f"Required exports did not succeed: {', '.join(missing_exports)}")

        generated = {
            "page_types": page_type_values,
            "export_status_by_format": export_status_by_format,
            "latest_qa_scores": [report.overall_score for report in latest_reports],
            "missing_key_beats": missing_beats,
            "missing_page_types": missing_page_types,
            "project_name": project.name,
        }
        counts = {
            "pages": len(pages),
            "panels": len(panels),
            "characters": len(character_cards),
            "locations": len(locations),
            "key_objects": len(key_objects),
            "renders": len(renders),
            "prompts": len(prompts),
            "bubbles": len(bubbles),
            "character_states": len(states),
            "compositions": count_composites(self.session, project.id),
            "qa_reports": len(latest_reports),
            "blocking_qa_issues": sum(1 for report in latest_reports if report.blocking),
            "exports_succeeded": sum(1 for export in exports if export.status == "succeeded"),
        }
        return {
            "counts": counts,
            "generated": generated,
            "story_schema_valid": story_schema_valid,
            "failures": failures,
            "panels": panels,
            "prompts": prompts,
            "reports": latest_reports,
            "exports": exports,
            "character_cards": character_cards,
        }


def validate_story_schema(project: Project, session: Session, failures: list[str]) -> bool:
    story = session.exec(
        select(StoryBible)
        .where(StoryBible.project_id == project.id)
        .order_by(StoryBible.created_at.desc())
    ).first()
    if story is None:
        failures.append("Story bible was not generated")
        return False

    characters = session.exec(select(CharacterCard).where(CharacterCard.project_id == project.id)).all()
    locations = session.exec(select(Location).where(Location.project_id == project.id)).all()
    key_objects = session.exec(select(KeyObject).where(KeyObject.project_id == project.id)).all()
    try:
        StoryBibleResult.model_validate(
            {
                "id": story.id,
                "project_id": project.id,
                "logline": story.logline,
                "synopsis": story.synopsis,
                "genre": story.genre,
                "themes": story.themes,
                "target_audience": story.target_audience,
                "tone": story.tone,
                "main_conflict": story.main_conflict,
                "world_rules": story.world_rules,
                "characters": [
                    {
                        "name": card.name,
                        "role": card.role or "character",
                        "description": card.personality or card.canonical_visual_summary or card.role or card.name,
                        "traits": card.aliases,
                        "visual_notes": card.canonical_visual_summary or card.outfit_default,
                    }
                    for card in characters
                ],
                "locations": [
                    {
                        "name": location.name,
                        "description": location.description,
                        "visual_notes": location.visual_notes,
                        "rules": location.rules,
                    }
                    for location in locations
                ],
                "key_objects": [
                    {
                        "name": key_object.name,
                        "description": key_object.description,
                        "significance": key_object.significance,
                        "visual_notes": key_object.visual_notes,
                    }
                    for key_object in key_objects
                ],
                "chapter_outline": story.chapter_outline,
                "continuity_rules": story.continuity_rules,
            }
        )
        return True
    except ValidationError as exc:
        failures.append(f"Story schema validation failed: {exc.errors()[0]['msg'] if exc.errors() else exc}")
        return False


def compute_scenario_scores(scenario: EvaluationScenario, data: dict[str, Any]) -> dict[str, float | int]:
    counts = data["counts"]
    panels: list[Panel] = data["panels"]
    prompts: list[PanelRenderPrompt] = data["prompts"]
    reports: list[QAReport] = data["reports"]
    character_cards: list[CharacterCard] = data["character_cards"]
    exports: list[ProjectExport] = data["exports"]

    prompt_anchor_coverage = coverage(
        count_prompts_with_character_anchors(prompts, character_cards),
        len(panels),
    )
    lettering_scores = [readability_from_report(report) for report in reports]
    export_successes = sum(
        1
        for export_format in scenario.export_requirements
        if any(export.format == export_format and export.status == "succeeded" for export in exports)
    )
    return {
        "pipeline_completion_rate": 1.0 if counts["pages"] > 0 and counts["exports_succeeded"] > 0 else 0.0,
        "story_schema_validity": 1.0 if data["story_schema_valid"] else 0.0,
        "page_count_accuracy": ratio_accuracy(counts["pages"], scenario.page_count),
        "panel_count_accuracy": ratio_accuracy(counts["panels"], scenario.expected_panel_count),
        "character_state_coverage": coverage(counts["character_states"], max(1, len(character_cards))),
        "prompt_anchor_coverage": prompt_anchor_coverage,
        "render_asset_coverage": coverage(counts["renders"], max(1, counts["panels"])),
        "composition_success_rate": coverage(counts["compositions"], max(1, counts["pages"])),
        "lettering_readability_score": round(sum(lettering_scores) / len(lettering_scores), 3) if lettering_scores else 0.0,
        "qa_blocking_issue_count": counts["blocking_qa_issues"],
        "export_success_rate": coverage(export_successes, max(1, len(scenario.export_requirements))),
    }


def aggregate_metrics(scenario_reports: list[dict[str, Any]]) -> dict[str, float | int]:
    metric_names = [
        "pipeline_completion_rate",
        "story_schema_validity",
        "page_count_accuracy",
        "panel_count_accuracy",
        "character_state_coverage",
        "prompt_anchor_coverage",
        "render_asset_coverage",
        "composition_success_rate",
        "lettering_readability_score",
        "export_success_rate",
    ]
    aggregate: dict[str, float | int] = {}
    for name in metric_names:
        values = [float(report["scores"].get(name, 0.0)) for report in scenario_reports]
        aggregate[name] = round(sum(values) / len(values), 3) if values else 0.0
    aggregate["qa_blocking_issue_count"] = sum(int(report["scores"].get("qa_blocking_issue_count", 0)) for report in scenario_reports)
    return aggregate


def count_prompts_with_character_anchors(prompts: list[PanelRenderPrompt], cards: list[CharacterCard]) -> int:
    if not prompts:
        return 0
    anchor_values = []
    for card in cards:
        anchor_values.extend(
            [
                card.name,
                card.face_anchor_description,
                card.hair_anchor_description,
                card.eye_anchor_description,
                card.outfit_anchor_description,
                card.face_description,
                card.hair_description,
                card.eye_description,
                card.outfit_default,
            ]
        )
    anchors = [value.lower() for value in anchor_values if value and value.strip()]
    if not anchors:
        return 0
    hits = 0
    for prompt in prompts:
        text = f"{prompt.positive_prompt} {json.dumps(prompt.structured_context, default=str)}".lower()
        if any(anchor in text for anchor in anchors):
            hits += 1
    return hits


def readability_from_report(report: QAReport) -> float:
    lettering_score = report.scores.get("lettering") if isinstance(report.scores, dict) else None
    if isinstance(lettering_score, (int, float)):
        return max(0.0, min(1.0, float(lettering_score) / 100.0))
    lettering_issues = [
        issue
        for issue in report.issues
        if issue.get("category") == "lettering" or issue.get("issue_category") == "lettering"
    ]
    return max(0.0, 1.0 - len(lettering_issues) * 0.2)


def count_composites(session: Session, project_id: uuid.UUID) -> int:
    from manga_api.models import Asset

    return len(
        session.exec(
            select(Asset)
            .where(Asset.project_id == project_id, Asset.kind == "page_composite")
        ).all()
    )


def ratio_accuracy(actual: int, expected: int) -> float:
    if expected <= 0:
        return 1.0 if actual == expected else 0.0
    return round(max(0.0, 1.0 - abs(actual - expected) / expected), 3)


def coverage(actual: int, expected: int) -> float:
    if expected <= 0:
        return 1.0
    return round(max(0.0, min(1.0, actual / expected)), 3)


def beat_present(beat: str, text: str) -> bool:
    words = [word.strip(".,:;!?").lower() for word in beat.split() if len(word.strip(".,:;!?")) > 3]
    if not words:
        return beat.lower() in text
    return sum(1 for word in words if word in text) >= max(1, len(words) // 2)


def estimate_cost(scenario_reports: list[dict[str, Any]], provider: str) -> float | None:
    if provider == "mock":
        return 0.0
    costs: list[float] = []
    for report in scenario_reports:
        cost = report.get("generated", {}).get("estimated_cost")
        if isinstance(cost, (int, float)):
            costs.append(float(cost))
    return round(sum(costs), 4) if costs else None


def write_eval_reports(report: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "latest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )
    (reports_dir / "latest.md").write_text(render_markdown_report(report), encoding="utf-8")


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Manga AI Studio Evaluation Report",
        "",
        f"- Run: `{report['run_id']}`",
        f"- Created: {report['created_at']}",
        f"- Provider: `{report['provider']}`",
        f"- Quality mode: `{report['quality_mode']}`",
        f"- Scenarios: {report['scenario_count']}",
        "",
        "## Aggregate Metrics",
        "",
    ]
    for key, value in report["metrics"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Scenario Results", ""])
    for scenario_report in report["scenarios"]:
        scenario = scenario_report["scenario"]
        lines.extend(
            [
                f"### {scenario['name']}",
                "",
                f"- Status: `{scenario_report['status']}`",
                f"- Project: `{scenario_report['project_id']}`",
                f"- Duration: {scenario_report['duration_seconds']}s",
                "",
                "| Metric | Value |",
                "| --- | ---: |",
            ]
        )
        for key, value in scenario_report["scores"].items():
            lines.append(f"| `{key}` | {value} |")
        if scenario_report["failures"]:
            lines.extend(["", "Failures:"])
            for failure in scenario_report["failures"]:
                lines.append(f"- {failure}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def default_reports_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "eval_reports"
