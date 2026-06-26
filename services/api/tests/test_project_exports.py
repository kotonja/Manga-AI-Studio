import json
import uuid
import zipfile
from io import BytesIO

from PIL import Image
from sqlmodel import Session, select

from manga_api.main import app
from manga_api.models import QAReport
from manga_api.storage import get_object_storage


class MemoryObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key][0]

    def public_url(self, key: str) -> str:
        return f"http://objects.test/{key}"


def test_zip_export_includes_pages_project_json_and_respects_force(client) -> None:
    storage = MemoryObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    try:
        project, page = create_composed_project(client)
        qa_response = client.post(f"/pages/{page['id']}/qa", json={"provider_name": "mock", "export_preset": "draft"})
        assert qa_response.status_code == 201
        assert qa_response.json()["blocking"] is True

        blocked_response = client.post(
            f"/projects/{project['id']}/exports",
            json={"format": "zip", "force": False, "options": {"label": "blocked"}},
        )
        assert blocked_response.status_code == 201
        blocked = blocked_response.json()
        assert blocked["status"] == "failed"
        assert blocked["file_asset_id"] is None
        assert "Blocking QA issues" in blocked["error_message"]

        export_response = client.post(
            f"/projects/{project['id']}/exports",
            json={"format": "zip", "force": True, "options": {"label": "forced"}},
        )
        assert export_response.status_code == 201
        export = export_response.json()
        assert export["status"] == "succeeded"
        assert export["file_asset"]["content_type"] == "application/zip"
        zip_bytes = storage.objects[export["file_asset"]["storage_key"]][0]

        with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
            names = set(archive.namelist())
            assert "project.json" in names
            assert "pages/page-001.png" in names
            metadata = json.loads(archive.read("project.json"))
            assert metadata["project"]["id"] == project["id"]
            assert metadata["pages"][0]["width"] == 640
            assert metadata["pages"][0]["height"] == 960
            assert metadata["pages"][0]["reading_direction"] == "rtl"

        download = client.get(f"/exports/{export['id']}/download")
        assert download.status_code == 200
        assert download.content == zip_bytes
        assert download.headers["content-type"] == "application/zip"
    finally:
        app.dependency_overrides.pop(get_object_storage, None)


def test_pdf_export_creates_downloadable_pdf(client) -> None:
    storage = MemoryObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    try:
        project, _page = create_composed_project(client)
        export_response = client.post(
            f"/projects/{project['id']}/exports",
            json={"format": "pdf", "force": False, "options": {}},
        )
        assert export_response.status_code == 201
        export = export_response.json()
        assert export["status"] == "succeeded"
        assert export["file_asset"]["content_type"] == "application/pdf"
        pdf_bytes = storage.objects[export["file_asset"]["storage_key"]][0]
        assert pdf_bytes.startswith(b"%PDF")

        get_response = client.get(f"/exports/{export['id']}")
        assert get_response.status_code == 200
        assert get_response.json()["file_asset_id"] == export["file_asset_id"]

        download = client.get(f"/exports/{export['id']}/download")
        assert download.status_code == 200
        assert download.content == pdf_bytes
        assert download.headers["content-type"] == "application/pdf"
    finally:
        app.dependency_overrides.pop(get_object_storage, None)


def test_export_readiness_fails_if_qa_blocking_issue_exists_and_passes_after_fix(client) -> None:
    project, page = create_composed_project(client)
    complete_publishing_requirements(client, project["id"])
    qa_response = client.post(f"/pages/{page['id']}/qa", json={"provider_name": "mock", "export_preset": "draft"})
    assert qa_response.status_code == 201
    assert qa_response.json()["blocking"] is True

    blocked = client.get(f"/projects/{project['id']}/export-readiness?preset_id=archive_package")
    assert blocked.status_code == 200
    blocked_payload = blocked.json()
    assert blocked_payload["ready"] is False
    assert any(item["key"] == "no_blocking_qa" and not item["passed"] for item in blocked_payload["checklist"])

    with Session(app.state.engine) as session:
        report = session.exec(select(QAReport).where(QAReport.target_id == uuid.UUID(page["id"]))).first()
        assert report is not None
        report.blocking = False
        report.overall_score = 100
        report.issues = []
        report.recommendations = []
        session.add(report)
        session.commit()

    ready = client.get(f"/projects/{project['id']}/export-readiness?preset_id=archive_package")
    assert ready.status_code == 200
    assert ready.json()["ready"] is True


