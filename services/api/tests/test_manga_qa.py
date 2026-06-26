import uuid

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from manga_api.models import (
    Asset,
    Bubble,
    CharacterCard,
    CharacterState,
    Chapter,
    GenerationJob,
    KeyObject,
    Page,
    PagePlan,
    Panel,
    PanelPlan,
    PanelRenderPrompt,
    Project,
    Render,
    Scene,
    StoryBible,
)
from manga_api.qa_autofix import AutoFixService
from manga_api.qa import PageQAService, QAOptions


def test_page_qa_detects_layout_render_lettering_and_export_issues() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        project = Project(name="QA Project")
        page = Page(
            project_id=project.id,
            page_number=1,
            width=800,
            height=1200,
            layout_json={"reading_direction": "rtl"},
        )
        page_plan = PagePlan(
            project_id=project.id,
            chapter_id=project.id,
            page_number=1,
            summary="Two beats planned",
            pacing="fast",
            panel_count=2,
        )
        panel = Panel(
            page_id=page.id,
            x=80,
            y=100,
            width=320,
            height=260,
            reading_order=1,
            polygon=[
                {"x": 80, "y": 100},
                {"x": 400, "y": 100},
                {"x": 400, "y": 360},
                {"x": 80, "y": 360},
            ],
        )
        large_bubble = Bubble(
            panel_id=panel.id,
            kind="speech",
            x=88,
            y=108,
            width=260,
            height=210,
            text="This is too much text space.",
        )
        session.add_all([project, page, page_plan, panel, large_bubble])
        session.commit()

        report = PageQAService(session).run_page_qa(
            page.id,
            QAOptions(export_preset="draft", max_bubble_panel_coverage=0.25),
        )

        codes = {issue["code"] for issue in report.issues}
        assert "panel_count_mismatch" in codes
        assert "panel_render_missing" in codes
        assert "bubble_covers_panel" in codes
        assert "composite_missing" in codes
        assert report.blocking is True
        assert report.overall_score < 100

    SQLModel.metadata.drop_all(engine)


