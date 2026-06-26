from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from manga_api.ai_tasks import AITaskRunner
from manga_api.db import get_session
from manga_api.llm import get_llm_provider
from manga_api.models import (
    Chapter,
    Character,
    KeyObject,
    Location,
    PagePlan,
    PanelPlan,
    Project,
    Scene,
    StoryBible,
    StyleBible,
)
from manga_api.schemas import (
    ChapterOutlineItem,
    ChapterPlanBatchResult,
    ChapterPlanResult,
    PagePlanBatchResult,
    PagePlanResult,
    PanelPlanResult,
    ScenePlanResult,
    StoryBibleCreate,
    StoryBibleResult,
    StoryCharacterResult,
    StoryKeyObjectResult,
    StoryLocationResult,
    StyleBibleResult,
)
from manga_api.versioning import VersioningService

router = APIRouter(tags=["story"])


def touch(row) -> None:
    row.updated_at = datetime.now(timezone.utc)


@router.get("/projects/{project_id}/story/bible", response_model=StoryBibleResult)
def get_story_bible(project_id: uuid.UUID, session: Session = Depends(get_session)) -> StoryBibleResult:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    story_bible = get_latest_story_bible(session, project_id)
    if story_bible is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story bible not found")
    return build_story_bible_result(session, story_bible)


@router.post("/projects/{project_id}/story/generate-bible", response_model=StoryBibleResult, status_code=status.HTTP_201_CREATED)
def generate_story_bible(
    project_id: uuid.UUID,
    payload: StoryBibleCreate,
    session: Session = Depends(get_session),
) -> StoryBibleResult:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    provider = get_llm_provider()
    result = AITaskRunner(session).run(
        "generate_story_bible",
        build_story_bible_inputs(project, payload),
        StoryBibleResult,
        provider,
    )

    story_bible = StoryBible(
        project_id=project.id,
        logline=result.logline,
        synopsis=result.synopsis,
        genre=result.genre,
        themes=result.themes,
        target_audience=result.target_audience,
        tone=result.tone,
        main_conflict=result.main_conflict,
        world_rules=result.world_rules,
        chapter_outline=[item.model_dump() for item in result.chapter_outline],
        continuity_rules=result.continuity_rules,
    )
    session.add(story_bible)
    session.flush()

    for character in result.characters:
        session.add(
            Character(
                project_id=project.id,
                story_bible_id=story_bible.id,
                name=character.name,
                role=character.role,
                description=character.description,
                traits=character.traits,
                visual_notes=character.visual_notes,
            )
        )

    for location in result.locations:
        session.add(
            Location(
                project_id=project.id,
                story_bible_id=story_bible.id,
                name=location.name,
                description=location.description,
                visual_notes=location.visual_notes,
                rules=location.rules,
            )
        )

    for key_object in result.key_objects:
        session.add(
            KeyObject(
                project_id=project.id,
                story_bible_id=story_bible.id,
                name=key_object.name,
                description=key_object.description,
                significance=key_object.significance,
                visual_notes=key_object.visual_notes,
            )
        )

    generated_style_bible = None
    if result.style_bible is not None:
        generated_style_bible = StyleBible(
            project_id=project.id,
            story_bible_id=story_bible.id,
            visual_style=result.style_bible.visual_style,
            line_art=result.style_bible.line_art,
            palette=result.style_bible.palette,
            paneling=result.style_bible.paneling,
            lettering=result.style_bible.lettering,
            negative_prompts=result.style_bible.negative_prompts,
        )
        session.add(generated_style_bible)

    touch(project)
    session.add(project)
    versioning = VersioningService(session)
    versioning.create_snapshot(story_bible, label="Story bible generated", reason="story_bible_generate")
    if generated_style_bible is not None:
        session.flush()
        versioning.create_snapshot(generated_style_bible, label="Style bible generated", reason="story_bible_generate")
    session.commit()
    session.refresh(story_bible)
    return build_story_bible_result(session, story_bible)


