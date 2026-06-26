import pytest
from pydantic import ValidationError

from manga_api.llm import MockLLMProvider
from manga_api.schemas import (
    ChapterPlanBatchResult,
    PagePlanBatchResult,
    PanelPlanResult,
    StoryBibleResult,
)


def test_story_schema_validation_requires_panel_plan_fields() -> None:
    valid = PanelPlanResult(
        panel_order=1,
        story_beat="Nami sees the skyline change.",
        shot_type="wide shot",
        camera_angle="high angle",
        characters=["Nami Vale"],
        location="Kurobay Rooftops",
        dialogue=None,
        narration="The city had started revising itself.",
        visual_notes="Strong perspective lines and red correction marks.",
        emotional_intent="Awe turning into alarm",
    )
    assert valid.panel_order == 1

    with pytest.raises(ValidationError):
        PanelPlanResult(
            panel_order=1,
            story_beat="Missing visual notes should fail.",
            shot_type="wide shot",
            camera_angle="high angle",
            emotional_intent="Alarm",
        )


def test_mock_story_generation_returns_valid_structures() -> None:
    provider = MockLLMProvider()

    story_bible = provider.generate_structured(
        StoryBibleResult,
        "system",
        "user",
    )
    chapters = provider.generate_structured(
        ChapterPlanBatchResult,
        "system",
        "user",
    )
    pages = provider.generate_structured(
        PagePlanBatchResult,
        "system",
        "user",
    )

    assert story_bible.logline
    assert story_bible.characters[0].name == "Nami Vale"
    assert chapters.chapters[0].scenes
    assert pages.pages[0].panels[0].visual_notes


def test_generate_and_retrieve_story_bible(client) -> None:
    project = client.post(
        "/projects",
        json={
            "name": "Margin City",
            "description": "A living manga city rewrites itself.",
            "style_prompt": "Crisp ink, dynamic panel borders",
        },
    ).json()

    generated = client.post(
        f"/projects/{project['id']}/story/generate-bible",
        json={
            "premise": "An artist fights a masked editor who can revise reality.",
            "genre": "Urban fantasy",
            "chapter_count": 3,
        },
    )

    assert generated.status_code == 201
    bible = generated.json()
    assert bible["project_id"] == project["id"]
    assert bible["characters"]
    assert bible["locations"]
    assert bible["key_objects"]
    assert bible["chapter_outline"]
    assert bible["style_bible"]["visual_style"]

    retrieved = client.get(f"/projects/{project['id']}/story/bible")
    assert retrieved.status_code == 200
    assert retrieved.json()["id"] == bible["id"]
    assert retrieved.json()["logline"] == bible["logline"]


def test_generate_chapter_and_page_plans(client) -> None:
    project = client.post("/projects", json={"name": "Margin City"}).json()
    bible_response = client.post(
        f"/projects/{project['id']}/story/generate-bible",
        json={"premise": "A city that lives inside manga panels."},
    )
    assert bible_response.status_code == 201

    chapter_response = client.post(f"/projects/{project['id']}/story/generate-chapter-plan")
    assert chapter_response.status_code == 201
    chapters = chapter_response.json()
    assert chapters[0]["id"]
    assert chapters[0]["scenes"][0]["characters"]

    page_response = client.post(f"/chapters/{chapters[0]['id']}/story/generate-page-plans")
    assert page_response.status_code == 201
    pages = page_response.json()
    assert pages[0]["panels"][0]["panel_order"] == 1
    assert pages[0]["panels"][0]["emotional_intent"]
