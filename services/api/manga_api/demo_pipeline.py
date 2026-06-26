from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from sqlmodel import Session

from manga_api.compositor import PageCompositor
from manga_api.exporting import ProjectExporter
from manga_api.models import (
    Bubble,
    Chapter,
    Character,
    CharacterCard,
    KeyObject,
    Location,
    Page,
    PagePlan,
    Panel,
    PanelPlan,
    Project,
    ProjectExport,
    QAReport,
    Scene,
    StoryBible,
    StyleBible,
)
from manga_api.qa import MockQAProvider, PageQAService, QAOptions
from manga_api.rendering import RenderOrchestrator


DEMO_PREMISE = "A lonely swordsman protects a ghost child in a ruined city."
DemoEventCallback = Callable[[str, str, dict[str, Any] | None], None]


class DemoPipelineError(RuntimeError):
    """Raised when the deterministic demo pipeline cannot be completed."""


class DemoStorage(Protocol):
    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        """Persist bytes to object storage."""

    def get_bytes(self, key: str) -> bytes:
        """Read bytes from object storage."""

    def public_url(self, key: str) -> str:
        """Return a browser-accessible URL for a stored object."""


@dataclass(frozen=True)
class DemoPipelineCreated:
    project: Project
    story_bible_id: uuid.UUID
    chapter_id: uuid.UUID
    page_ids: list[uuid.UUID]
    panel_ids: list[uuid.UUID]
    render_job_ids: list[uuid.UUID]
    composite_asset_ids: list[uuid.UUID]
    qa_report_ids: list[uuid.UUID]
    exports: dict[str, uuid.UUID]


