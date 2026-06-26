from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from manga_api.models import Page, Panel, Project, StyleBible
from manga_api.rendering import assemble_panel_prompt, prompt_json_to_text
from manga_api.style_guard import evaluate_style_safety


def safe_style_payload() -> dict:
    return {
        "name": "Raincut Lantern Noir",
        "style_name": "Raincut Lantern Noir",
        "style_intent": "An original supernatural manga look based on wet silhouettes and restrained facial acting.",
        "line_weight": "Medium-heavy outer contours with thin interior face detail.",
        "line_variation": "Even calm lines shift into snapped pressure changes during threat beats.",
        "line_texture": "Dry brush on ruins, clean smooth strokes on eyes.",
        "face_shape_language": "Long tired adult faces and small rounded ghost-child silhouettes.",
        "eye_design_language": "Dark almond eyes with tiny white value anchors.",
        "nose_mouth_simplification": "Minimal wedge noses and narrow mouths.",
        "anatomy_proportions": "Grounded lean figures with slightly elongated limbs.",
        "hair_rendering": "Grouped black hair masses with wet strand cuts.",
        "clothing_fold_style": "Large angular coat folds with sparse interior detail.",
        "background_density": "Dense establishing panels and simplified action backgrounds.",
        "architecture_detail": "Broken signage, cracked shrine geometry, hanging cables.",
        "shadow_strategy": "Deep black foregrounds with ghost-lit rim highlights.",
        "screentone_strategy": "Soft gray rain sheets and low-density rubble texture.",
        "hatching_strategy": "Short directional hatch bursts around fear and sword draws.",
        "black_fill_ratio": "45 percent black in tense panels.",
        "speedline_style": "Sparse blade-following arcs.",
        "impact_frame_style": "Thin black impact frames with chipped corners.",
        "panel_border_style": "Clean black borders, slightly thicker during threat beats.",
        "gutter_style": "Wide white gutters for silence.",
        "sfx_shape_language": "Cracked brush shapes that lean with motion.",
        "bubble_style": "Round quiet speech bubbles and rectangular narration.",
        "typography_notes": "Compact all-caps dialogue with generous padding.",
        "emotional_visual_rules": ["Isolation uses large negative space."],
        "positive_prompt_fragments": ["original black-and-white supernatural manga", "wet ink silhouettes"],
        "negative_prompt_fragments": ["artist imitation", "franchise resemblance"],
        "forbidden_artist_references": [],
        "forbidden_franchise_references": [],
        "linework": "Medium-heavy contour with thin interior details.",
        "screentone": "Soft gray rain sheets.",
        "hatching": "Short directional hatch bursts.",
        "black_white_balance": "Deep blacks with ghost-lit rim highlights.",
        "face_language": "Restrained faces with expressive eyes.",
        "anatomy_style": "Grounded lean action proportions.",
        "background_detail": "Ruined city landmarks stay readable.",
        "panel_rhythm": "Wide silence panels broken by narrow threat cuts.",
        "sfx_style": "Cracked brush impact shapes.",
        "forbidden_references": [],
        "prompt_style_positive": "original manga, wet silhouettes, ghost-light contrast",
        "prompt_style_negative": "artist imitation, franchise resemblance, muddy gray values",
    }


def test_style_guard_catches_risky_phrases() -> None:
    result = evaluate_style_safety(
        {
            **safe_style_payload(),
            "style_intent": "Make this exactly like Akira Toriyama and in the style of Dragon Ball.",
        }
    )

    assert result.allowed is False
    assert result.severity == "blocked"
    codes = {issue.code for issue in result.issues}
    assert "risky_phrase_exactly_like" in codes
    assert "risky_phrase_in_the_style_of" in codes
    assert "artist_reference" in codes
    assert "franchise_reference" in codes
    assert "self-contained original design system" in result.suggested_style["style_intent"]


def test_safe_original_style_passes_guard() -> None:
    result = evaluate_style_safety(safe_style_payload())

    assert result.allowed is True
    assert result.severity == "safe"
    assert result.issues == []


def test_style_save_blocks_risky_style_and_generator_returns_options(client) -> None:
    project = client.post("/projects", json={"name": "Style DNA Project"}).json()
    risky = {**safe_style_payload(), "style_intent": "Copy Naruto exactly like the franchise look."}
    blocked = client.post(f"/projects/{project['id']}/style-bibles", json=risky)
    assert blocked.status_code == 422
    assert blocked.json()["detail"]["severity"] == "blocked"

    generated = client.post(
        f"/projects/{project['id']}/style/generate-dna",
        json={
            "genre": "supernatural samurai drama",
            "tone": "melancholy and tense",
            "audience": "teen",
            "visual_keywords": ["rain", "ruins", "ghost light"],
            "avoid_keywords": ["artist names", "franchise references"],
            "sample_story_summary": "A lonely swordsman protects a ghost child in a ruined city.",
        },
    )
    assert generated.status_code == 201
    options = generated.json()["options"]
    assert 3 <= len(options) <= 6
    assert options[0]["style_name"]
    assert options[0]["preview_prompt"]


def test_style_prompt_assembly_includes_style_dna() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        project = Project(name="Style Prompt Project")
        style = StyleBible(project_id=project.id, **safe_style_payload())
        project.active_style_bible_id = style.id
        page = Page(project_id=project.id, page_number=1, width=900, height=1300)
        panel = Panel(
            page_id=page.id,
            x=80,
            y=90,
            width=420,
            height=300,
            reading_order=1,
            polygon=[
                {"x": 80, "y": 90},
                {"x": 500, "y": 90},
                {"x": 500, "y": 390},
                {"x": 80, "y": 390},
            ],
        )
        session.add_all([project, style, page, panel])
        session.commit()

        prompt_json = assemble_panel_prompt(session, project, page, panel)
        prompt_text = prompt_json_to_text(prompt_json)

        assert prompt_json["style_bible"]["style_name"] == "Raincut Lantern Noir"
        assert prompt_json["style_bible"]["line_weight"].startswith("Medium-heavy")
        assert "wet ink silhouettes" in prompt_text
        assert "franchise resemblance" in prompt_json["negative_prompt"]

    SQLModel.metadata.drop_all(engine)
