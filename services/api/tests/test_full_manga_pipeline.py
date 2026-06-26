import json
import zipfile
from io import BytesIO


def test_full_manga_pipeline_demo_outputs_exports_and_metadata(client) -> None:
    demo_response = client.post("/demo/create-full-project")
    assert demo_response.status_code == 201
    demo = demo_response.json()
    project = demo["project"]

    assert project["description"] == "A lonely swordsman protects a ghost child in a ruined city."
    assert len(demo["page_ids"]) == 4
    assert len(demo["panel_ids"]) == 12
    assert len(demo["render_job_ids"]) == 12
    assert len(demo["composite_asset_ids"]) == 4
    assert len(demo["qa_report_ids"]) == 4
    assert set(demo["exports"]) == {"zip", "pdf"}

    story_response = client.get(f"/projects/{project['id']}/story/bible")
    assert story_response.status_code == 200
    story = story_response.json()
    assert story["logline"]
    assert len(story["characters"]) >= 2
    assert len(story["locations"]) >= 1

    characters_response = client.get(f"/projects/{project['id']}/characters")
    assert characters_response.status_code == 200
    assert len(characters_response.json()) >= 2

    project_detail = client.get(f"/projects/{project['id']}")
    assert project_detail.status_code == 200
    pages = project_detail.json()["pages"]
    assert len(pages) == 4
    assert all(len(page["panels"]) >= 3 for page in pages)
    for page in pages:
        layout_response = client.get(f"/pages/{page['id']}/layout")
        assert layout_response.status_code == 200
        layout = layout_response.json()
        assert layout["reading_direction"] == "rtl"
        assert len(layout["panels"]) >= 3
        assert any(panel["bubbles"] for panel in layout["panels"])
        for panel in layout["panels"]:
            renders_response = client.get(f"/panels/{panel['id']}/renders")
            assert renders_response.status_code == 200
            assert len(renders_response.json()) >= 1

        composite_response = client.get(f"/pages/{page['id']}/composite")
        assert composite_response.status_code == 200
        assert composite_response.json()["content_type"] == "image/png"

        qa_response = client.get(f"/pages/{page['id']}/qa/latest")
        assert qa_response.status_code == 200
        assert qa_response.json()["blocking"] is False

    zip_export = client.get(f"/exports/{demo['exports']['zip']}/download")
    assert zip_export.status_code == 200
    assert zip_export.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(zip_export.content)) as archive:
        names = set(archive.namelist())
        assert "project.json" in names
        assert "provenance.json" in names
        assert "asset-rights-summary.json" in names
        assert "pages/page-001.png" in names
        assert "pages/page-004.png" in names
        metadata = json.loads(archive.read("project.json"))
        assert metadata["project"]["id"] == project["id"]
        assert metadata["pages"][0]["reading_direction"] == "rtl"
        assert metadata["pages"][0]["panels"][0]["render"]["storage_key"]
        provenance = json.loads(archive.read("provenance.json"))
        assert provenance["summary"]["total_assets"] >= 16

    pdf_export = client.get(f"/exports/{demo['exports']['pdf']}/download")
    assert pdf_export.status_code == 200
    assert pdf_export.headers["content-type"] == "application/pdf"
    assert pdf_export.content.startswith(b"%PDF")