def create_full_demo_project(
    session: Session,
    storage: DemoStorage,
    *,
    project_id: uuid.UUID | str | None = None,
    premise: str = DEMO_PREMISE,
    page_count: int = 4,
    reading_direction: str = "rtl",
    render_provider: str = "mock",
    allow_mock_assets: bool = True,
    style_profile: dict[str, Any] | None = None,
    event_callback: DemoEventCallback | None = None,
) -> DemoPipelineCreated:
    """Create a complete deterministic manga project that exercises the full MVP pipeline."""

    style_profile = style_profile or {}
    style_prompt = str(
        style_profile.get(
            "prompt_style_positive",
            "Black-and-white ruined-city manga, lonely atmosphere, clean action silhouettes.",
        )
    )
    if project_id is not None:
        project = session.get(Project, uuid.UUID(str(project_id)))
        if project is None:
            raise DemoPipelineError(f"Demo project {project_id} was not found")
        project.description = premise
        project.style_prompt = style_prompt
    else:
        project = Project(
            name=str(style_profile.get("project_name", "Ghost Lantern")),
            description=premise,
            style_prompt=style_prompt,
        )
    session.add(project)
    session.flush()
    emit_demo_event(event_callback, "creating_project", "Created the Founder Demo manga workspace.", {"project_id": str(project.id)})

    story_bible = StoryBible(
        project_id=project.id,
        logline="A wandering swordsman escorts a silent ghost child through a city that remembers every war it lost.",
        synopsis=(
            "In the ruined city of Karakuri Vale, swordsman Ren Aki survives by avoiding attachments. "
            "When he finds Mio, a ghost child carrying the last lantern of the city, he is forced to guide "
            "her across collapsed districts while ash spirits and old war machines hunt the light she protects."
        ),
        genre="Supernatural samurai fantasy",
        themes=["grief", "protection", "chosen family", "memory after disaster"],
        target_audience="Teen and young adult manga readers",
        tone="Melancholic, tense, and hopeful",
        main_conflict="Ren must protect Mio without letting fear of loss turn him back into the weapon he used to be.",
        world_rules=[
            "Ghosts remain visible only near lantern light.",
            "Broken war machines awaken when they hear drawn steel.",
            "The ruined city rearranges streets around unresolved memories.",
        ],
        chapter_outline=[
            {
                "chapter_number": 1,
                "title": "The Lantern in the Rubble",
                "summary": "Ren finds Mio and chooses to cross the city rather than abandon her.",
            }
        ],
        continuity_rules=[
            "Mio never casts a shadow.",
            "Ren's cracked sword guard is visible in every close-up.",
            "Lantern light is the only soft glow in the ruined city.",
        ],
    )
    session.add(story_bible)
    session.flush()
    emit_demo_event(
        event_callback,
        "writing_story_bible",
        "Wrote the story bible and continuity rules.",
        {"story_bible_id": str(story_bible.id)},
    )

    characters = [
        Character(
            project_id=project.id,
            story_bible_id=story_bible.id,
            name="Ren Aki",
            role="Lonely swordsman protector",
            description="A quiet wanderer with a broken sword guard and a habit of standing between danger and anyone smaller than him.",
            traits=["guarded", "precise", "secretly gentle"],
            visual_notes="Long travel coat, chipped katana, tired eyes, rain-dark hair.",
        ),
        Character(
            project_id=project.id,
            story_bible_id=story_bible.id,
            name="Mio",
            role="Ghost child",
            description="A silent child spirit carrying a paper lantern that keeps the ruined city from going fully dark.",
            traits=["watchful", "brave", "otherworldly"],
            visual_notes="Small kimono, bare feet above the ground, translucent edges, lantern held close.",
        ),
    ]
    session.add_all(characters)

    location = Location(
        project_id=project.id,
        story_bible_id=story_bible.id,
        name="Karakuri Vale",
        description="A rain-slick ruined city of collapsed arcades, shrine gates, hanging wires, and dormant war machines.",
        visual_notes="Broken rooflines, deep black alleys, white mist, lantern reflections in puddles.",
        rules=["The city shifts at dawn.", "Ash spirits cannot cross a lit threshold."],
    )
    session.add(location)

    key_object = KeyObject(
        project_id=project.id,
        story_bible_id=story_bible.id,
        name="Mio's Lantern",
        description="A rain-spotted paper lantern that keeps Mio visible and holds the last warm light in the city.",
        significance="The lantern is the reason ash spirits pursue Mio and the reason Karakuri Vale can still remember hope.",
        visual_notes="Handmade paper sides, bent bamboo frame, small flame that does not flicker in rain.",
    )
    session.add(key_object)
    session.flush()
    emit_demo_event(
        event_callback,
        "designing_characters",
        "Designed two character cards, the core location, and the lantern object.",
        {
            "character_count": len(characters),
            "location_id": str(location.id),
            "key_object_id": str(key_object.id),
        },
    )

    style_bible = StyleBible(
        project_id=project.id,
        story_bible_id=story_bible.id,
        name=str(style_profile.get("name", "Ruined Ink Elegy")),
        style_name=str(style_profile.get("style_name", style_profile.get("name", "Ruined Ink Elegy"))),
        style_intent=str(style_profile.get("style_intent", "Original supernatural samurai manga style for a founder demo.")),
        line_weight=str(style_profile.get("line_weight", "Medium-heavy foreground outlines with thin atmospheric background lines.")),
        line_variation=str(style_profile.get("line_variation", "Quiet panels use even contours; action panels break into fast dry-brush cuts.")),
        line_texture=str(style_profile.get("line_texture", "Crisp ink with dry edges on rubble and rain-worn surfaces.")),
        face_shape_language=str(style_profile.get("face_shape_language", "Reserved faces with sharp protector angles and soft ghost-child curves.")),
        eye_design_language=str(style_profile.get("eye_design_language", "Strong eye acting, small highlights, readable emotional restraint.")),
        nose_mouth_simplification=str(style_profile.get("nose_mouth_simplification", "Minimal nose bridges and small mouth changes.")),
        anatomy_proportions=str(style_profile.get("anatomy_proportions", "Grounded action manga proportions with readable silhouettes.")),
        hair_rendering=str(style_profile.get("hair_rendering", "Black hair masses broken by rain strands and white rim highlights.")),
        clothing_fold_style=str(style_profile.get("clothing_fold_style", "Angular travel-cloth folds with sparse hatching.")),
        background_density=str(style_profile.get("background_density", "Detailed ruined landmarks, simplified distant silhouettes.")),
        architecture_detail=str(style_profile.get("architecture_detail", "Broken shrine beams, hanging wires, collapsed roofs, and wet stone.")),
        shadow_strategy=str(style_profile.get("shadow_strategy", "Large black shapes against reserved lantern-white highlights.")),
        screentone_strategy=str(style_profile.get("screentone_strategy", "Rain tone in skies and heavier dot tone in alleys.")),
        hatching_strategy=str(style_profile.get("hatching_strategy", "Thin crosshatching for stone, bold slashes for sword motion.")),
        black_fill_ratio=str(style_profile.get("black_fill_ratio", "High contrast, about forty percent deep black on moody panels.")),
        speedline_style=str(style_profile.get("speedline_style", "Directional rain and blade lines integrated into composition.")),
        impact_frame_style=str(style_profile.get("impact_frame_style", "Cracked black frames for sudden danger.")),
        panel_border_style=str(style_profile.get("panel_border_style", "Clean black borders with slightly heavier action beats.")),
        gutter_style=str(style_profile.get("gutter_style", "White gutters with generous breathing room.")),
        sfx_shape_language=str(style_profile.get("sfx_shape_language", "Hand-brushed impact shapes with broken edges.")),
        bubble_style=str(style_profile.get("bubble_style", "Clean speech bubbles and rectangular narration boxes.")),
        emotional_visual_rules=list(style_profile.get("emotional_visual_rules", ["Lantern light is the only soft glow.", "Isolation is shown with negative space."])),
        positive_prompt_fragments=list(
            style_profile.get(
                "positive_prompt_fragments",
                ["black-and-white manga", "ruined samurai city", "rain", "crisp ink", "emotional restraint"],
            )
        ),
        negative_prompt_fragments=list(style_profile.get("negative_prompt_fragments", ["muddy grayscale", "unreadable text", "copied artist style"])),
        forbidden_artist_references=[],
        forbidden_franchise_references=[],
        linework=str(style_profile.get("linework", "Sharp brush contours with dry, broken texture on ruins.")),
        screentone=str(style_profile.get("screentone", "Soft rain tone in skies, heavier dot tone in alleys.")),
        hatching=str(style_profile.get("hatching", "Thin crosshatching for stone, bold slashes for sword motion.")),
        black_white_balance=str(style_profile.get("black_white_balance", "Large black ruins contrasted with white lantern glow and clean silhouettes.")),
        face_language=str(style_profile.get("face_language", "Reserved expressions, strong eye acting, small mouth changes.")),
        anatomy_style=str(style_profile.get("anatomy_style", "Grounded samurai action proportions with readable poses.")),
        background_detail=str(style_profile.get("background_detail", "Detailed rubble, shrine fragments, hanging cables, and broken signs.")),
        panel_rhythm=str(style_profile.get("panel_rhythm", "Quiet wide panels punctuated by narrow sword-action cuts.")),
        sfx_style=str(style_profile.get("sfx_style", "Hand-brushed impact kana with cracked edges.")),
        typography_notes=str(style_profile.get("typography_notes", "Small, careful dialogue with rectangular narration boxes.")),
        forbidden_references=["photorealistic color", "modern city traffic", "comedy chibi style"],
        prompt_style_positive=style_prompt,
        prompt_style_negative=str(style_profile.get("prompt_style_negative", "muddy grayscale, soft painterly color, unreadable lettering.")),
        visual_style=str(style_profile.get("visual_style", "Black-and-white supernatural samurai manga with detailed ruins and luminous lantern contrast.")),
        line_art=str(style_profile.get("line_art", "Crisp brush line art with strong silhouettes.")),
        palette=str(style_profile.get("palette", "Monochrome ink, white gutters, lantern glow reserved for highlights.")),
        paneling=str(style_profile.get("paneling", "Cinematic quiet panels alternating with fast action slices.")),
        lettering=str(style_profile.get("lettering", "Clean manga lettering with restrained narration boxes.")),
        negative_prompts=list(style_profile.get("negative_prompts", ["muddy anatomy", "blank backgrounds", "soft painterly color"])),
    )
    session.add(style_bible)
    session.flush()
    project.active_style_bible_id = style_bible.id
    session.add(project)
    emit_demo_event(
        event_callback,
        "creating_style_dna",
        f"Created original Style DNA: {style_bible.name}.",
        {"style_bible_id": str(style_bible.id), "style_option": style_bible.name},
    )

    character_cards = [
        CharacterCard(
            project_id=project.id,
            name="Ren Aki",
            aliases=["The Ash Ronin"],
            age_range="late 20s",
            role="protector swordsman",
            personality="Reserved, vigilant, self-punishing, protective when it matters.",
            face_description="Long tired face, narrow eyes, faint scar through one brow.",
            hair_description="Rain-dark shoulder-length hair tied low.",
            eye_description="Dark, watchful eyes with heavy lower lids.",
            body_type="Lean, tall, travel-worn swordsman build.",
            outfit_default="Tattered dark travel coat over layered kimono, cracked sword guard.",
            accessories=["chipped katana", "frayed scarf"],
            scars_marks="Thin brow scar and old cuts on sword hand.",
            voice_style="Sparse, low, direct.",
            forbidden_changes=["Do not make Ren cheerful or ornate.", "Do not remove the cracked sword guard."],
            continuity_rules=["Ren stands between Mio and threats.", "Ren grips the sword only when danger is real."],
            canonical_visual_summary="Tall rain-worn swordsman in a tattered dark travel coat with a chipped katana and cracked sword guard.",
            silhouette_keywords=["tall", "coat", "katana", "frayed scarf"],
            face_anchor_description="Long tired face with a thin brow scar and narrow watchful eyes.",
            hair_anchor_description="Rain-dark shoulder-length hair tied low.",
            eye_anchor_description="Dark, guarded eyes with heavy lower lids.",
            body_anchor_description="Lean, tall, travel-worn swordsman build.",
            outfit_anchor_description="Tattered dark travel coat over layered kimono; cracked sword guard always visible.",
            color_notes_even_for_bw="Dark coat mass, pale rain highlights, chipped blade glints.",
            recurring_props=["chipped katana", "frayed scarf", "cracked sword guard"],
            allowed_variations=["rain-soaked coat", "minor ash scuffs"],
            forbidden_variations=["ornate armor", "missing sword guard", "bright cheerful expression"],
            current_story_state="Reluctant protector beginning to care for Mio.",
            injury_state="Old scars only; no fresh injury in the demo.",
            emotional_baseline="Controlled grief with protective focus.",
        ),
        CharacterCard(
            project_id=project.id,
            name="Mio",
            aliases=["Lantern Child"],
            age_range="appears 8-10",
            role="ghost child",
            personality="Quiet, observant, gentle, braver than she looks.",
            face_description="Round small face with calm, distant eyes.",
            hair_description="Short pale bob that floats slightly at the ends.",
            eye_description="Large reflective eyes with tiny lantern highlights.",
            body_type="Small childlike ghost silhouette.",
            outfit_default="Simple pale kimono, bare feet hovering just above ground.",
            accessories=["paper lantern"],
            scars_marks="Faint translucent edges, no shadow.",
            voice_style="Soft, minimal, sometimes only gestures.",
            forbidden_changes=["Do not give Mio a shadow.", "Do not make the lantern look electric."],
            continuity_rules=["Mio keeps the lantern close.", "Mio floats slightly above wet ground."],
            canonical_visual_summary="Small ghost child in a pale kimono, hovering above wet ground while holding a handmade paper lantern.",
            silhouette_keywords=["small", "floating", "kimono", "lantern"],
            face_anchor_description="Round small face with calm, distant eyes.",
            hair_anchor_description="Short pale bob that floats slightly at the ends.",
            eye_anchor_description="Large reflective eyes with tiny lantern highlights.",
            body_anchor_description="Small childlike ghost silhouette with translucent edges.",
            outfit_anchor_description="Simple pale kimono and bare feet hovering just above ground.",
            color_notes_even_for_bw="Pale silhouette, translucent edge treatment, warm lantern-white highlight.",
            recurring_props=["paper lantern"],
            allowed_variations=["faint glow strength", "subtle ghost edge shimmer"],
            forbidden_variations=["visible shadow", "electric lantern", "adult proportions"],
            current_story_state="Trusting Ren while still afraid of the ash spirits.",
            injury_state="No physical injury; ghostly translucence only.",
            emotional_baseline="Quiet bravery and lonely hope.",
        ),
    ]
    session.add_all(character_cards)

    chapter = Chapter(
        project_id=project.id,
        story_bible_id=story_bible.id,
        chapter_number=1,
        title="The Lantern in the Rubble",
        summary="Ren discovers Mio in the ruins and chooses to protect her from ash spirits crossing the city.",
        goal="Move Ren from isolation into reluctant guardianship.",
    )
    session.add(chapter)
    session.flush()

    scenes = [
        Scene(
            chapter_id=chapter.id,
            scene_order=1,
            title="Rain Over Karakuri Vale",
            summary="Ren crosses the dead city alone and hears a child humming in the rubble.",
            location_name="Karakuri Vale",
            emotional_turn="Isolation becomes curiosity.",
            characters=["Ren Aki", "Mio"],
        ),
        Scene(
            chapter_id=chapter.id,
            scene_order=2,
            title="Ash at the Gate",
            summary="Ash spirits gather around Mio's lantern, forcing Ren to draw his blade.",
            location_name="Collapsed shrine gate",
            emotional_turn="Reluctance becomes commitment.",
            characters=["Ren Aki", "Mio"],
        ),
    ]
    session.add_all(scenes)

    page_ids: list[uuid.UUID] = []
    panel_ids: list[uuid.UUID] = []
    panels_by_page: dict[uuid.UUID, list[Panel]] = {}
    page_specs = demo_page_specs(page_count)
    page_plan_specs: list[tuple[dict[str, Any], PagePlan]] = []

    for page_spec in page_specs:
        page_plan = PagePlan(
            project_id=project.id,
            chapter_id=chapter.id,
            page_number=page_spec["page_number"],
            summary=page_spec["summary"],
            pacing=page_spec["pacing"],
            panel_count=len(page_spec["panels"]),
        )
        session.add(page_plan)
        session.flush()
        page_plan_specs.append((page_spec, page_plan))

        for panel_spec in page_spec["panels"]:
            session.add(
                PanelPlan(
                    page_plan_id=page_plan.id,
                    panel_order=panel_spec["order"],
                    story_beat=panel_spec["beat"],
                    shot_type=panel_spec["shot_type"],
                    camera_angle=panel_spec["camera_angle"],
                    characters=panel_spec["characters"],
                    location="Karakuri Vale",
                    dialogue=panel_spec.get("dialogue"),
                    narration=panel_spec.get("narration"),
                    visual_notes=panel_spec["visual_notes"],
                    emotional_intent=panel_spec["emotion"],
                )
            )
    session.flush()
    emit_demo_event(
        event_callback,
        "planning_pages",
        f"Planned {len(page_specs)} pages and {sum(len(spec['panels']) for spec in page_specs)} panels.",
        {"page_count": len(page_specs), "panel_count": sum(len(spec["panels"]) for spec in page_specs)},
    )

    panel_bubble_specs: list[tuple[Panel, dict[str, Any]]] = []
    for page_spec, _page_plan in page_plan_specs:
        page = Page(
            project_id=project.id,
            page_number=page_spec["page_number"],
            width=1000,
            height=1500,
            layout_json={
                "bleed": 40,
                "safe_margin": 80,
                "reading_direction": reading_direction,
                "qa_overlay_enabled": False,
            },
        )
        session.add(page)
        session.flush()
        page_ids.append(page.id)
        panels_by_page[page.id] = []

        for panel_spec in page_spec["panels"]:
            panel = Panel(
                page_id=page.id,
                x=panel_spec["x"],
                y=panel_spec["y"],
                width=panel_spec["width"],
                height=panel_spec["height"],
                reading_order=panel_spec["order"],
                prompt=panel_spec["prompt"],
                polygon=rect_polygon(panel_spec["x"], panel_spec["y"], panel_spec["width"], panel_spec["height"]),
            )
            session.add(panel)
            session.flush()
            panel_ids.append(panel.id)
            panels_by_page[page.id].append(panel)
            panel_bubble_specs.append((panel, panel_spec))

    session.flush()
    emit_demo_event(
        event_callback,
        "drawing_layouts",
        "Drew page layouts with readable panel order and safe margins.",
        {"page_ids": [str(page_id) for page_id in page_ids], "panel_ids": [str(panel_id) for panel_id in panel_ids]},
    )

    for panel, panel_spec in panel_bubble_specs:
        bubble = Bubble(
            panel_id=panel.id,
            kind=panel_spec["bubble_kind"],
            x=panel.x + panel_spec["bubble_dx"],
            y=panel.y + panel_spec["bubble_dy"],
            width=panel_spec["bubble_width"],
            height=panel_spec["bubble_height"],
            text=panel_spec["bubble_text"],
        )
        session.add(bubble)

    session.flush()
    emit_demo_event(
        event_callback,
        "lettering_pages",
        "Placed dialogue bubbles and narration boxes.",
        {"bubble_count": len(panel_bubble_specs)},
    )

    session.commit()

    render_job_ids: list[uuid.UUID] = []
    orchestrator = RenderOrchestrator(session, storage)
    for index, panel_id in enumerate(panel_ids, start=1):
        job = orchestrator.render_panel(panel_id, render_provider, options={"seed": 9000 + index, "demo_mode": "founder"})
        if job.status == "failed" and allow_mock_assets and render_provider != "mock":
            job = orchestrator.render_panel(
                panel_id,
                "mock",
                options={"seed": 19000 + index, "demo_mode": "founder", "fallback_from": render_provider},
            )
        if job.status != "succeeded":
            raise DemoPipelineError(job.error_message or f"Render failed for panel {panel_id}")
        render_job_ids.append(job.id)
    emit_demo_event(
        event_callback,
        "rendering_panels",
        "Rendered polished deterministic mock panel art.",
        {"render_job_ids": [str(job_id) for job_id in render_job_ids]},
    )

    composite_asset_ids: list[uuid.UUID] = []
    compositor = PageCompositor(session, storage)
    for page_id in page_ids:
        composite = compositor.compose_page(page_id)
        composite_asset_ids.append(composite.asset.id)
    emit_demo_event(
        event_callback,
        "composing_final_pages",
        "Composed final page PNGs with panel art and lettering.",
        {"composite_asset_ids": [str(asset_id) for asset_id in composite_asset_ids]},
    )

    qa_report_ids: list[uuid.UUID] = []
    qa_service = PageQAService(session, MockQAProvider())
    for page_id in page_ids:
        report = qa_service.run_page_qa(page_id, QAOptions(export_preset="draft"))
        if report.blocking:
            raise DemoPipelineError(f"Demo QA unexpectedly blocked page {page_id}: {report.issues}")
        qa_report_ids.append(report.id)
    emit_demo_event(
        event_callback,
        "checking_quality",
        "Ran deterministic QA checks across the demo pages.",
        {"qa_report_ids": [str(report_id) for report_id in qa_report_ids]},
    )

    exports: dict[str, uuid.UUID] = {}
    exporter = ProjectExporter(session, storage)
    for export_format in ["zip", "pdf"]:
        export = exporter.export_project(
            project.id,
            export_format,
            force=False,
            options={"source": "demo_pipeline", "premise": premise, "reading_direction": reading_direction},
        )
        assert_export_succeeded(export)
        exports[export_format] = export.id
    emit_demo_event(
        event_callback,
        "exporting_files",
        "Prepared ZIP and PDF exports for download.",
        {"exports": {key: str(value) for key, value in exports.items()}},
    )

    session.refresh(project)
    return DemoPipelineCreated(
        project=project,
        story_bible_id=story_bible.id,
        chapter_id=chapter.id,
        page_ids=page_ids,
        panel_ids=panel_ids,
        render_job_ids=render_job_ids,
        composite_asset_ids=composite_asset_ids,
        qa_report_ids=qa_report_ids,
        exports=exports,
    )


