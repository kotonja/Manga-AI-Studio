from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from manga_api.models import Page, Panel, PanelRenderPrompt, Project
from manga_api.rendering import assemble_panel_prompt, clean_strings, stable_seed


PROMPT_VERSION = "panel-render-director-v1"


@dataclass(frozen=True)
class RenderModeConfig:
    max_dimension: int
    detail_level: str
    retries: int
    qa_threshold: int
    provider_options: dict[str, Any]


RENDER_MODE_CONFIGS: dict[str, RenderModeConfig] = {
    "storyboard": RenderModeConfig(
        max_dimension=768,
        detail_level="loose readable storyboard draft, clear silhouettes, minimal polish",
        retries=0,
        qa_threshold=60,
        provider_options={"quality": "low", "steps": 12, "guidance": 3.0},
    ),
    "draft": RenderModeConfig(
        max_dimension=1024,
        detail_level="clean draft manga panel, readable acting and backgrounds",
        retries=1,
        qa_threshold=70,
        provider_options={"quality": "medium", "steps": 20, "guidance": 4.0},
    ),
    "final": RenderModeConfig(
        max_dimension=1536,
        detail_level="finished production manga panel with polished linework and tones",
        retries=2,
        qa_threshold=82,
        provider_options={"quality": "high", "steps": 32, "guidance": 5.5},
    ),
    "ultra": RenderModeConfig(
        max_dimension=2048,
        detail_level="highest fidelity final manga panel, dense controlled detail, print-ready values",
        retries=3,
        qa_threshold=90,
        provider_options={"quality": "high", "steps": 44, "guidance": 6.5},
    ),
}


class PanelRenderDirector:
    def __init__(self, session: Session) -> None:
        self.session = session

    def build_prompt(
        self,
        panel_id: uuid.UUID | str,
        *,
        provider_name: str = "mock",
        render_mode: str = "draft",
        seed: int | None = None,
        advanced_prompt_override: str | None = None,
        additional_user_instruction: str | None = None,
        camera_instruction: str | None = None,
        expression_instruction: str | None = None,
        preserve_layout: bool = True,
    ) -> PanelRenderPrompt:
        panel = self.session.get(Panel, uuid.UUID(str(panel_id)))
        if panel is None:
            raise ValueError("Panel not found")
        page = self.session.get(Page, panel.page_id)
        if page is None:
            raise ValueError("Panel page not found")
        project = self.session.get(Project, page.project_id)
        if project is None:
            raise ValueError("Panel project not found")

        mode = normalize_render_mode(render_mode)
        mode_config = RENDER_MODE_CONFIGS[mode]
        base_context = assemble_panel_prompt(self.session, project, page, panel)
        reference_pack = base_context.get("reference_pack") or {}
        story_memory = reference_pack.get("story_memory") or {}
        panel_plan = base_context.get("panel_plan") or story_memory.get("panel_plan") or {}
        page_plan = base_context.get("page_plan") or story_memory.get("page_plan") or {}
        style_bible = base_context.get("style_bible") or {}
        layout_context = build_layout_context(page, panel, preserve_layout)
        resolved_seed = seed if seed is not None else stable_seed(
            json.dumps(
                {
                    "panel_id": str(panel.id),
                    "mode": mode,
                    "panel_plan": panel_plan,
                    "layout": layout_context,
                    "instruction": additional_user_instruction or "",
                    "camera": camera_instruction or "",
                    "expression": expression_instruction or "",
                },
                sort_keys=True,
                default=str,
            )
        )
        size = size_for_mode(panel.width, panel.height, mode_config.max_dimension)

        director_context = {
            "prompt_version": PROMPT_VERSION,
            "render_mode": mode,
            "render_mode_config": {
                "resolution": size,
                "detail_level": mode_config.detail_level,
                "retries": mode_config.retries,
                "qa_threshold": mode_config.qa_threshold,
                "provider_options": mode_config.provider_options,
            },
            "project_metadata": {
                "id": str(project.id),
                "name": project.name,
                "description": project.description,
                "style_prompt": project.style_prompt,
            },
            "story_bible_summary": summarize_story(base_context.get("story_bible")),
            "chapter_summary": summarize_chapter(story_memory.get("chapter")),
            "scene_summary": summarize_scene(story_memory.get("scene")),
            "page_emotional_intent": page_emotional_intent(page_plan, panel_plan),
            "panel_story_beat": panel_plan.get("story_beat") or panel.prompt,
            "shot_type": panel_plan.get("shot_type"),
            "camera_angle": camera_instruction or panel_plan.get("camera_angle"),
            "composition": {
                **layout_context,
                "visual_notes": panel_plan.get("visual_notes"),
                "bubble_safe_area_instruction": bubble_safe_area_instruction(base_context),
            },
            "characters": character_director_context(reference_pack, base_context),
            "character_states": reference_pack.get("character_states", []),
            "location_anchors": location_director_context(reference_pack, base_context),
            "object_anchors": object_director_context(reference_pack, base_context),
            "style_dna": style_bible,
            "additional_user_instruction": additional_user_instruction,
            "expression_instruction": expression_instruction,
            "preserve_layout": preserve_layout,
            "seed": resolved_seed,
        }
        structured_context = {
            **base_context,
            "panel_render_director": director_context,
        }
        positive_prompt = advanced_prompt_override.strip() if advanced_prompt_override else build_positive_prompt(structured_context, mode_config)
        negative_prompt = build_negative_prompt(structured_context)

        prompt = PanelRenderPrompt(
            panel_id=panel.id,
            prompt_version=PROMPT_VERSION,
            provider_name=provider_name.lower().strip(),
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            structured_context=structured_context,
            reference_pack=reference_pack,
            size=size,
            seed=resolved_seed,
            quality_mode=mode,
        )
        prompt.created_at = utc_now()
        prompt.updated_at = prompt.created_at
        self.session.add(prompt)
        self.session.commit()
        self.session.refresh(prompt)
        return prompt

    @staticmethod
    def mode_options(render_mode: str, user_options: dict[str, Any] | None = None) -> dict[str, Any]:
        mode = normalize_render_mode(render_mode)
        config = RENDER_MODE_CONFIGS[mode]
        return {
            **config.provider_options,
            "render_mode": mode,
            "quality_mode": mode,
            "retries": config.retries,
            "qa_threshold": config.qa_threshold,
            **(user_options or {}),
        }


