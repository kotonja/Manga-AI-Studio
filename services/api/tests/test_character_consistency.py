from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from manga_api.models import (
    Asset,
    Chapter,
    CharacterCard,
    CharacterReferenceAsset,
    CharacterState,
    KeyObject,
    Location,
    Page,
    PagePlan,
    Panel,
    PanelPlan,
    Project,
    Scene,
    StoryBible,
    StyleBible,
)
from manga_api.reference_pack import ReferencePackBuilder
from manga_api.rendering import RenderOrchestrator, assemble_panel_prompt, prompt_json_to_text


class MemoryObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    def public_url(self, key: str) -> str:
        return f"http://objects.test/{key}"


def test_reference_pack_builds_panel_consistency_context() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        context = create_consistency_context(session)
        pack = ReferencePackBuilder(session).build_for_panel(context["panel"].id)

        assert pack["style_bible"]["name"] == "Ash Ink"
        assert pack["story_memory"]["story_bible"]["logline"].startswith("A lonely swordsman")
        assert pack["characters"][0]["card"]["name"] == "Ren Aki"
        assert pack["characters"][0]["state"]["outfit_state"] == "Rain-soaked travel coat, scarf tied tight."
        assert pack["locations"][0]["name"] == "Karakuri Vale"
        assert pack["key_objects"][0]["name"] == "Paper lantern"
        assert pack["approved_visual_references"][0]["storage_key"].startswith("characters/")
        assert "Ren Aki:canonical_visual_summary" in pack["required_anchor_names"]
        assert pack["missing_character_state_ids"] == []

    SQLModel.metadata.drop_all(engine)


def test_panel_prompt_includes_character_anchors_reference_pack_and_state() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    store = MemoryObjectStore()

    with Session(engine) as session:
        context = create_consistency_context(session)
        job = RenderOrchestrator(session, store).render_panel(context["panel"].id, "mock", options={"seed": 77})

        assert job.status == "succeeded"
        prompt_json = job.input_payload["prompt_json"]
        prompt_text = job.input_payload["prompt"]

        assert prompt_json["reference_pack"]["characters"][0]["card"]["name"] == "Ren Aki"
        assert "identity anchors" in prompt_text.lower()
        assert "Lean swordsman silhouette with low-tied dark hair and cracked sword guard." in prompt_text
        assert "Thin brow scar; tired long face; guarded expression." in prompt_text
        assert "Rain-soaked travel coat, scarf tied tight." in prompt_text
        assert "Fresh cut across left sleeve, no face injury." in prompt_text
        assert "Karakuri Vale" in prompt_text
        assert "low angle" in prompt_text
        assert "muddy gray values" in prompt_json["negative_prompt"]
        assert store.objects

        assembled = assemble_panel_prompt(session, context["project"], context["page"], context["panel"])
        assembled_text = prompt_json_to_text(assembled)
        assert "reference_pack" in assembled
        assert "cracked sword guard" in assembled_text

    SQLModel.metadata.drop_all(engine)


def test_character_state_changes_persist_across_pages() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        context = create_consistency_context(session)
        project = context["project"]
        chapter = context["chapter"]
        scene = context["scene"]
        character = context["character"]

        page_two = Page(project_id=project.id, page_number=2, width=1000, height=1400)
        page_plan_two = PagePlan(
            project_id=project.id,
            chapter_id=chapter.id,
            page_number=2,
            summary="Ren shields Mio at the gate.",
            pacing="tense",
            panel_count=1,
        )
        panel_plan_two = PanelPlan(
            page_plan_id=page_plan_two.id,
            panel_order=1,
            story_beat="Ren blocks a spirit strike.",
            shot_type="medium action",
            camera_angle="eye level",
            characters=["Ren Aki"],
            location="Karakuri Vale",
            dialogue="Stay behind me.",
            narration=None,
            visual_notes="Sword guard catches lantern light.",
            emotional_intent="protective resolve",
        )
        panel_two = Panel(
            page_id=page_two.id,
            x=90,
            y=120,
            width=460,
            height=320,
            reading_order=1,
            polygon=[
                {"x": 90, "y": 120},
                {"x": 550, "y": 120},
                {"x": 550, "y": 440},
                {"x": 90, "y": 440},
            ],
        )
        state_two = CharacterState(
            character_id=character.id,
            chapter_id=chapter.id,
            scene_id=scene.id,
            page_id=page_two.id,
            outfit_state="Coat torn open at shoulder, scarf loose.",
            injury_state="Bandaged left forearm after spirit strike.",
            emotional_state="openly protective",
            prop_state="katana drawn",
            visibility_notes="Mio's lantern rim light on sword guard.",
            continuity_notes="Page two injury overrides scene-level clean sleeve.",
        )
        session.add_all([page_two, page_plan_two, panel_plan_two, panel_two, state_two])
        session.commit()

        page_one_pack = ReferencePackBuilder(session).build_for_panel(context["panel"].id)
        page_two_pack = ReferencePackBuilder(session).build_for_panel(panel_two.id)

        assert page_one_pack["characters"][0]["state"]["injury_state"] == "Fresh cut across left sleeve, no face injury."
        assert page_two_pack["characters"][0]["state"]["injury_state"] == "Bandaged left forearm after spirit strike."
        assert page_two_pack["characters"][0]["state"]["outfit_state"] == "Coat torn open at shoulder, scarf loose."

    SQLModel.metadata.drop_all(engine)


