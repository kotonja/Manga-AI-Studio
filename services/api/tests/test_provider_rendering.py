import uuid

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from manga_api.models import (
    Asset,
    Chapter,
    CharacterCard,
    KeyObject,
    Location,
    Page,
    PagePlan,
    Panel,
    PanelPlan,
    Project,
    Render,
    StoryBible,
    StyleBible,
)
from manga_api.rendering import MockImageProvider, RenderOrchestrator


class MemoryObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    def public_url(self, key: str) -> str:
        return f"http://objects.test/{key}"


def test_mock_image_provider_is_deterministic_png() -> None:
    provider = MockImageProvider()
    first = provider.generate_image("panel prompt", "320x240", [], {"seed": 42, "panel_id": "panel-1"})
    second = provider.generate_image("panel prompt", "320x240", [], {"seed": 42, "panel_id": "panel-1"})

    assert first.data == second.data
    assert first.data.startswith(b"\x89PNG")
    assert first.width == 320
    assert first.height == 240
    assert first.model_name == "mock-image-v1"


def test_render_orchestrator_assembles_prompt_and_persists_mock_render() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    store = MemoryObjectStore()

    with Session(engine) as session:
        project = Project(name="Provider Project", style_prompt="High contrast noir inks")
        story = StoryBible(
            project_id=project.id,
            logline="A courier protects a forbidden sketchbook.",
            synopsis="A rooftop chase reveals the city remembers every drawing.",
            genre="urban fantasy",
            themes=["memory", "craft"],
            target_audience="teen",
            tone="urgent and hopeful",
            main_conflict="Artists are hunted for drawing living maps.",
            world_rules=["Ink can store memories"],
            chapter_outline=[{"chapter_number": 1, "title": "Inkfall", "summary": "The map wakes"}],
            continuity_rules=["The sketchbook clasp is always visible"],
        )
        style = StyleBible(
            project_id=project.id,
            name="Noir Brush",
            linework="Heavy confident brush lines",
            screentone="Sparse diagonal tone",
            hatching="Tense crosshatching around shadows",
            black_white_balance="Deep blacks against clean white gutters",
            face_language="Large expressive eyes with restrained mouths",
            anatomy_style="Grounded teen action proportions",
            background_detail="Dense urban rooftops",
            panel_rhythm="Fast narrow panels for chase beats",
            sfx_style="Hand-lettered impact bursts",
            typography_notes="Compact all-caps dialogue",
            forbidden_references=["photorealism"],
            prompt_style_positive="Black-and-white manga, crisp ink, cinematic rooftop action",
            prompt_style_negative="muddy grayscale, soft painterly color",
        )
        project.active_style_bible_id = style.id
        chapter = Chapter(
            project_id=project.id,
            story_bible_id=story.id,
            chapter_number=1,
            title="Inkfall",
            summary="The map wakes.",
            goal="Reach the clocktower before dawn.",
        )
        page = Page(project_id=project.id, page_number=1, width=1000, height=1400)
        page_plan = PagePlan(
            project_id=project.id,
            chapter_id=chapter.id,
            page_number=1,
            summary="The courier jumps across rooftops.",
            pacing="rapid",
            panel_count=1,
        )
        panel_plan = PanelPlan(
            page_plan_id=page_plan.id,
            panel_order=1,
            story_beat="Courier lands beside a glowing map line.",
            shot_type="wide action",
            camera_angle="low angle",
            characters=["Mira"],
            location="Clocktower roof",
            dialogue="No turning back.",
            narration="Dawn was catching up.",
            visual_notes="Coat flares, city below, map light cutting the shadows.",
            emotional_intent="defiant momentum",
        )
        panel = Panel(
            page_id=page.id,
            x=80,
            y=100,
            width=480,
            height=360,
            reading_order=1,
            prompt="Mira lands in a crouch",
            polygon=[
                {"x": 80, "y": 100},
                {"x": 560, "y": 100},
                {"x": 560, "y": 460},
                {"x": 80, "y": 460},
            ],
        )
        character = CharacterCard(
            project_id=project.id,
            name="Mira",
            role="courier protagonist",
            personality="Quick, guarded, brave",
            face_description="Round face with determined brows",
            hair_description="Short black hair swept by motion",
            eye_description="Bright alert eyes",
            body_type="lean runner",
            outfit_default="cropped jacket and satchel",
        )
        location = Location(
            project_id=project.id,
            story_bible_id=story.id,
            name="Clocktower roof",
            description="A slate roof above the memory district",
            visual_notes="Gargoyles, antennae, and wet tiles",
            rules=["The bell rings when ink magic is nearby"],
        )
        key_object = KeyObject(
            project_id=project.id,
            story_bible_id=story.id,
            name="Forbidden sketchbook",
            description="A worn sketchbook with a brass clasp",
            significance="Stores living maps",
            visual_notes="Always carried in Mira's satchel",
        )
        session.add_all(
            [
                project,
                story,
                style,
                chapter,
                page,
                page_plan,
                panel_plan,
                panel,
                character,
                location,
                key_object,
            ]
        )
        session.commit()

        job = RenderOrchestrator(session, store).render_panel(panel.id, "mock", options={"seed": 1234})

        assert job.status == "succeeded"
        assert job.provider == "mock"
        assert job.error_message is None
        assert job.input_payload["provider"] == "mock"
        assert job.input_payload["model_name"] == "mock-image-v1"
        assert job.input_payload["options"]["seed"] == 1234

        prompt_json = job.input_payload["prompt_json"]
        assert prompt_json["style_bible"]["name"] == "Noir Brush"
        assert prompt_json["story_bible"]["logline"].startswith("A courier")
        assert prompt_json["page_plan"]["summary"] == "The courier jumps across rooftops."
        assert prompt_json["panel_plan"]["emotional_intent"] == "defiant momentum"
        assert prompt_json["characters"][0]["name"] == "Mira"
        assert prompt_json["locations"][0]["name"] == "Clocktower roof"
        assert prompt_json["key_objects"][0]["name"] == "Forbidden sketchbook"
        assert prompt_json["panel_layout"]["polygon"][0] == {"x": 80, "y": 100}

        render = session.exec(select(Render).where(Render.job_id == job.id)).one()
        asset_id = uuid.UUID(job.output_payload["asset_id"])
        asset = session.get(Asset, asset_id)
        assert asset is not None
        assert asset.storage_key == render.storage_key
        assert render.public_url == f"http://objects.test/{asset.storage_key}"
        assert store.objects[asset.storage_key][0].startswith(b"\x89PNG")
        assert asset.metadata_json["model_name"] == "mock-image-v1"

    SQLModel.metadata.drop_all(engine)
