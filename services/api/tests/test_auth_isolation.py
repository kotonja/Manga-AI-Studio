import uuid

from sqlmodel import Session

from manga_api.config import get_settings
from manga_api.main import app
from manga_api.models import Asset, ProjectExport


USER_A = {"X-Alpha-Token": "token-a"}
USER_B = {"X-Alpha-Token": "token-b"}
ADMIN = {"X-Alpha-Token": "admin-token"}


def enable_alpha(monkeypatch) -> None:
    monkeypatch.setenv("ALPHA_AUTH_ENABLED", "true")
    monkeypatch.setenv("ALPHA_USER_TOKENS", "user-a:token-a,user-b:token-b")
    monkeypatch.setenv("ALPHA_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("ENABLE_DEV_ADMIN", "false")
    monkeypatch.setenv("APP_ENV", "alpha")
    get_settings.cache_clear()


def create_rendered_export(client) -> dict:
    project = client.post("/projects", headers=USER_A, json={"name": "A Project", "description": "Owned by A"}).json()
    page = client.post(f"/projects/{project['id']}/pages", headers=USER_A, json={"width": 640, "height": 960}).json()
    panel = client.post(
        f"/pages/{page['id']}/panels",
        headers=USER_A,
        json={"x": 40, "y": 60, "width": 520, "height": 360, "prompt": "A protects the lantern"},
    ).json()
    render_job = client.post("/jobs/mock-render-panel", headers=USER_A, json={"panel_id": panel["id"]}).json()
    composite = client.post(f"/pages/{page['id']}/compose", headers=USER_A).json()
    export = client.post(
        f"/projects/{project['id']}/exports",
        headers=USER_A,
        json={"format": "zip", "force": True, "options": {"test": True}},
    ).json()
    return {
        "project": project,
        "page": page,
        "panel": panel,
        "render_job": render_job,
        "composite": composite,
        "export": export,
    }


def test_local_dev_project_owner_defaults_to_local_dev(client) -> None:
    response = client.post("/projects", json={"name": "Local Project", "description": "No auth in local dev"})
    assert response.status_code == 201
    assert response.json()["owner_user_id"] == "local-dev"


def test_alpha_requires_auth_and_isolates_projects(client, monkeypatch) -> None:
    enable_alpha(monkeypatch)

    assert client.get("/projects").status_code == 401

    project_a = client.post("/projects", headers=USER_A, json={"name": "User A", "description": "A"}).json()
    project_b = client.post("/projects", headers=USER_B, json={"name": "User B", "description": "B"}).json()
    assert project_a["owner_user_id"] == "user-a"
    assert project_b["owner_user_id"] == "user-b"

    list_a = client.get("/projects", headers=USER_A).json()
    assert [item["id"] for item in list_a] == [project_a["id"]]
    assert client.get(f"/projects/{project_a['id']}", headers=USER_A).status_code == 200
    assert client.get(f"/projects/{project_a['id']}", headers=USER_B).status_code == 404
    assert client.post(f"/projects/{project_a['id']}/pages", headers=USER_B, json={"width": 640, "height": 960}).status_code == 404


def test_alpha_session_cookie_authenticates_web_client(client, monkeypatch) -> None:
    monkeypatch.setenv("ALPHA_AUTH_ENABLED", "true")
    monkeypatch.setenv("ALPHA_SESSION_SECRET", "session-secret")
    monkeypatch.setenv("APP_ENV", "alpha")
    get_settings.cache_clear()

    assert client.post("/projects", json={"name": "No Session"}).status_code == 401
    client.cookies.set("manga_alpha_session", "session-secret")
    response = client.post("/projects", json={"name": "Session Project"})
    assert response.status_code == 201
    assert response.json()["owner_user_id"] == "alpha-user"


def test_alpha_isolates_pages_panels_jobs_exports_and_downloads(client, monkeypatch) -> None:
    enable_alpha(monkeypatch)
    created = create_rendered_export(client)
    project = created["project"]
    page = created["page"]
    panel = created["panel"]
    render_job = created["render_job"]
    export = created["export"]

    assert client.get(f"/pages/{page['id']}/layout", headers=USER_A).status_code == 200
    assert client.get(f"/pages/{page['id']}/layout", headers=USER_B).status_code == 404
    assert client.post("/jobs/mock-render-panel", headers=USER_B, json={"panel_id": panel["id"]}).status_code == 404
    assert client.get(f"/jobs/{render_job['id']}", headers=USER_B).status_code == 404
    assert client.get(f"/exports/{export['id']}", headers=USER_B).status_code == 404
    assert client.get(f"/exports/{export['id']}/download", headers=USER_A).status_code == 200
    assert client.get(f"/exports/{export['id']}/download", headers=USER_B).status_code == 404

    with Session(app.state.engine) as session:
        export_row = session.get(ProjectExport, uuid.UUID(export["id"]))
        assert export_row is not None and export_row.file_asset_id is not None
        asset = session.get(Asset, export_row.file_asset_id)
        assert asset is not None
        assert asset.project_id == uuid.UUID(project["id"])
        asset_id = str(asset.id)

    assert client.get(f"/assets/{asset_id}/download", headers=USER_A).status_code == 200
    assert client.get(f"/assets/{asset_id}/download", headers=USER_B).status_code == 404


def test_alpha_admin_routes_require_admin_token(client, monkeypatch) -> None:
    enable_alpha(monkeypatch)
    assert client.get("/admin/ai-task-runs").status_code == 401
    assert client.get("/admin/ai-task-runs", headers=USER_A).status_code == 401
    assert client.get("/admin/ai-task-runs", headers=ADMIN).status_code == 200


def test_external_auth_requires_admin_marker_for_admin_routes(client, monkeypatch) -> None:
    monkeypatch.setenv("ALPHA_AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_PROVIDER_MODE", "external")
    monkeypatch.setenv("AUTH_PROVIDER_NAME", "proxy")
    monkeypatch.setenv("AUTH_FORWARDED_USER_HEADER", "X-Authenticated-User")
    monkeypatch.setenv("ALPHA_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("APP_ENV", "alpha")
    get_settings.cache_clear()

    forwarded = {"X-Authenticated-User": "proxy-user"}
    assert client.get("/projects", headers=forwarded).status_code == 200
    assert client.get("/admin/ai-task-runs", headers=forwarded).status_code == 401
    assert client.get("/admin/ai-task-runs", headers={**forwarded, "X-Authenticated-Admin": "true"}).status_code == 200
    assert client.get("/admin/ai-task-runs", headers={**forwarded, "X-Alpha-Token": "admin-token"}).status_code == 200


def test_feedback_project_context_requires_project_access(client, monkeypatch) -> None:
    enable_alpha(monkeypatch)
    general_payload = {
        "category": "bug",
        "severity": "medium",
        "title": "General issue",
        "description": "This is not tied to a private project.",
    }
    assert client.post("/feedback", json=general_payload).status_code == 201

    project = client.post("/projects", headers=USER_A, json={"name": "Feedback Project", "description": "A"}).json()
    linked_payload = {**general_payload, "project_id": project["id"], "title": "Project issue"}
    assert client.post("/feedback", json=linked_payload).status_code == 401
    assert client.post("/feedback", headers=USER_B, json=linked_payload).status_code == 404
    assert client.post("/feedback", headers=USER_A, json=linked_payload).status_code == 201

    learning_payload = {
        "project_id": project["id"],
        "target_type": "page_layout",
        "target_id": project["id"],
        "rating": -1,
        "issue_type": "confusing layout",
        "comment": "Project-linked learning feedback should be private.",
    }
    assert client.post("/learning/feedback", json=learning_payload).status_code == 401
    assert client.post("/learning/feedback", headers=USER_B, json=learning_payload).status_code == 404