def emit_demo_event(callback: DemoEventCallback | None, event_type: str, message: str, payload: dict[str, Any] | None = None) -> None:
    if callback is not None:
        callback(event_type, message, payload or {})


def assert_export_succeeded(export: ProjectExport) -> None:
    if export.status != "succeeded" or export.file_asset_id is None:
        raise DemoPipelineError(export.error_message or f"{export.format} export failed")


def rect_polygon(x: int, y: int, width: int, height: int) -> list[dict[str, int]]:
    return [
        {"x": x, "y": y},
        {"x": x + width, "y": y},
        {"x": x + width, "y": y + height},
        {"x": x, "y": y + height},
    ]


def demo_page_specs(page_count: int = 4) -> list[dict[str, Any]]:
    base_pages = with_final_boss_panel_geometry([
        {
            "page_number": 1,
            "summary": "Ren crosses the ruined city and discovers Mio's lantern in the rubble.",
            "pacing": "quiet reveal",
            "panels": [
                {
                    "order": 1,
                    "x": 80,
                    "y": 100,
                    "width": 840,
                    "height": 560,
                    "beat": "Ren walks alone under broken rooftops.",
                    "shot_type": "wide establishing shot",
                    "camera_angle": "high angle",
                    "characters": ["Ren Aki"],
                    "narration": "Karakuri Vale had forgotten every voice but the rain.",
                    "dialogue": None,
                    "visual_notes": "Tiny swordsman silhouette in huge ruined street.",
                    "emotion": "lonely scale",
                    "prompt": "Ren Aki walks through rain-slick ruins, tiny against collapsed buildings.",
                    "bubble_kind": "narration",
                    "bubble_dx": 40,
                    "bubble_dy": 36,
                    "bubble_width": 430,
                    "bubble_height": 92,
                    "bubble_text": "The city had forgotten every voice but the rain.",
                },
                {
                    "order": 2,
                    "x": 80,
                    "y": 760,
                    "width": 840,
                    "height": 600,
                    "beat": "A soft lantern glow appears beneath rubble.",
                    "shot_type": "medium reveal",
                    "camera_angle": "low angle",
                    "characters": ["Ren Aki", "Mio"],
                    "narration": None,
                    "dialogue": "Who is there?",
                    "visual_notes": "Lantern glow under broken shrine beams.",
                    "emotion": "suspicion turning wonder",
                    "prompt": "Ren finds a ghost child holding a paper lantern under broken shrine beams.",
                    "bubble_kind": "speech",
                    "bubble_dx": 460,
                    "bubble_dy": 64,
                    "bubble_width": 300,
                    "bubble_height": 130,
                    "bubble_text": "Who is there?",
                },
            ],
        },
        {
            "page_number": 2,
            "summary": "Mio appears and ash spirits begin to gather.",
            "pacing": "slow dread",
            "panels": [
                {
                    "order": 1,
                    "x": 80,
                    "y": 100,
                    "width": 840,
                    "height": 560,
                    "beat": "Mio floats out from the lantern light without a shadow.",
                    "shot_type": "close-up",
                    "camera_angle": "eye level",
                    "characters": ["Mio"],
                    "narration": "She did not touch the ground.",
                    "dialogue": None,
                    "visual_notes": "Ghost child with lantern, no shadow beneath her feet.",
                    "emotion": "fragile mystery",
                    "prompt": "Mio floats above wet stone holding a paper lantern, no shadow below.",
                    "bubble_kind": "narration",
                    "bubble_dx": 48,
                    "bubble_dy": 42,
                    "bubble_width": 330,
                    "bubble_height": 90,
                    "bubble_text": "She did not touch the ground.",
                },
                {
                    "order": 2,
                    "x": 80,
                    "y": 760,
                    "width": 840,
                    "height": 600,
                    "beat": "Ash spirits crawl down the cracked walls toward the lantern.",
                    "shot_type": "wide threat shot",
                    "camera_angle": "tilted low angle",
                    "characters": ["Ren Aki", "Mio"],
                    "narration": None,
                    "dialogue": "Stay behind me.",
                    "visual_notes": "Black ash hands on walls, Ren half-draws sword.",
                    "emotion": "protective alarm",
                    "prompt": "Ash spirits crawl down cracked walls as Ren shields Mio with one arm.",
                    "bubble_kind": "speech",
                    "bubble_dx": 480,
                    "bubble_dy": 70,
                    "bubble_width": 300,
                    "bubble_height": 126,
                    "bubble_text": "Stay behind me.",
                },
            ],
        },
        {
            "page_number": 3,
            "summary": "Ren fights the spirits while Mio protects the lantern.",
            "pacing": "action burst",
            "panels": [
                {
                    "order": 1,
                    "x": 80,
                    "y": 100,
                    "width": 840,
                    "height": 560,
                    "beat": "Ren cuts through ash without looking back.",
                    "shot_type": "dynamic action shot",
                    "camera_angle": "diagonal low angle",
                    "characters": ["Ren Aki"],
                    "narration": None,
                    "dialogue": "Do not let the light go out.",
                    "visual_notes": "Sword arc splits black ash, speed lines, rain spray.",
                    "emotion": "focused urgency",
                    "prompt": "Ren swings a chipped katana through ash spirits, rain and speed lines exploding.",
                    "bubble_kind": "speech",
                    "bubble_dx": 420,
                    "bubble_dy": 48,
                    "bubble_width": 360,
                    "bubble_height": 132,
                    "bubble_text": "Do not let the light go out.",
                },
                {
                    "order": 2,
                    "x": 80,
                    "y": 760,
                    "width": 840,
                    "height": 600,
                    "beat": "Mio hugs the lantern as the city stairs shift open.",
                    "shot_type": "medium shot",
                    "camera_angle": "over shoulder",
                    "characters": ["Mio", "Ren Aki"],
                    "narration": "The city answered the lantern.",
                    "dialogue": None,
                    "visual_notes": "Stairway forms from rubble behind Mio.",
                    "emotion": "uncertain hope",
                    "prompt": "Mio holds the lantern while rubble rearranges into a hidden stairway.",
                    "bubble_kind": "narration",
                    "bubble_dx": 46,
                    "bubble_dy": 42,
                    "bubble_width": 390,
                    "bubble_height": 92,
                    "bubble_text": "The city answered the lantern.",
                },
            ],
        },
        {
            "page_number": 4,
            "summary": "Ren accepts the burden of escorting Mio through the city.",
            "pacing": "emotional close",
            "panels": [
                {
                    "order": 1,
                    "x": 80,
                    "y": 100,
                    "width": 840,
                    "height": 560,
                    "beat": "Ren kneels and repairs the lantern handle with his scarf thread.",
                    "shot_type": "quiet close-up",
                    "camera_angle": "low intimate angle",
                    "characters": ["Ren Aki", "Mio"],
                    "narration": None,
                    "dialogue": "I know a road through the dead districts.",
                    "visual_notes": "Hands repairing paper lantern, sword resting nearby.",
                    "emotion": "reluctant tenderness",
                    "prompt": "Ren repairs Mio's paper lantern with thread from his scarf, gentle close-up.",
                    "bubble_kind": "speech",
                    "bubble_dx": 390,
                    "bubble_dy": 54,
                    "bubble_width": 390,
                    "bubble_height": 138,
                    "bubble_text": "I know a road through the dead districts.",
                },
                {
                    "order": 2,
                    "x": 80,
                    "y": 760,
                    "width": 840,
                    "height": 600,
                    "beat": "Ren and Mio leave together under the last lantern glow.",
                    "shot_type": "wide closing shot",
                    "camera_angle": "rear view",
                    "characters": ["Ren Aki", "Mio"],
                    "narration": "For the first time in years, Ren did not walk alone.",
                    "dialogue": None,
                    "visual_notes": "Two silhouettes on broken bridge, lantern glow in rain.",
                    "emotion": "hopeful companionship",
                    "prompt": "Ren and Mio cross a broken bridge in rain, lantern glow leading them onward.",
                    "bubble_kind": "narration",
                    "bubble_dx": 48,
                    "bubble_dy": 428,
                    "bubble_width": 520,
                    "bubble_height": 96,
                    "bubble_text": "For the first time in years, Ren did not walk alone.",
                },
            ],
        },
    ])

    if page_count <= len(base_pages):
        return copy.deepcopy(base_pages[:page_count])

    pages = copy.deepcopy(base_pages)
    for page_number in range(len(base_pages) + 1, page_count + 1):
        source = copy.deepcopy(base_pages[(page_number - 1) % len(base_pages)])
        source["page_number"] = page_number
        source["summary"] = f"Ren and Mio press deeper into Karakuri Vale as the lantern reveals another path on page {page_number}."
        source["pacing"] = "founder demo continuation"
        for panel in source["panels"]:
            panel["beat"] = f"Page {page_number}: {panel['beat']}"
            panel["prompt"] = f"Founder demo page {page_number}, {panel['prompt']}"
            if panel.get("narration"):
                panel["narration"] = f"Page {page_number}: the ruined city opens another memory."
            if panel.get("dialogue"):
                panel["dialogue"] = "Stay close to the lantern."
            panel["bubble_text"] = (
                f"Page {page_number}: the city opens another memory."
                if panel["bubble_kind"] == "narration"
                else "Stay close to the lantern."
            )
        pages.append(source)
    return pages