def create_consistency_context(session: Session) -> dict:
    project = Project(name="Consistency Project", description="Reference pack test")
    story = StoryBible(
        project_id=project.id,
        logline="A lonely swordsman protects a ghost child in a ruined city.",
        synopsis="Ren Aki crosses Karakuri Vale and chooses to defend Mio from ash spirits.",
        genre="supernatural samurai drama",
        themes=["protection", "memory"],
        target_audience="teen",
        tone="melancholy and tense",
        main_conflict="Ash spirits hunt Mio's lantern.",
        world_rules=["Ghost light reflects in metal but casts no shadow."],
        chapter_outline=[{"chapter_number": 1, "title": "Lantern in Rain", "summary": "Ren finds Mio."}],
        continuity_rules=["Ren's cracked sword guard stays visible.", "Mio never casts a shadow."],
    )
    style = StyleBible(
        project_id=project.id,
        story_bible_id=story.id,
        name="Ash Ink",
        linework="Crisp brush linework with clear silhouettes.",
        screentone="Rain haze and rubble shadows.",
        hatching="Tense hatching near spirit threats.",
        black_white_balance="Heavy foreground blacks with white gutters.",
        face_language="Tired eyes and restrained mouths.",
        anatomy_style="Grounded samurai action proportions.",
        background_detail="Ruined city landmarks repeat clearly.",
        panel_rhythm="Quiet wide panels broken by narrow action cuts.",
        sfx_style="Cracked brush impact kana.",
        typography_notes="Small dialogue, rectangular narration.",
        forbidden_references=["photorealistic color"],
        prompt_style_positive="Black-and-white manga, rain, ruins, readable silhouettes.",
        prompt_style_negative="muddy gray values, soft painterly color",
    )
    project.active_style_bible_id = style.id
    chapter = Chapter(
        project_id=project.id,
        story_bible_id=story.id,
        chapter_number=1,
        title="Lantern in Rain",
        summary="Ren discovers the ghost child.",
        goal="Turn isolation into guardianship.",
    )
    scene = Scene(
        chapter_id=chapter.id,
        scene_order=1,
        title="Rain Over Karakuri Vale",
        summary="Rain falls through broken signs as Ren hears Mio humming.",
        location_name="Karakuri Vale",
        emotional_turn="Isolation becomes responsibility.",
        characters=["Ren Aki"],
    )
    page = Page(project_id=project.id, page_number=1, width=1000, height=1400)
    page_plan = PagePlan(
        project_id=project.id,
        chapter_id=chapter.id,
        page_number=1,
        summary="Ren enters the ruined city.",
        pacing="quiet reveal",
        panel_count=1,
    )
    panel_plan = PanelPlan(
        page_plan_id=page_plan.id,
        panel_order=1,
        story_beat="Ren steps into the flooded avenue.",
        shot_type="wide establishing",
        camera_angle="low angle",
        characters=["Ren Aki"],
        location="Karakuri Vale",
        dialogue="Someone is here.",
        narration="The city answered only in rain.",
        visual_notes="Cracked sword guard visible; lantern glow far ahead.",
        emotional_intent="watchful loneliness",
    )
    panel = Panel(
        page_id=page.id,
        x=80,
        y=100,
        width=480,
        height=360,
        reading_order=1,
        prompt="Ren watches the ruined avenue.",
        polygon=[
            {"x": 80, "y": 100},
            {"x": 560, "y": 100},
            {"x": 560, "y": 460},
            {"x": 80, "y": 460},
        ],
    )
    character = CharacterCard(
        project_id=project.id,
        name="Ren Aki",
        aliases=["The Ash Ronin"],
        age_range="late 20s",
        role="protector swordsman",
        personality="Reserved, vigilant, self-punishing.",
        face_description="Long tired face with narrow eyes.",
        hair_description="Rain-dark shoulder-length hair tied low.",
        eye_description="Dark watchful eyes with heavy lower lids.",
        body_type="Lean, tall swordsman build.",
        outfit_default="Tattered dark travel coat over layered kimono.",
        accessories=["chipped katana", "frayed scarf"],
        scars_marks="Thin brow scar and old cuts on sword hand.",
        voice_style="Sparse, low, direct.",
        forbidden_changes=["Do not remove the cracked sword guard."],
        continuity_rules=["Ren stands between Mio and threats."],
        canonical_visual_summary="Lean swordsman silhouette with low-tied dark hair and cracked sword guard.",
        silhouette_keywords=["tall lean ronin", "low tied hair", "long coat"],
        face_anchor_description="Thin brow scar; tired long face; guarded expression.",
        hair_anchor_description="Rain-dark shoulder-length hair tied low behind neck.",
        eye_anchor_description="Narrow watchful dark eyes with heavy lower lids.",
        body_anchor_description="Lean tall build, shoulders slightly hunched from travel.",
        outfit_anchor_description="Tattered dark travel coat over layered kimono, frayed scarf.",
        color_notes_even_for_bw="Dark coat reads as black mass; scarf is mid-gray.",
        recurring_props=["cracked sword guard", "frayed scarf"],
        allowed_variations=["wet coat", "loosened scarf"],
        forbidden_variations=["ornate armor", "short hair", "missing sword guard"],
        current_story_state="Reluctant protector.",
        injury_state="Fresh cut across left sleeve, no face injury.",
        emotional_baseline="controlled grief",
    )
    reference = CharacterReferenceAsset(
        project_id=project.id,
        character_card_id=character.id,
        filename="ren-front.png",
        kind="reference",
        content_type="image/png",
        size_bytes=2048,
        storage_key=f"characters/{character.id}/ren-front.png",
        metadata_json={"pose": "front"},
    )
    approved_asset = Asset(
        project_id=project.id,
        filename="ren-approved-panel.png",
        kind="render",
        content_type="image/png",
        size_bytes=3000,
        storage_key=f"approved/{character.id}/panel.png",
        metadata_json={"approved": True},
    )
    character.reference_asset_ids = [str(reference.id)]
    character.approved_panel_asset_ids = [str(approved_asset.id)]
    location = Location(
        project_id=project.id,
        story_bible_id=story.id,
        name="Karakuri Vale",
        description="A ruined city of flooded avenues, cracked signs, and broken shrines.",
        visual_notes="Collapsed tram wires, shrine fragments, and rain mirrors.",
        rules=["The broken clocktower appears in wide shots."],
    )
    key_object = KeyObject(
        project_id=project.id,
        story_bible_id=story.id,
        name="Paper lantern",
        description="Mio's small lantern with ghost flame.",
        significance="It attracts ash spirits and anchors Mio's presence.",
        visual_notes="Soft white glow, never electric.",
    )
    state = CharacterState(
        character_id=character.id,
        chapter_id=chapter.id,
        scene_id=scene.id,
        page_id=page.id,
        outfit_state="Rain-soaked travel coat, scarf tied tight.",
        injury_state="Fresh cut across left sleeve, no face injury.",
        emotional_state="guarded and lonely",
        prop_state="katana sheathed, hand near cracked guard",
        visibility_notes="Full figure silhouette visible.",
        continuity_notes="Keep brow scar visible in closeups.",
    )
    session.add_all(
        [
            project,
            story,
            style,
            chapter,
            scene,
            page,
            page_plan,
            panel_plan,
            panel,
            character,
            reference,
            approved_asset,
            location,
            key_object,
            state,
        ]
    )
    session.commit()
    return {
        "project": project,
        "story": story,
        "style": style,
        "chapter": chapter,
        "scene": scene,
        "page": page,
        "page_plan": page_plan,
        "panel_plan": panel_plan,
        "panel": panel,
        "character": character,
        "state": state,
    }
