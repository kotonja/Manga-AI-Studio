import uuid

from sqlmodel import Session

from manga_api.config import get_settings
from manga_api.main import app
from manga_api.models import FeedbackItem, GenerationJob


def test_protected_admin_routes_require_auth_or_dev_flag(client, monkeypatch) -> None:
    get_settings.cache_clear()
    response = client.get("/admin/ai-task-runs")
    assert response.status_code == 404

    monkeypatch.setenv("ENABLE_DEV_ADMIN", "true")
    get_settings.cache_clear()
    response = client.get("/admin/ai-task-runs")
    assert response.status_code == 200
    assert response.json() == []

    monkeypatch.delenv("ENABLE_DEV_ADMIN", raising=False)
    get_settings.cache_clear()


def test_onboarding_route_loads(client) -> None:
    response = client.get("/alpha/onboarding")
    assert response.status_code == 200
    payload = response.json()
    assert payload["welcome_title"] == "Welcome to Manga AI Studio Alpha"
    assert payload["first_demo_premise"] == "A lonely swordsman protects a ghost child in a ruined city."
    assert {mode["id"] for mode in payload["provider_modes"]} == {"mock", "real"}


def test_feedback_submission_works(client) -> None:
    project = client.post("/projects", json={"name": "Alpha Feedback", "description": "Testing feedback"}).json()
    response = client.post(
        "/feedback",
        json={
            "project_id": project["id"],
            "category": "bug",
            "severity": "high",
            "title": "Export button confused me",
            "description": "I could not tell whether the export was mock or real.",
            "contact_email": "tester@example.com",
            "browser_info": {"userAgent": "pytest", "token": "secret-value"},
            "context": {"pathname": "/projects/demo/publishing"},
            "diagnostic_info": {"request_id": "alpha-test"},
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["project_id"] == project["id"]
    assert payload["status"] == "open"
    assert payload["browser_info"]["token"] == "[redacted]"

    with Session(app.state.engine) as session:
        stored = session.get(FeedbackItem, uuid.UUID(payload["id"]))
        assert stored is not None
        assert stored.title == "Export button confused me"


def test_failed_render_job_retry_works(client) -> None:
    project = client.post("/projects", json={"name": "Retry Project", "description": "Retry smoke"}).json()
    page = client.post(f"/projects/{project['id']}/pages", json={"width": 640, "height": 960}).json()
    panel = client.post(
        f"/pages/{page['id']}/panels",
        json={"x": 80, "y": 100, "width": 260, "height": 220, "reading_order": 1, "prompt": "Retry panel"},
    ).json()

    with Session(app.state.engine) as session:
        failed = GenerationJob(
            project_id=uuid.UUID(project["id"]),
            page_id=uuid.UUID(page["id"]),
            panel_id=uuid.UUID(panel["id"]),
            provider="openai",
            job_type="render_panel",
            status="failed",
            input_payload={
                "panel_id": panel["id"],
                "page_id": page["id"],
                "provider": "openai",
                "options": {"quality_mode": "draft"},
            },
            output_payload={"error_metadata": {"provider": "openai", "safe_message": "Missing key"}},
            error_message="openai is not configured",
        )
        session.add(failed)
        session.commit()
        session.refresh(failed)
        failed_id = str(failed.id)

    response = client.post(f"/jobs/{failed_id}/retry", json={"provider_name": "mock", "use_mock_fallback": True})
    assert response.status_code == 202
    payload = response.json()
    assert payload["source_job_id"] == failed_id
    assert payload["job"]["provider"] == "mock"
    assert payload["job"]["status"] == "succeeded"
    assert payload["job"]["output_payload"]["asset_id"]