def test_webtoon_export_creates_vertical_package(client) -> None:
    storage = MemoryObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    try:
        project, _page = create_composed_project(client)
        create_extra_composed_page(client, project["id"], page_number=2)
        complete_publishing_requirements(client, project["id"])
        response = client.post(
            f"/projects/{project['id']}/exports/create",
            json={
                "preset_id": "webtoon_vertical_strip",
                "force": False,
                "options": {"spacing": 20, "max_image_height": 5000},
            },
        )
        assert response.status_code == 201
        export = response.json()
        assert export["status"] == "succeeded"
        assert export["format"] == "webtoon"
        data = storage.objects[export["file_asset"]["storage_key"]][0]
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
            assert "webtoon/strip-001.png" in names
            assert "webtoon/manifest.json" in names
            image = Image.open(BytesIO(archive.read("webtoon/strip-001.png")))
            assert image.width == 1080
            assert image.height > image.width
    finally:
        app.dependency_overrides.pop(get_object_storage, None)


def test_pdf_export_includes_all_pages(client) -> None:
    storage = MemoryObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    try:
        project, _page = create_composed_project(client)
        create_extra_composed_page(client, project["id"], page_number=2)
        complete_publishing_requirements(client, project["id"])
        response = client.post(
            f"/projects/{project['id']}/exports/create",
            json={"preset_id": "print_pdf", "force": True, "options": {}},
        )
        assert response.status_code == 201
        export = response.json()
        assert export["status"] == "succeeded"
        pdf_bytes = storage.objects[export["file_asset"]["storage_key"]][0]
        assert pdf_bytes.startswith(b"%PDF")
        assert pdf_bytes.count(b"/Type /Page") >= 2
    finally:
        app.dependency_overrides.pop(get_object_storage, None)


def test_zip_export_includes_provenance_files(client) -> None:
    storage = MemoryObjectStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    try:
        project, _page = create_composed_project(client)
        complete_publishing_requirements(client, project["id"])
        response = client.post(
            f"/projects/{project['id']}/exports/create",
            json={"preset_id": "archive_package", "force": False, "options": {}},
        )
        assert response.status_code == 201
        export = response.json()
        data = storage.objects[export["file_asset"]["storage_key"]][0]
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
            assert "provenance.json" in names
            assert "asset-rights-summary.json" in names
            assert "project.json" in names
    finally:
        app.dependency_overrides.pop(get_object_storage, None)


def create_composed_project(client):
    project = client.post("/projects", json={"name": "Export Test", "description": "Publishing test"}).json()
    page = client.post(f"/projects/{project['id']}/pages", json={"width": 640, "height": 960}).json()
    layout = client.put(
        f"/pages/{page['id']}/layout",
        json={
            "width": 640,
            "height": 960,
            "bleed": 16,
            "safe_margin": 48,
            "reading_direction": "rtl",
            "qa_overlay_enabled": False,
            "panels": [
                {
                    "x": 80,
                    "y": 100,
                    "width": 260,
                    "height": 220,
                    "reading_order": 1,
                    "prompt": "Export panel",
                    "polygon": [
                        {"x": 80, "y": 100},
                        {"x": 340, "y": 100},
                        {"x": 340, "y": 320},
                        {"x": 80, "y": 320},
                    ],
                }
            ],
        },
    )
    assert layout.status_code == 200
    compose = client.post(f"/pages/{page['id']}/compose")
    assert compose.status_code == 201
    return project, page


def create_extra_composed_page(client, project_id: str, *, page_number: int):
    page = client.post(f"/projects/{project_id}/pages", json={"page_number": page_number, "width": 640, "height": 960}).json()
    layout = client.put(
        f"/pages/{page['id']}/layout",
        json={
            "width": 640,
            "height": 960,
            "bleed": 16,
            "safe_margin": 48,
            "reading_direction": "rtl",
            "qa_overlay_enabled": False,
            "panels": [
                {
                    "x": 90,
                    "y": 140,
                    "width": 260,
                    "height": 220,
                    "reading_order": 1,
                    "prompt": "Export panel two",
                    "polygon": [
                        {"x": 90, "y": 140},
                        {"x": 350, "y": 140},
                        {"x": 350, "y": 360},
                        {"x": 90, "y": 360},
                    ],
                }
            ],
        },
    )
    assert layout.status_code == 200
    compose = client.post(f"/pages/{page['id']}/compose")
    assert compose.status_code == 201
    return page


def complete_publishing_requirements(client, project_id: str) -> None:
    rights = client.put(
        f"/projects/{project_id}/rights-declaration",
        json={
            "user_confirms_upload_rights": True,
            "user_confirms_no_unlicensed_ip": True,
            "user_confirms_review_required_before_publish": True,
            "notes": "Test rights complete.",
        },
    )
    assert rights.status_code == 200
    metadata = client.put(
        f"/projects/{project_id}/publishing-metadata",
        json={
            "title": "Export Test",
            "subtitle": "A test book",
            "author_name": "Test Author",
            "publisher": "Manga AI Studio",
            "language": "en",
            "synopsis": "A complete test manga package.",
            "age_rating": "13+",
            "genres": ["fantasy"],
            "tags": ["test"],
            "copyright_notice": "Copyright Test Author.",
            "ai_disclosure_text": "Created with AI-assisted tools for tests.",
            "metadata_json": {},
        },
    )
    assert metadata.status_code == 200