def test_page_qa_endpoint_persists_and_returns_latest_report(client) -> None:
    project = client.post("/projects", json={"name": "Endpoint QA"}).json()
    page = client.post(f"/projects/{project['id']}/pages", json={"width": 700, "height": 1000}).json()
    layout = client.put(
        f"/pages/{page['id']}/layout",
        json={
            "width": 700,
            "height": 1000,
            "bleed": 16,
            "safe_margin": 48,
            "reading_direction": "ltr",
            "qa_overlay_enabled": False,
            "panels": [
                {
                    "x": 80,
                    "y": 90,
                    "width": 260,
                    "height": 220,
                    "reading_order": 1,
                    "prompt": "Panel one",
                    "polygon": [
                        {"x": 80, "y": 90},
                        {"x": 340, "y": 90},
                        {"x": 340, "y": 310},
                        {"x": 80, "y": 310},
                    ],
                }
            ],
        },
    ).json()
    panel = layout["panels"][0]
    client.post(
        f"/panels/{panel['id']}/bubbles",
        json={"kind": "speech", "x": 100, "y": 110, "width": 160, "height": 90, "text": "Ready."},
    )

    response = client.post(
        f"/pages/{page['id']}/qa",
        json={"provider_name": "mock", "export_preset": "draft"},
    )
    assert response.status_code == 201
    report = response.json()
    assert report["target_type"] == "page"
    assert report["target_id"] == page["id"]
    assert report["blocking"] is True
    assert any(issue["code"] == "panel_render_missing" for issue in report["issues"])

    latest = client.get(f"/pages/{page['id']}/qa/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == report["id"]


def test_advanced_qa_detects_deterministic_issue_categories() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        project = Project(name="Advanced QA", style_prompt="in the style of Naruto")
        story = StoryBible(
            project_id=project.id,
            logline="A guardian carries the Moon Blade.",
            synopsis="A test story.",
            genre="dark fantasy",
            themes=[],
            target_audience="teen",
            tone="somber",
            main_conflict="protect the relic",
            world_rules=[],
            continuity_rules=[],
        )
        key_object = KeyObject(
            project_id=project.id,
            story_bible_id=story.id,
            name="Moon Blade",
            description="A pale sword.",
            significance="Must appear in the action beat.",
        )
        chapter = Chapter(project_id=project.id, story_bible_id=story.id, chapter_number=1, title="One", summary="Test", goal="Test")
        scene = Scene(chapter_id=chapter.id, scene_order=1, title="Scene", summary="Rain fight", characters=["Ren", "Mira"])
        page = Page(project_id=project.id, page_number=1, width=800, height=1200, layout_json={"reading_direction": "rtl", "safe_margin": 80})
        page_plan = PagePlan(project_id=project.id, chapter_id=chapter.id, page_number=1, summary="", pacing="fast", panel_count=4)
        panel_plan_1 = PanelPlan(
            page_plan_id=page_plan.id,
            panel_order=1,
            story_beat="Ren and Mira lift the Moon Blade.",
            shot_type="medium",
            camera_angle="low",
            characters=["Ren", "Mira"],
            dialogue="We have to move.",
            visual_notes="Moon Blade in rain.",
            emotional_intent="",
        )
        panel_plan_2 = PanelPlan(
            page_plan_id=page_plan.id,
            panel_order=2,
            story_beat="",
            shot_type="close",
            camera_angle="eye",
            characters=[],
            visual_notes="",
            emotional_intent="",
        )
        ren = CharacterCard(
            project_id=project.id,
            name="Ren",
            canonical_visual_summary="lonely swordsman with crescent scar",
            face_anchor_description="crescent scar under left eye",
            outfit_anchor_description="torn black travel cloak",
        )
        mira = CharacterCard(
            project_id=project.id,
            name="Mira",
            canonical_visual_summary="ghost child with translucent hair",
            face_anchor_description="round worried face",
            outfit_anchor_description="white rain robe",
        )
        mira_state = CharacterState(
            character_id=mira.id,
            chapter_id=chapter.id,
            scene_id=scene.id,
            page_id=page.id,
            outfit_state="white rain robe soaked at hem",
            injury_state="glowing crack on right hand",
            emotional_state="frightened",
            prop_state="holding a paper charm",
        )
        panel_1 = Panel(
            page_id=page.id,
            x=20,
            y=20,
            width=360,
            height=260,
            reading_order=1,
            polygon=[{"x": 20, "y": 20}, {"x": 380, "y": 20}, {"x": 380, "y": 280}, {"x": 20, "y": 280}],
        )
        panel_2 = Panel(
            page_id=page.id,
            x=40,
            y=40,
            width=70,
            height=80,
            reading_order=1,
            polygon=[{"x": 40, "y": 40}, {"x": 110, "y": 40}, {"x": 110, "y": 120}, {"x": 40, "y": 120}],
        )
        panel_3 = Panel(
            page_id=page.id,
            x=760,
            y=1000,
            width=90,
            height=160,
            reading_order=2,
            polygon=[{"x": 760, "y": 1000}, {"x": 850, "y": 1000}, {"x": 850, "y": 1160}, {"x": 760, "y": 1160}],
        )
        bubbles = [
            Bubble(panel_id=panel_1.id, kind="speech", bubble_type="speech", x=790, y=40, width=80, height=80, text="Outside"),
            Bubble(panel_id=panel_1.id, kind="speech", bubble_type="speech", x=30, y=30, width=300, height=240, text=""),
            Bubble(panel_id=panel_1.id, kind="speech", bubble_type="speech", x=60, y=60, width=70, height=35, text="This line is far too long for the tiny bubble box.", font_size=28),
            Bubble(panel_id=panel_1.id, kind="speech", bubble_type="speech", x=120, y=90, width=80, height=70, text="No speaker"),
        ]
        asset = Asset(
            project_id=project.id,
            filename="render.png",
            kind="render",
            content_type="image/png",
            size_bytes=100,
            storage_key="renders/qa/render.png",
            metadata_json={"approved": False},
        )
        render_job = GenerationJob(project_id=project.id, page_id=page.id, panel_id=panel_1.id, provider="mock", job_type="render_panel", status="succeeded")
        render = Render(job_id=render_job.id, panel_id=panel_1.id, asset_id=asset.id, storage_key=asset.storage_key, width=300, height=80)
        prompt = PanelRenderPrompt(
            panel_id=panel_1.id,
            provider_name="mock",
            positive_prompt="Ren and Mira in rain.",
            negative_prompt="",
            structured_context={"reference_pack": {"present": True}},
            reference_pack={},
            size="512x512",
            quality_mode="draft",
        )
        composite = Asset(
            project_id=project.id,
            filename="page.png",
            kind="page_composite",
            content_type="image/png",
            size_bytes=100,
            storage_key="pages/qa/composite.png",
            metadata_json={
                "page_id": str(page.id),
                "width": 500,
                "height": 700,
                "panel_render_asset_ids": {str(panel_1.id): str(asset.id)},
                "approved_render_asset_ids": {},
            },
        )
        session.add_all(
            [
                project,
                story,
                key_object,
                chapter,
                scene,
                page,
                page_plan,
                panel_plan_1,
                panel_plan_2,
                ren,
                mira,
                mira_state,
                panel_1,
                panel_2,
                panel_3,
                *bubbles,
                asset,
                render_job,
                render,
                prompt,
                composite,
            ]
        )
        session.commit()

        report = PageQAService(session).run_page_qa(page.id, QAOptions(export_preset="draft", max_bubble_panel_coverage=0.25))

        codes = {issue["code"] for issue in report.issues}
        expected_codes = {
            "page_story_beat_missing",
            "panel_count_mismatch",
            "impossible_reading_order",
            "panel_out_of_bounds",
            "panel_overlap_excessive",
            "panel_too_tiny",
            "panel_unsafe_margin",
            "render_wrong_aspect_ratio",
            "render_resolution_too_low",
            "unapproved_render_used_in_composite",
            "panel_render_missing",
            "bubble_out_of_bounds",
            "bubble_text_missing",
            "bubble_text_overflow",
            "bubble_covers_panel",
            "too_many_bubbles_in_panel",
            "character_state_missing",
            "character_anchor_missing_in_prompt",
            "outfit_injury_mismatch",
            "key_object_missing_in_prompt",
            "panel_emotional_intent_missing",
            "dialogue_speaker_missing",
            "export_resolution_too_low",
            "forbidden_style_reference_detected",
            "forbidden_franchise_reference_detected",
        }
        assert expected_codes.issubset(codes)
        assert all("issue_category" in issue for issue in report.issues)
        assert any(issue["auto_fix_available"] for issue in report.issues)
        assert report.issue_code is not None
        assert report.auto_fix_available is True

    SQLModel.metadata.drop_all(engine)


def test_auto_fix_moves_bubble_inside_page(client) -> None:
    project = client.post("/projects", json={"name": "Fix Bubble"}).json()
    page = client.post(f"/projects/{project['id']}/pages", json={"width": 500, "height": 700}).json()
    layout = client.put(
        f"/pages/{page['id']}/layout",
        json={
            "width": 500,
            "height": 700,
            "bleed": 0,
            "safe_margin": 20,
            "reading_direction": "ltr",
            "qa_overlay_enabled": False,
            "panels": [
                {
                    "x": 60,
                    "y": 80,
                    "width": 240,
                    "height": 180,
                    "reading_order": 1,
                    "polygon": [{"x": 60, "y": 80}, {"x": 300, "y": 80}, {"x": 300, "y": 260}, {"x": 60, "y": 260}],
                }
            ],
        },
    ).json()
    panel = layout["panels"][0]
    bubble = client.post(
        f"/panels/{panel['id']}/bubbles",
        json={"kind": "speech", "x": 470, "y": 650, "width": 80, "height": 80, "text": "Move me"},
    ).json()

    qa = client.post(f"/pages/{page['id']}/qa", json={"provider_name": "mock", "export_preset": "draft"}).json()
    issue = next(issue for issue in qa["issues"] if issue["code"] == "bubble_out_of_bounds")
    response = client.post(f"/qa/{qa['id']}/apply-fix", json={"issue_id": issue["id"]})

    assert response.status_code == 200
    assert response.json()["applied"]
    fixed = client.get(f"/pages/{page['id']}/layout").json()["panels"][0]["bubbles"][0]
    assert fixed["id"] == bubble["id"]
    assert fixed["x"] + fixed["width"] <= page["width"]
    assert fixed["y"] + fixed["height"] <= page["height"]


def test_auto_fix_rebuilds_missing_prompt_anchors(client) -> None:
    demo = client.post("/demo/create-full-project").json()
    page_id = demo["page_ids"][0]
    panel_id = demo["panel_ids"][0]
    with Session(client.app.state.engine) as session:
        panel = session.get(Panel, uuid.UUID(panel_id))
        prompt = PanelRenderPrompt(
            panel_id=panel.id,
            provider_name="mock",
            positive_prompt="A vague panel.",
            negative_prompt="",
            structured_context={"reference_pack": {"present": True}},
            reference_pack={},
            size="512x512",
            quality_mode="draft",
        )
        session.add(prompt)
        session.commit()

    qa = client.post(f"/pages/{page_id}/qa", json={"provider_name": "mock", "export_preset": "draft"}).json()
    issue = next(issue for issue in qa["issues"] if issue["code"] == "character_anchor_missing_in_prompt")
    response = client.post(f"/qa/{qa['id']}/apply-fix", json={"issue_id": issue["id"]})

    assert response.status_code == 200
    assert response.json()["applied"][0]["action"] == "rebuild_panel_prompt"
    prompts = client.get(f"/panels/{panel_id}/render-prompts").json()
    assert len(prompts) >= 2