def with_final_boss_panel_geometry(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize the demo to the final-boss evidence contract: 4 pages, 3 panels each."""

    geometry = [
        {
            "x": 80,
            "y": 100,
            "width": 840,
            "height": 360,
            "bubble_dx": 40,
            "bubble_dy": 32,
            "bubble_width": 430,
            "bubble_height": 86,
        },
        {
            "x": 80,
            "y": 560,
            "width": 840,
            "height": 360,
            "bubble_dx": 470,
            "bubble_dy": 52,
            "bubble_width": 320,
            "bubble_height": 112,
        },
        {
            "x": 80,
            "y": 1020,
            "width": 840,
            "height": 360,
            "bubble_dx": 42,
            "bubble_dy": 40,
            "bubble_width": 430,
            "bubble_height": 90,
        },
    ]
    extra_panels = {
        1: {
            "order": 3,
            "beat": "Mio lifts the lantern and the rubble seems to breathe.",
            "shot_type": "quiet close-up",
            "camera_angle": "eye level",
            "characters": ["Mio", "Ren Aki"],
            "narration": None,
            "dialogue": "I was waiting.",
            "visual_notes": "Mio's paper lantern glows under broken beams while Ren watches from shadow.",
            "emotion": "uneasy connection",
            "prompt": "Mio lifts a rain-spotted paper lantern under broken shrine beams as Ren watches from shadow.",
            "bubble_kind": "speech",
            "bubble_text": "I was waiting.",
        },
        2: {
            "order": 3,
            "beat": "Ren realizes the ash spirits are afraid of the lantern.",
            "shot_type": "medium reaction",
            "camera_angle": "over the shoulder",
            "characters": ["Ren Aki", "Mio"],
            "narration": None,
            "dialogue": "They fear your light.",
            "visual_notes": "Ash hands recoil from the lantern glow while Ren lowers his stance.",
            "emotion": "discovery under pressure",
            "prompt": "Ash spirit hands recoil from Mio's lantern as Ren lowers his stance to protect her.",
            "bubble_kind": "speech",
            "bubble_text": "They fear your light.",
        },
        3: {
            "order": 3,
            "beat": "Ren blocks an ash claw and orders Mio toward the hidden stairs.",
            "shot_type": "action close-up",
            "camera_angle": "diagonal low angle",
            "characters": ["Ren Aki", "Mio"],
            "narration": None,
            "dialogue": "When I move, run.",
            "visual_notes": "Katana guard locks against a black claw; Mio hesitates by the opened stair.",
            "emotion": "urgent protection",
            "prompt": "Ren's chipped katana blocks a black ash claw while Mio waits beside a hidden stairway.",
            "bubble_kind": "speech",
            "bubble_text": "When I move, run.",
        },
        4: {
            "order": 3,
            "beat": "Ren and Mio step into the hidden stairway together.",
            "shot_type": "wide closing reveal",
            "camera_angle": "rear view",
            "characters": ["Ren Aki", "Mio"],
            "narration": "The road opened for two.",
            "dialogue": None,
            "visual_notes": "Two silhouettes enter a stairwell of lantern light beneath the ruined city.",
            "emotion": "fragile hope",
            "prompt": "Ren and Mio descend a hidden stairway beneath the ruined city, lantern glow guiding them.",
            "bubble_kind": "narration",
            "bubble_text": "The road opened for two.",
        },
    }

    for page in pages:
        for index, panel in enumerate(page["panels"]):
            panel.update(geometry[index])
        page["panels"].append({**extra_panels[page["page_number"]], **geometry[2]})
    return pages