def build_layout_context(page: Page, panel: Panel, preserve_layout: bool) -> dict[str, Any]:
    layout = page.layout_json or {}
    bubble_safe_areas = layout.get("bubble_slots") or layout.get("bubble_safe_areas") or []
    return {
        "page_id": str(page.id),
        "page_number": page.page_number,
        "page_width": page.width,
        "page_height": page.height,
        "reading_direction": layout.get("reading_direction", "rtl"),
        "bleed": int(layout.get("bleed", 0)),
        "safe_margin": int(layout.get("safe_margin", 80)),
        "panel_id": str(panel.id),
        "panel_x": panel.x,
        "panel_y": panel.y,
        "panel_width": panel.width,
        "panel_height": panel.height,
        "polygon": panel.polygon,
        "reading_order": panel.reading_order,
        "preserve_panel_polygon": preserve_layout,
        "bubble_safe_areas": bubble_safe_areas,
    }


def summarize_story(story: dict[str, Any] | None) -> dict[str, Any] | None:
    if not story:
        return None
    return {
        "logline": story.get("logline"),
        "synopsis": story.get("synopsis"),
        "genre": story.get("genre"),
        "tone": story.get("tone"),
        "themes": story.get("themes", []),
        "main_conflict": story.get("main_conflict"),
        "continuity_rules": story.get("continuity_rules", []),
    }


def summarize_chapter(chapter: dict[str, Any] | None) -> dict[str, Any] | None:
    if not chapter:
        return None
    return {
        "chapter_number": chapter.get("chapter_number"),
        "title": chapter.get("title"),
        "summary": chapter.get("summary"),
        "goal": chapter.get("goal"),
    }


def summarize_scene(scene: dict[str, Any] | None) -> dict[str, Any] | None:
    if not scene:
        return None
    return {
        "title": scene.get("title"),
        "summary": scene.get("summary"),
        "location_name": scene.get("location_name"),
        "emotional_turn": scene.get("emotional_turn"),
        "characters": scene.get("characters", []),
    }


