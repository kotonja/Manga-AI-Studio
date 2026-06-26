from __future__ import annotations

from manga_api.evaluation import EVALUATION_SCENARIOS, MangaEvaluationRunner
from manga_api.db import get_session
from manga_api.storage import get_object_storage


EXPECTED_METRICS = {
    "pipeline_completion_rate",
    "story_schema_validity",
    "page_count_accuracy",
    "panel_count_accuracy",
    "character_state_coverage",
    "prompt_anchor_coverage",
    "render_asset_coverage",
    "composition_success_rate",
    "lettering_readability_score",
    "qa_blocking_issue_count",
    "export_success_rate",
    "total_generation_time",
    "estimated_cost",
}


def test_eval_scenarios_are_defined() -> None:
    assert [scenario.id for scenario in EVALUATION_SCENARIOS] == [
        "dark_fantasy_revenge",
        "school_romance_confession",
        "shonen_battle_intro",
        "horror_shrine_mystery",
        "comedy_slice_of_life",
    ]
    for scenario in EVALUATION_SCENARIOS:
        assert scenario.premise
        assert scenario.genre
        assert scenario.tone
        assert scenario.target_audience
        assert scenario.page_count > 0
        assert scenario.expected_character_count > 0
        assert scenario.expected_location_count > 0
        assert scenario.expected_key_beats
        assert scenario.expected_page_types
        assert scenario.export_requirements


def test_eval_runner_works_with_mock_provider(client, tmp_path) -> None:
    session_generator = client.app.dependency_overrides[get_session]()
    session = next(session_generator)
    try:
        storage = client.app.dependency_overrides[get_object_storage]()
        report = MangaEvaluationRunner(session, storage, reports_dir=tmp_path).run(
            scenario="comedy_slice_of_life",
            provider="mock",
            write_reports=True,
        )
    finally:
        session_generator.close()

    assert report["scenario_count"] == 1
    assert set(report["metrics"]).issuperset(EXPECTED_METRICS)
    assert report["metrics"]["estimated_cost"] == 0.0
    assert report["scenarios"][0]["scenario"]["id"] == "comedy_slice_of_life"
    assert "page_count_accuracy" in report["scenarios"][0]["scores"]
    assert (tmp_path / "latest.json").exists()
    assert (tmp_path / "latest.md").exists()


def test_eval_run_endpoint_returns_report(client) -> None:
    response = client.post(
        "/eval/run",
        json={"scenario": "comedy_slice_of_life", "provider": "mock", "write_reports": False},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["scenario_count"] == 1
    assert set(payload["metrics"]).issuperset(EXPECTED_METRICS)
    assert payload["scenarios"][0]["project_id"]
