from __future__ import annotations

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from manga_api.models import Chapter, PagePlan, PanelPlan, Project
from manga_api.pacing import PacingAnalyzer
from manga_api.versioning import VersioningService


def test_pacing_analyzer_produces_scores() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        project, chapter, _page = seed_pacing_page(
            session,
            summary="A lonely swordsman protects the ghost child as dread rises.",
            pacing="quiet reveal into action",
            dialogues=["Stay behind me.", ""],
            beats=["The swordsman sees a hidden enemy.", "The ghost child silently points at the ruined tower."],
        )

        result = PacingAnalyzer(session).analyze_chapter(chapter.id)

        assert result.project_id == project.id
        assert result.pages[0].emotional_intensity > 30
        assert result.pages[0].reveal_level > 20
        assert result.pages[0].panels[0].beat_importance > 0
        refreshed = session.get(PagePlan, result.pages[0].page_plan_id)
        assert refreshed is not None
        assert refreshed.recommended_page_type in {"standard", "reveal_page", "horror_build", "action_sequence", "silent_page"}


def test_overcrowded_dialogue_page_is_detected() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _project, chapter, _page = seed_pacing_page(
            session,
            summary="A crowded argument in the alley.",
            pacing="fast dialogue",
            dialogues=[
                "I need to explain every single thing before we move because the city is collapsing around us.",
                "You always explain too much and now the reader has no room to breathe at all.",
                "Then listen carefully because this curse has rules and every rule matters tonight.",
                "No, we need one short line and a silent reaction before the swords come out.",
            ],
            beats=["argument"] * 4,
        )

        result = PacingAnalyzer(session).analyze_chapter(chapter.id)

        assert result.pages[0].dialogue_density >= 70
        assert "overcrowded_dialogue" in {item.code for item in result.recommendations}


def test_page_turn_reveal_suggestion_works() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _project, chapter, _page = seed_pacing_page(
            session,
            page_number=2,
            summary="The final hidden truth appears: the ghost child knows the ruined city's secret.",
            pacing="slow dread reveal",
            dialogues=[""],
            beats=["A secret door opens and the unknown ghost army is revealed."],
        )

        result = PacingAnalyzer(session).analyze_chapter(chapter.id)

        codes = {item.code for item in result.recommendations}
        assert "page_turn_reveal" in codes
        assert result.pages[0].page_turn_importance >= 65


def test_rebalance_creates_version_snapshot() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        project, chapter, page = seed_pacing_page(
            session,
            summary="A heavy page of strategy dialogue before a reveal.",
            pacing="dense exposition",
            dialogues=[
                "This explanation is long because it carries all the rules of the ruined city and every hidden condition.",
                "The ghost pact, sword oath, moon gate, ash district, and old bells are all connected tonight.",
                "If we fail to explain this then the final attack will not make sense to anyone.",
            ],
            beats=["dense explanation", "rules explanation", "setup reveal"],
        )
        before_versions = VersioningService(session).list_project_versions(project.id)

        result = PacingAnalyzer(session).rebalance_chapter(chapter.id)

        after_versions = VersioningService(session).list_project_versions(project.id)
        refreshed = session.get(PagePlan, page.id)
        assert result.version_ids
        assert len(after_versions) > len(before_versions)
        assert refreshed is not None
        assert refreshed.pacing_notes
        assert refreshed.panel_count <= 6


def seed_pacing_page(
    session: Session,
    *,
    summary: str,
    pacing: str,
    dialogues: list[str],
    beats: list[str],
    page_number: int = 1,
) -> tuple[Project, Chapter, PagePlan]:
    project = Project(name="Pacing Test")
    chapter = Chapter(
        project_id=project.id,
        chapter_number=1,
        title="The Ruined City",
        summary="A lonely swordsman protects a ghost child.",
        goal="Test pacing.",
    )
    page = PagePlan(
        project_id=project.id,
        chapter_id=chapter.id,
        page_number=page_number,
        summary=summary,
        pacing=pacing,
        panel_count=len(beats),
    )
    session.add_all([project, chapter, page])
    session.flush()
    for index, beat in enumerate(beats, start=1):
        session.add(
            PanelPlan(
                page_plan_id=page.id,
                panel_order=index,
                story_beat=beat,
                shot_type="medium",
                camera_angle="eye level",
                characters=["Swordsman"],
                location="Ruined city",
                dialogue=dialogues[index - 1] if index - 1 < len(dialogues) else "",
                narration=None,
                visual_notes="Manga panel pacing test.",
                emotional_intent="tense",
            )
        )
    session.commit()
    return project, chapter, page