def page_emotional_intent(page_plan: dict[str, Any], panel_plan: dict[str, Any]) -> str:
    values = [
        str(page_plan.get("summary") or ""),
        str(page_plan.get("pacing") or ""),
        str(panel_plan.get("emotional_intent") or ""),
    ]
    return " | ".join(value for value in values if value)


def character_director_context(reference_pack: dict[str, Any], base_context: dict[str, Any]) -> list[dict[str, Any]]:
    entries = reference_pack.get("characters") or []
    if entries:
        result: list[dict[str, Any]] = []
        for entry in entries:
            card = entry.get("card") or {}
            result.append(
                {
                    "name": card.get("name"),
                    "identity_anchors": clean_strings(
                        [
                            card.get("canonical_visual_summary", ""),
                            card.get("face_anchor_description", ""),
                            card.get("hair_anchor_description", ""),
                            card.get("eye_anchor_description", ""),
                            card.get("body_anchor_description", ""),
                            card.get("outfit_anchor_description", ""),
                            card.get("face_description", ""),
                            card.get("hair_description", ""),
                            card.get("eye_description", ""),
                            card.get("body_type", ""),
                            card.get("outfit_default", ""),
                            card.get("scars_marks", ""),
                            *(card.get("silhouette_keywords") or []),
                            *(card.get("recurring_props") or []),
                            *(card.get("accessories") or []),
                        ]
                    ),
                    "forbidden_changes": clean_strings(
                        [
                            *(card.get("forbidden_changes") or []),
                            *(card.get("forbidden_variations") or []),
                        ]
                    ),
                    "state": entry.get("state"),
                    "reference_assets": entry.get("reference_assets", []),
                    "approved_panel_assets": entry.get("approved_panel_assets", []),
                }
            )
        return result
    return [
        {
            "name": character.get("name"),
            "identity_anchors": clean_strings(
                [
                    character.get("canonical_visual_summary", ""),
                    character.get("face_anchor_description", ""),
                    character.get("hair_anchor_description", ""),
                    character.get("eye_anchor_description", ""),
                    character.get("outfit_anchor_description", ""),
                    character.get("face_description", ""),
                    character.get("hair_description", ""),
                    character.get("eye_description", ""),
                    character.get("body_type", ""),
                    character.get("outfit_default", ""),
                ]
            ),
            "forbidden_changes": character.get("forbidden_changes", []),
            "state": None,
            "reference_assets": [],
            "approved_panel_assets": [],
        }
        for character in base_context.get("characters", [])
    ]


def location_director_context(reference_pack: dict[str, Any], base_context: dict[str, Any]) -> list[dict[str, Any]]:
    locations = reference_pack.get("locations") or base_context.get("locations") or []
    return [
        {
            "name": location.get("name"),
            "description": location.get("description"),
            "visual_notes": location.get("visual_notes"),
            "rules": location.get("rules", []),
        }
        for location in locations
    ]


def object_director_context(reference_pack: dict[str, Any], base_context: dict[str, Any]) -> list[dict[str, Any]]:
    objects = reference_pack.get("key_objects") or base_context.get("key_objects") or []
    return [
        {
            "name": key_object.get("name"),
            "description": key_object.get("description"),
            "significance": key_object.get("significance"),
            "visual_notes": key_object.get("visual_notes"),
        }
        for key_object in objects
    ]


def bubble_safe_area_instruction(context: dict[str, Any]) -> str:
    panel_plan = context.get("panel_plan") or {}
    has_dialogue = bool(panel_plan.get("dialogue") or panel_plan.get("narration"))
    if has_dialogue:
        return (
            "Reserve clean low-detail bubble-safe space for dialogue/narration. Do not draw final lettering, "
            "speech bubble outlines, or text into the image; lettering is composited later."
        )
    return "Keep important faces, hands, and action away from likely bubble areas; lettering may be added later."


