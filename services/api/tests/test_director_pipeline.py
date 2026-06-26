import uuid
import zipfile
from io import BytesIO


def test_director_generate_draft_pipeline_creates_complete_project(client) -> None:
    project_id = uuid.uuid4()
    response = client.post(
        f"/projects/{project_id}/director/generate-draft",
        json={
            "premise": "A lonely swordsman protects a ghost child in a ruined city.",
            "chapter_count": 1,
            "page_count": 2,
            "target_audience": "Teen and young adult manga readers",
            "genre": ["dark fantasy", "action"],
            "tone": "melancholic, cinematic, hopeful",
            "reading_direction": "rtl",
            "render_provider": "mock",
            "quality_mode": "fast",
            "allow_mock_assets": True,
        },
    )
    assert response.status_code == 202
    result = response.json()
    assert result["project_id"] == str(project_id)

    job_response = client.get(f"/jobs/{result['job_id']}")
    assert job_response.status_code == 200
    job = job_response.json()
    assert job["status"] == "succeeded"
    state = job["output_payload"]["director_state"]
    assert len(state["page_ids"]) == 2
    assert len(state["panel_ids"]) == 4
    assert len(state["render_job_ids"]) == 4
    assert len(state["composite_asset_ids"]) == 2
    assert len(state["qa_report_ids"]) == 2
    assert state["draft_export_id"]

    events_response = client.get(f"/jobs/{result['job_id']}/events")
    assert events_response.status_code == 200
    event_types = [event["event_type"] for event in events_response.json()]
    assert event_types == [
        "queued",
        "generating_story_bible",
        "generating_characters",
        "generating_style",
        "planning_pages",
        "creating_layouts",
        "rendering_panels",
        "composing_pages",
        "running_qa",
        "exporting",
        "complete",
    ]

    detail = client.get(f"/projects/{project_id}")
    assert detail.status_code == 200
    project = detail.json()
    assert project["description"] == "A lonely swordsman protects a ghost child in a ruined city."
    assert project["active_style_bible_id"] == state["style_bible_id"]
    assert len(project["pages"]) == 2
    assert all(len(page["panels"]) == 2 for page in project["pages"])

    story = client.get(f"/projects/{project_id}/story/bible")
    assert story.status_code == 200
    story_json = story.json()
    assert story_json["logline"].startswith(project["name"])
    assert len(story_json["characters"]) == 2
    assert len(story_json["locations"]) == 1
    assert len(story_json["key_objects"]) == 1

    characters = client.get(f"/projects/{project_id}/characters")
    assert characters.status_code == 200
    assert len(characters.json()) == 2

    styles = client.get(f"/projects/{project_id}/style-bibles")
    assert styles.status_code == 200
    assert len(styles.json()) == 1

    for page_id in state["page_ids"]:
        composite = client.get(f"/pages/{page_id}/composite")
        assert composite.status_code == 200
        qa = client.get(f"/pages/{page_id}/qa/latest")
        assert qa.status_code == 200
        assert qa.json()["blocking"] is False

    export_response = client.get(f"/exports/{state['draft_export_id']}")
    assert export_response.status_code == 200
    assert export_response.json()["status"] == "succeeded"

    download = client.get(f"/exports/{state['draft_export_id']}/download")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(download.content)) as archive:
        names = set(archive.namelist())
        assert "project.json" in names
        assert "pages/page-001.png" in names
        assert "pages/page-002.png" in names
