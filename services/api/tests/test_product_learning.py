import uuid

from sqlmodel import Session, select

from manga_api.config import get_settings
from manga_api.main import app
from manga_api.models import GenerationFeedback, GenerationJob, PanelRating, ProjectExport, QAReport


def create_project_page_panel(client, *, allow_product_improvement: bool = False):
    project = client.post(
        "/projects",
        json={
            "name": "Learning Project",
            "description": "Opt-in smoke",
            "allow_product_improvement": allow_product_improvement,
        },
    ).json()
    page = client.post(f"/projects/{project['id']}/pages", json={"width": 640, "height": 960}).json()
    panel = client.post(
        f"/pages/{page['id']}/panels",
        json={"x": 80, "y": 100, "width": 260, "height": 220, "reading_order": 1, "prompt": "Learning panel"},
    ).json()
    return project, page, panel


def test_generation_feedback_saved(client) -> None:
    project, _page, panel = create_project_page_panel(client, allow_product_improvement=True)
    response = client.post(
        "/learning/feedback",
        json={
            "project_id": project["id"],
            "target_type": "panel_render",
            "target_id": panel["id"],
            "rating": -1,
            "issue_type": "bad hands",
            "comment": "The hand silhouette broke.",
            "user_correction": "Keep the sword hand simple and gloved.",
            "allow_use_for_product_improvement": True,
            "metadata_json": {"api_key": "secret"},
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["allow_use_for_product_improvement"] is True
    assert payload["metadata_json"]["api_key"] == "[redacted]"

    with Session(app.state.engine) as session:
        feedback = session.get(GenerationFeedback, uuid.UUID(payload["id"]))
        assert feedback is not None
        assert feedback.issue_type == "bad hands"
        rating = session.exec(select(PanelRating).where(PanelRating.feedback_id == feedback.id)).first()
        assert rating is not None
        assert rating.allow_use_for_product_improvement is True


def test_project_opt_in_respected(client) -> None:
    project, _page, panel = create_project_page_panel(client, allow_product_improvement=False)
    response = client.post(
        "/learning/feedback",
        json={
            "project_id": project["id"],
            "target_type": "panel_render",
            "target_id": panel["id"],
            "rating": 1,
            "issue_type": None,
            "comment": "Looks good.",
            "allow_use_for_product_improvement": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["allow_use_for_product_improvement"] is False

    controls = client.put(
        f"/projects/{project['id']}/data-controls",
        json={
            "allow_training": False,
            "allow_product_improvement": True,
            "data_collection_notes": "Tester opted into aggregate learning.",
        },
    )
    assert controls.status_code == 200
    assert controls.json()["allow_product_improvement"] is True

    allowed = client.post(
        "/learning/feedback",
        json={
            "project_id": project["id"],
            "target_type": "panel_render",
            "target_id": panel["id"],
            "rating": -1,
            "issue_type": "wrong tone",
            "allow_use_for_product_improvement": True,
        },
    )
    assert allowed.status_code == 201
    assert allowed.json()["allow_use_for_product_improvement"] is True


def test_improvement_report_aggregates_mock_data(client, monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_DEV_ADMIN", "true")
    get_settings.cache_clear()
    project, page, panel = create_project_page_panel(client, allow_product_improvement=True)

    feedback = client.post(
        "/learning/feedback",
        json={
            "project_id": project["id"],
            "target_type": "panel_render",
            "target_id": panel["id"],
            "rating": -1,
            "issue_type": "bad face",
            "comment": "Face drifted.",
            "allow_use_for_product_improvement": True,
        },
    )
    assert feedback.status_code == 201

    with Session(app.state.engine) as session:
        project_id = uuid.UUID(project["id"])
        page_id = uuid.UUID(page["id"])
        panel_id = uuid.UUID(panel["id"])
        session.add(
            GenerationJob(
                project_id=project_id,
                page_id=page_id,
                panel_id=panel_id,
                provider="mock",
                job_type="render_panel",
                status="succeeded",
                input_payload={},
            )
        )
        session.add(
            GenerationJob(
                project_id=project_id,
                page_id=page_id,
                panel_id=panel_id,
                provider="openai",
                job_type="render_panel",
                status="failed",
                input_payload={"options": {"retry_of_job_id": str(uuid.uuid4())}},
                error_message="Provider unavailable",
            )
        )
        session.add(ProjectExport(project_id=project_id, format="archive", status="succeeded", options={"preset_id": "archive_package"}))
        session.add(ProjectExport(project_id=project_id, format="pdf", status="failed", options={"preset_id": "print_pdf"}))
        session.add(
            QAReport(
                target_type="page",
                target_id=page_id,
                page_id=page_id,
                issue_code="missing_render",
                issue_category="render",
                severity="blocking",
                overall_score=55,
                scores={"render": 0},
                issues=[{"category": "render", "message": "Missing render"}],
                recommendations=[],
                blocking=True,
            )
        )
        session.commit()

    report = client.get("/admin/improvement-report")
    assert report.status_code == 200
    payload = report.json()
    assert payload["generation_success_rate"] < 1
    assert payload["retry_rate"] > 0
    assert payload["export_success_rate"] < 1
    assert payload["average_page_qa_score"] == 55
    assert payload["qa_failure_categories"]["render"] >= 1
    assert payload["provider_failure_rate"]["openai"] == 1
    assert payload["most_common_failures"][0]["issue_type"] == "bad face"

    monkeypatch.delenv("ENABLE_DEV_ADMIN", raising=False)
    get_settings.cache_clear()
