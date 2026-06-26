import zipfile
from io import BytesIO


def test_create_full_demo_project_builds_exportable_pipeline(client) -> None:
    response = client.post("/demo/create-full-project")
    assert response.status_code == 201

    demo = response.json()
    project = demo["project"]
    assert project["name"] == "Ghost Lantern"
    assert project["description"] == "A lonely swordsman protects a ghost child in a ruined city."
    assert len(demo["page_ids"]) == 4
    assert len(demo["panel_ids"]) == 12
    assert len(demo["render_job_ids"]) == 12
    assert len(demo["composite_asset_ids"]) == 4
    assert len(demo["qa_report_ids"]) == 4
    assert set(demo["exports"]) == {"zip", "pdf"}

    detail = client.get(f"/projects/{project['id']}")
    assert detail.status_code == 200
    detail_json = detail.json()
    assert len(detail_json["pages"]) == 4
    assert all(page["panels"] for page in detail_json["pages"])

    story = client.get(f"/projects/{project['id']}/story/bible")
    assert story.status_code == 200
    assert len(story.json()["characters"]) == 2
    assert len(story.json()["locations"]) == 1

    characters = client.get(f"/projects/{project['id']}/characters")
    assert characters.status_code == 200
    assert len(characters.json()) == 2

    zip_export_id = demo["exports"]["zip"]
    zip_download = client.get(f"/exports/{zip_export_id}/download")
    assert zip_download.status_code == 200
    assert zip_download.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(zip_download.content)) as archive:
        names = set(archive.namelist())
        assert "project.json" in names
        assert "pages/page-001.png" in names
        assert "pages/page-004.png" in names

    pdf_export_id = demo["exports"]["pdf"]
    pdf_download = client.get(f"/exports/{pdf_export_id}/download")
    assert pdf_download.status_code == 200
    assert pdf_download.content.startswith(b"%PDF")


def test_founder_demo_run_creates_evented_polished_demo(client) -> None:
    response = client.post(
        "/demo/founder-run",
        json={
            "premise": "A lonely swordsman protects a ghost child in a ruined city.",
            "style_option": "moonlit_screentone_noir",
            "page_count": 4,
            "reading_direction": "rtl",
            "render_provider": "mock",
            "quality_mode": "fast",
            "allow_mock_assets": True,
        },
    )
    assert response.status_code == 202
    result = response.json()

    job_response = client.get(f"/jobs/{result['job_id']}")
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["status"] == "succeeded"
    state = job["output_payload"]["founder_state"]
    assert state["project_id"] == result["project_id"]
    assert state["style_option"] == "moonlit_screentone_noir"
    assert len(state["page_ids"]) == 4
    assert len(state["panel_ids"]) == 12
    assert len(state["render_job_ids"]) == 12
    assert set(state["exports"]) == {"zip", "pdf"}

    events_response = client.get(f"/jobs/{result['job_id']}/events")
    assert events_response.status_code == 200
    event_types = [event["event_type"] for event in events_response.json()]
    assert event_types == [
        "queued",
        "creating_project",
        "writing_story_bible",
        "designing_characters",
        "creating_style_dna",
        "planning_pages",
        "drawing_layouts",
        "lettering_pages",
        "rendering_panels",
        "composing_final_pages",
        "checking_quality",
        "exporting_files",
        "complete",
    ]

    detail = client.get(f"/projects/{result['project_id']}")
    assert detail.status_code == 200
    assert len(detail.json()["pages"]) == 4

    for page_id in state["page_ids"]:
        composite = client.get(f"/pages/{page_id}/composite")
        assert composite.status_code == 200
        assert composite.json()["width"] == 1000
        assert composite.json()["height"] == 1500

    zip_download = client.get(f"/exports/{state['exports']['zip']}/download")
    assert zip_download.status_code == 200
    assert zip_download.headers["content-type"] == "application/zip"