@router.post("/projects/{project_id}/story/generate-chapter-plan", response_model=list[ChapterPlanResult], status_code=status.HTTP_201_CREATED)
def generate_chapter_plan(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[ChapterPlanResult]:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    story_bible = get_latest_story_bible(session, project_id)
    if story_bible is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Generate a story bible first")

    provider = get_llm_provider()
    result = AITaskRunner(session).run(
        "generate_chapter_plan",
        {
            "project_name": project.name,
            "story_bible_logline": story_bible.logline,
            "chapter_outline": story_bible.chapter_outline,
        },
        ChapterPlanBatchResult,
        provider,
    )

    chapters: list[Chapter] = []
    for item in result.chapters:
        chapter = Chapter(
            project_id=project.id,
            story_bible_id=story_bible.id,
            chapter_number=item.chapter_number,
            title=item.title,
            summary=item.summary,
            goal=item.goal,
        )
        session.add(chapter)
        session.flush()
        for scene_item in item.scenes:
            session.add(
                Scene(
                    chapter_id=chapter.id,
                    scene_order=scene_item.scene_order,
                    title=scene_item.title,
                    summary=scene_item.summary,
                    location_name=scene_item.location_name,
                    emotional_turn=scene_item.emotional_turn,
                    characters=scene_item.characters,
                )
            )
        chapters.append(chapter)

    touch(project)
    session.add(project)
    session.commit()

    return [build_chapter_plan_result(session, chapter) for chapter in chapters]


@router.post("/chapters/{chapter_id}/story/generate-page-plans", response_model=list[PagePlanResult], status_code=status.HTTP_201_CREATED)
def generate_page_plans(
    chapter_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[PagePlanResult]:
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

    provider = get_llm_provider()
    result = AITaskRunner(session).run(
        "generate_page_plan",
        {
            "chapter_title": chapter.title,
            "chapter_summary": chapter.summary,
            "chapter_goal": chapter.goal,
        },
        PagePlanBatchResult,
        provider,
    )

    page_plans: list[PagePlan] = []
    for item in result.pages:
        page_plan = PagePlan(
            project_id=chapter.project_id,
            chapter_id=chapter.id,
            page_number=item.page_number,
            summary=item.summary,
            pacing=item.pacing,
            panel_count=len(item.panels),
            page_role=item.page_role,
            emotional_intensity=item.emotional_intensity,
            action_intensity=item.action_intensity,
            dialogue_density=item.dialogue_density,
            silence_level=item.silence_level,
            reveal_level=item.reveal_level,
            page_turn_importance=item.page_turn_importance,
            recommended_page_type=str(item.recommended_page_type),
            pacing_notes=item.pacing_notes,
        )
        session.add(page_plan)
        session.flush()
        for panel_item in item.panels:
            session.add(
                PanelPlan(
                    page_plan_id=page_plan.id,
                    panel_order=panel_item.panel_order,
                    story_beat=panel_item.story_beat,
                    shot_type=panel_item.shot_type,
                    camera_angle=panel_item.camera_angle,
                    characters=panel_item.characters,
                    location=panel_item.location,
                    dialogue=panel_item.dialogue,
                    narration=panel_item.narration,
                    visual_notes=panel_item.visual_notes,
                    emotional_intent=panel_item.emotional_intent,
                    beat_importance=panel_item.beat_importance,
                    time_duration=panel_item.time_duration,
                    camera_motion=panel_item.camera_motion,
                    motion_intensity=panel_item.motion_intensity,
                    dialogue_weight=panel_item.dialogue_weight,
                    silence=panel_item.silence,
                    impact_level=panel_item.impact_level,
                    recommended_panel_size=panel_item.recommended_panel_size,
                    transition_type=panel_item.transition_type,
                )
            )
        page_plans.append(page_plan)

    session.commit()
    return [build_page_plan_result(session, page_plan) for page_plan in page_plans]


@router.get("/projects/{project_id}/story/chapters", response_model=list[ChapterPlanResult])
def list_chapter_plans(project_id: uuid.UUID, session: Session = Depends(get_session)) -> list[ChapterPlanResult]:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    chapters = session.exec(
        select(Chapter)
        .where(Chapter.project_id == project.id)
        .order_by(Chapter.chapter_number.asc(), Chapter.created_at.asc())
    ).all()
    return [build_chapter_plan_result(session, chapter) for chapter in chapters]


@router.get("/chapters/{chapter_id}/story/page-plans", response_model=list[PagePlanResult])
def list_page_plans(chapter_id: uuid.UUID, session: Session = Depends(get_session)) -> list[PagePlanResult]:
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    page_plans = session.exec(
        select(PagePlan)
        .where(PagePlan.chapter_id == chapter.id)
        .order_by(PagePlan.page_number.asc(), PagePlan.created_at.asc())
    ).all()
    return [build_page_plan_result(session, page_plan) for page_plan in page_plans]


def get_latest_story_bible(session: Session, project_id: uuid.UUID) -> StoryBible | None:
    return session.exec(
        select(StoryBible)
        .where(StoryBible.project_id == project_id)
        .order_by(StoryBible.created_at.desc())
    ).first()


def build_story_bible_prompt(project: Project, payload: StoryBibleCreate) -> str:
    return "\n".join(
        [
            f"Project name: {project.name}",
            f"Project description: {project.description or 'None'}",
            f"Project style prompt: {project.style_prompt or 'None'}",
            f"Premise: {payload.premise or project.description or project.name}",
            f"Genre: {payload.genre or 'derive from premise'}",
            f"Tone: {payload.tone or 'derive from premise'}",
            f"Target audience: {payload.target_audience or 'derive from premise'}",
            f"Chapter count: {payload.chapter_count}",
        ]
    )


def build_story_bible_inputs(project: Project, payload: StoryBibleCreate) -> dict:
    return {
        "project_name": project.name,
        "project_description": project.description,
        "project_style_prompt": project.style_prompt,
        "premise": payload.premise or project.description or project.name,
        "genre": payload.genre or "derive from premise",
        "tone": payload.tone or "derive from premise",
        "target_audience": payload.target_audience or "derive from premise",
        "chapter_count": payload.chapter_count,
    }


def build_story_bible_result(session: Session, story_bible: StoryBible) -> StoryBibleResult:
    characters = session.exec(
        select(Character)
        .where(Character.story_bible_id == story_bible.id)
        .order_by(Character.created_at.asc())
    ).all()
    locations = session.exec(
        select(Location)
        .where(Location.story_bible_id == story_bible.id)
        .order_by(Location.created_at.asc())
    ).all()
    key_objects = session.exec(
        select(KeyObject)
        .where(KeyObject.story_bible_id == story_bible.id)
        .order_by(KeyObject.created_at.asc())
    ).all()
    style_bible = session.exec(
        select(StyleBible)
        .where(StyleBible.story_bible_id == story_bible.id)
        .order_by(StyleBible.created_at.desc())
    ).first()

    return StoryBibleResult(
        id=story_bible.id,
        project_id=story_bible.project_id,
        logline=story_bible.logline,
        synopsis=story_bible.synopsis,
        genre=story_bible.genre,
        themes=story_bible.themes,
        target_audience=story_bible.target_audience,
        tone=story_bible.tone,
        main_conflict=story_bible.main_conflict,
        world_rules=story_bible.world_rules,
        characters=[
            StoryCharacterResult(
                id=character.id,
                name=character.name,
                role=character.role,
                description=character.description,
                traits=character.traits,
                visual_notes=character.visual_notes,
            )
            for character in characters
        ],
        locations=[
            StoryLocationResult(
                id=location.id,
                name=location.name,
                description=location.description,
                visual_notes=location.visual_notes,
                rules=location.rules,
            )
            for location in locations
        ],
        key_objects=[
            StoryKeyObjectResult(
                id=key_object.id,
                name=key_object.name,
                description=key_object.description,
                significance=key_object.significance,
                visual_notes=key_object.visual_notes,
            )
            for key_object in key_objects
        ],
        chapter_outline=[ChapterOutlineItem.model_validate(item) for item in story_bible.chapter_outline],
        continuity_rules=story_bible.continuity_rules,
        style_bible=(
            StyleBibleResult(
                id=style_bible.id,
                visual_style=style_bible.visual_style,
                line_art=style_bible.line_art,
                palette=style_bible.palette,
                paneling=style_bible.paneling,
                lettering=style_bible.lettering,
                negative_prompts=style_bible.negative_prompts,
            )
            if style_bible is not None
            else None
        ),
        created_at=story_bible.created_at,
        updated_at=story_bible.updated_at,
    )


def build_chapter_plan_result(session: Session, chapter: Chapter) -> ChapterPlanResult:
    scenes = session.exec(
        select(Scene)
        .where(Scene.chapter_id == chapter.id)
        .order_by(Scene.scene_order.asc(), Scene.created_at.asc())
    ).all()
    return ChapterPlanResult(
        id=chapter.id,
        project_id=chapter.project_id,
        story_bible_id=chapter.story_bible_id,
        chapter_number=chapter.chapter_number,
        title=chapter.title,
        summary=chapter.summary,
        goal=chapter.goal,
        scenes=[
            ScenePlanResult(
                id=scene.id,
                scene_order=scene.scene_order,
                title=scene.title,
                summary=scene.summary,
                location_name=scene.location_name,
                emotional_turn=scene.emotional_turn,
                characters=scene.characters,
            )
            for scene in scenes
        ],
    )


def build_page_plan_result(session: Session, page_plan: PagePlan) -> PagePlanResult:
    panels = session.exec(
        select(PanelPlan)
        .where(PanelPlan.page_plan_id == page_plan.id)
        .order_by(PanelPlan.panel_order.asc(), PanelPlan.created_at.asc())
    ).all()
    return PagePlanResult(
        id=page_plan.id,
        project_id=page_plan.project_id,
        chapter_id=page_plan.chapter_id,
        page_number=page_plan.page_number,
        summary=page_plan.summary,
        pacing=page_plan.pacing,
        page_role=page_plan.page_role,
        emotional_intensity=page_plan.emotional_intensity,
        action_intensity=page_plan.action_intensity,
        dialogue_density=page_plan.dialogue_density,
        silence_level=page_plan.silence_level,
        reveal_level=page_plan.reveal_level,
        page_turn_importance=page_plan.page_turn_importance,
        recommended_page_type=page_plan.recommended_page_type,
        pacing_notes=page_plan.pacing_notes,
        panels=[
            PanelPlanResult(
                id=panel.id,
                page_plan_id=panel.page_plan_id,
                panel_order=panel.panel_order,
                story_beat=panel.story_beat,
                shot_type=panel.shot_type,
                camera_angle=panel.camera_angle,
                characters=panel.characters,
                location=panel.location,
                dialogue=panel.dialogue,
                narration=panel.narration,
                visual_notes=panel.visual_notes,
                emotional_intent=panel.emotional_intent,
                beat_importance=panel.beat_importance,
                time_duration=panel.time_duration,
                camera_motion=panel.camera_motion,
                motion_intensity=panel.motion_intensity,
                dialogue_weight=panel.dialogue_weight,
                silence=panel.silence,
                impact_level=panel.impact_level,
                recommended_panel_size=panel.recommended_panel_size,
                transition_type=panel.transition_type,
            )
            for panel in panels
        ],
    )
