import json
import zipfile
from io import BytesIO


def test_provenance_created_for_mock_render(client) -> None:
    _project, _page, panel = create_project_page_panel(client)

    render_response = client.post(
        f"/panels/{panel['id']}/render",
        json={"provider_name": "mock", "render_mode": "draft", "seed": 77},
    )
    assert render_response.status_code == 202
    job = render_response.json()["job"]
    assert job["status"] == "succeeded"
    asset_id = job["output_payload"]["asset_id"]

    provenance_response = client.get(f"/assets/{asset_id}/provenance")
    assert provenance_response.status_code == 200
    provenance = provenance_response.json()
    assert provenance["source_type"] == "internal_mock"
    assert provenance["provider_name"] == "mock"
    assert provenance["model_name"] == "mock-image-v1"
    assert provenance["generation_job_id"] == job["id"]
    assert provenance["ai_disclosure_required"] is True


def test_uploaded_asset_requires_rights_declaration(client) -> None:
    project = client.post("/projects", json={"name": "Rights Gate"}).json()
    character = client.post(f"/projects/{project['id']}/characters", json={"name": "Mira"}).json()

    blocked = client.post(
        f"/characters/{character['id']}/reference-assets",
        json={
            "filename": "mira-ref.png",
            "content_type": "image/png",
            "size_bytes": 200,
            "metadata_json": {"source": "test"},
        },
    )
    assert blocked.status_code == 409
    assert "Upload rights declaration is required" in blocked.json()["detail"]

    declaration = client.put(
        f"/projects/{project['id']}/rights-declaration",
        json={
            "user_confirms_upload_rights": True,
            "user_confirms_no_unlicensed_ip": True,
            "user_confirms_review_required_before_publish": True,
            "notes": "Uploaded references are owned by the test user.",
        },
    )
    assert declaration.status_code == 200

    created = client.post(
        f"/characters/{character['id']}/reference-assets",
        json={
            "filename": "mira-ref.png",
            "content_type": "image/png",
            "size_bytes": 200,
            "metadata_json": {"source": "test", "license_type": "creator_owned"},
        },
    )
    assert created.status_code == 201
    generic_asset_id = created.json()["metadata_json"]["asset_id"]

    provenance = client.get(f"/assets/{generic_asset_id}/provenance").json()
    assert provenance["source_type"] == "user_upload"
    assert provenance["license_type"] == "creator_owned"
    assert provenance["uploaded_filename"] == "mira-ref.png"


def test_risky_style_prompt_warning(client) -> None:
    response = client.post(
        "/safety/check",
        json={
            "target": "style_request",
            "text": "Make this exactly like Naruto with the same franchise look.",
            "metadata": {},
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["allowed"] is False
    assert result["severity"] == "blocked"
    codes = {issue["code"] for issue in result["issues"]}
    assert "risky_phrase_make_exactly_like" in codes
    assert "franchise_reference" in codes
    assert "self-contained original design system" in result["suggested_text"]


def test_zip_export_includes_provenance_files(client) -> None:
    project, page, panel = create_project_page_panel(client)
    render = client.post(f"/panels/{panel['id']}/render", json={"provider_name": "mock", "render_mode": "draft"})
    assert render.status_code == 202
    compose = client.post(f"/pages/{page['id']}/compose")
    assert compose.status_code == 201

    export_response = client.post(
        f"/projects/{project['id']}/exports",
        json={"format": "zip", "force": True, "options": {"source": "provenance_test"}},
    )
    assert export_response.status_code == 201
    export = export_response.json()
    assert export["status"] == "succeeded"

    download = client.get(f"/exports/{export['id']}/download")
    assert download.status_code == 200

    with zipfile.ZipFile(BytesIO(download.content)) as archive:
        names = set(archive.namelist())
        assert "provenance.json" in names
        assert "asset-rights-summary.json" in names
        assert "ai_disclosure.txt" in names
        provenance = json.loads(archive.read("provenance.json"))
        assert provenance["summary"]["ai_disclosure_required"] is True
        assert any((item["provenance"] or {}).get("source_type") == "internal_mock" for item in provenance["assets"])


def create_project_page_panel(client):
    project = client.post("/projects", json={"name": "Provenance Project", "description": "Rights and provenance"}).json()
    page = client.post(f"/projects/{project['id']}/pages", json={"width": 640, "height": 960}).json()
    panel_response = client.post(
        f"/pages/{page['id']}/panels",
        json={
            "x": 80,
            "y": 100,
            "width": 260,
            "height": 220,
            "reading_order": 1,
            "prompt": "A lonely swordsman protects a ghost child.",
        },
    )
    assert panel_response.status_code == 201
    return project, page, panel_response.json()