def build_positive_prompt(context: dict[str, Any], mode_config: RenderModeConfig) -> str:
    director = context["panel_render_director"]
    style = director.get("style_dna") or {}
    story = director.get("story_bible_summary") or {}
    chapter = director.get("chapter_summary") or {}
    scene = director.get("scene_summary") or {}
    lines = [
        "Render a black-and-white original manga panel.",
        f"Detail target: {mode_config.detail_level}.",
        "Use crisp manga linework, controlled screentone, deliberate hatching, strong value grouping, and clean white gutters.",
        f"Project: {director['project_metadata']['name']}.",
        f"Story: {story.get('logline') or story.get('synopsis') or 'Use provided story continuity.'}",
        f"Chapter: {chapter.get('title') or ''} {chapter.get('summary') or ''}".strip(),
        f"Scene: {scene.get('summary') or ''} {scene.get('emotional_turn') or ''}".strip(),
        f"Page emotional intent: {director.get('page_emotional_intent') or 'maintain story pacing'}.",
        f"Panel story beat: {director.get('panel_story_beat') or 'render the planned panel beat'}.",
        f"Shot type: {director.get('shot_type') or 'story-appropriate shot'}; camera angle: {director.get('camera_angle') or 'story-appropriate angle'}.",
        f"Composition/layout: {json.dumps(director.get('composition'), ensure_ascii=True)}",
        f"Style DNA: {json.dumps(style, ensure_ascii=True)}",
        f"Characters and continuity: {json.dumps(director.get('characters'), ensure_ascii=True)}",
        f"Character states: {json.dumps(director.get('character_states'), ensure_ascii=True)}",
        f"Location anchors: {json.dumps(director.get('location_anchors'), ensure_ascii=True)}",
        f"Object anchors: {json.dumps(director.get('object_anchors'), ensure_ascii=True)}",
        director["composition"]["bubble_safe_area_instruction"],
        "Preserve character identity anchors, outfit/injury continuity, scene lighting, reading direction, and panel polygon composition.",
    ]
    for field in [
        "linework",
        "line_weight",
        "line_variation",
        "line_texture",
        "screentone",
        "screentone_strategy",
        "hatching",
        "hatching_strategy",
        "black_white_balance",
        "shadow_strategy",
        "positive_prompt_fragments",
        "prompt_style_positive",
    ]:
        value = style.get(field)
        if value:
            lines.append(f"{field}: {json.dumps(value, ensure_ascii=True)}")
    if director.get("expression_instruction"):
        lines.append(f"Expression variation: {director['expression_instruction']}")
    if director.get("additional_user_instruction"):
        lines.append(f"Additional user instruction: {director['additional_user_instruction']}")
    return "\n".join(line for line in lines if line)


def build_negative_prompt(context: dict[str, Any]) -> str:
    director = context["panel_render_director"]
    style = director.get("style_dna") or {}
    consistency = context.get("consistency_requirements") or {}
    common_failures = [
        "color render",
        "photorealistic style",
        "artist or franchise imitation",
        "muddy grayscale",
        "broken anatomy",
        "extra fingers",
        "wrong costume",
        "changed hairstyle",
        "missing recurring props",
        "unreadable silhouettes",
        "text baked into art",
        "speech bubble text",
        "cropped faces",
        "panel border inside image",
        "unsafe IP reference",
    ]
    values = [
        *common_failures,
        consistency.get("negative_prompt", ""),
        style.get("prompt_style_negative", ""),
        *(style.get("negative_prompt_fragments") or []),
        *(style.get("negative_prompts") or []),
        *(style.get("forbidden_artist_references") or []),
        *(style.get("forbidden_franchise_references") or []),
        *(style.get("forbidden_references") or []),
    ]
    for character in director.get("characters") or []:
        values.extend(character.get("forbidden_changes") or [])
    return "; ".join(clean_strings([str(value) for value in values]))


def size_for_mode(width: int, height: int, max_dimension: int) -> str:
    safe_width = max(64, int(width))
    safe_height = max(64, int(height))
    largest = max(safe_width, safe_height)
    if largest <= max_dimension:
        return f"{safe_width}x{safe_height}"
    scale = max_dimension / largest
    return f"{max(64, round(safe_width * scale))}x{max(64, round(safe_height * scale))}"


def normalize_render_mode(render_mode: str | None) -> str:
    normalized = (render_mode or "draft").lower().strip()
    if normalized not in RENDER_MODE_CONFIGS:
        return "draft"
    return normalized


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
