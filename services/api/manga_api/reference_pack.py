from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from manga_api.models import (
    Asset,
    CharacterCard,
    CharacterReferenceAsset,
    CharacterState,
    Chapter,
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


class ReferencePackBuilder:
    def __init__(self, session: Session) -> None:
        self.session = session

    def build_for_panel(self, panel_id: uuid.UUID | str) -> dict[str, Any]:
        panel = self.session.get(Panel, uuid.UUID(str(panel_id)))
        if panel is None:
            raise ValueError("Panel not found")
        page = self.session.get(Page, panel.page_id)
        if page is None:
            raise ValueError("Panel page not found")
        project = self.session.get(Project, page.project_id)
        if project is None:
            raise ValueError("Panel project not found")

        story_bible = self._latest_story_bible(project.id)
        style_bible = self._active_style_bible(project)
        page_plan = self._page_plan(project.id, page.page_number)
        panel_plan = self._panel_plan(page_plan, panel.reading_order)
        chapter = self.session.get(Chapter, page_plan.chapter_id) if page_plan else None
        scene = self._scene_for_panel(chapter, panel_plan)
        character_cards = self._character_cards(project.id, panel_plan, scene)
        locations = self._locations(project.id, story_bible, panel_plan)
        key_objects = self._key_objects(project.id, story_bible)

        character_entries: list[dict[str, Any]] = []
        character_states: list[dict[str, Any]] = []
        approved_visual_references: list[dict[str, Any]] = []
        continuity_rules: list[str] = list(story_bible.continuity_rules if story_bible else [])
        required_anchor_names: list[str] = []
        missing_character_state_ids: list[str] = []

        for card in character_cards:
            state = self._best_character_state(card.id, chapter.id if chapter else None, scene.id if scene else None, page.id)
            reference_assets = self._reference_assets(card)
            approved_panel_assets = self._approved_panel_assets(card)
            if state is None:
                missing_character_state_ids.append(str(card.id))
            else:
                character_states.append(character_state_to_dict(state))

            character_entries.append(
                {
                    "card": character_card_to_dict(card),
                    "state": character_state_to_dict(state) if state else None,
                    "reference_assets": [character_reference_asset_to_dict(asset) for asset in reference_assets],
                    "approved_panel_assets": [asset_to_dict(asset) for asset in approved_panel_assets],
                    "missing_state": state is None,
                }
            )
            for asset in reference_assets:
                approved_visual_references.append(reference_asset_to_prompt_reference(asset, "character_reference"))
            for asset in approved_panel_assets:
                approved_visual_references.append(asset_to_prompt_reference(asset, "approved_panel"))

            continuity_rules.extend(card.continuity_rules)
            continuity_rules.extend(card.forbidden_changes)
            continuity_rules.extend(card.forbidden_variations)
            required_anchor_names.extend(character_required_anchor_names(card))

        return {
            "panel_id": str(panel.id),
            "page_id": str(page.id),
            "project_id": str(project.id),
            "style_bible": style_bible_to_dict(style_bible),
            "story_memory": story_memory_to_dict(story_bible, chapter, scene, page_plan, panel_plan),
            "characters": character_entries,
            "character_states": character_states,
            "locations": [location_to_story_result(location) for location in locations],
            "key_objects": [key_object_to_story_result(key_object) for key_object in key_objects],
            "approved_visual_references": dedupe_references(approved_visual_references),
            "continuity_rules": dedupe_strings(continuity_rules),
            "previous_summaries": self._previous_summaries(page, page_plan, panel),
            "required_anchor_names": dedupe_strings(required_anchor_names),
            "missing_character_state_ids": missing_character_state_ids,
        }

    def build_page_summary(self, page_id: uuid.UUID | str) -> dict[str, Any]:
        page = self.session.get(Page, uuid.UUID(str(page_id)))
        if page is None:
            raise ValueError("Page not found")
        panels = self.session.exec(
            select(Panel)
            .where(Panel.page_id == page.id)
            .order_by(Panel.reading_order.asc(), Panel.created_at.asc())
        ).all()
        summaries: list[dict[str, Any]] = []
        for panel in panels:
            pack = self.build_for_panel(panel.id)
            summaries.append(
                {
                    "panel_id": str(panel.id),
                    "reading_order": panel.reading_order,
                    "characters": [entry["card"]["name"] for entry in pack["characters"]],
                    "active_states": [entry["state"] for entry in pack["characters"] if entry["state"] is not None],
                    "missing_state_character_ids": pack["missing_character_state_ids"],
                    "warning": "Character state missing" if pack["missing_character_state_ids"] else None,
                }
            )
        return {"page_id": str(page.id), "panels": summaries}

    def _latest_story_bible(self, project_id: uuid.UUID) -> StoryBible | None:
        return self.session.exec(
            select(StoryBible)
            .where(StoryBible.project_id == project_id)
            .order_by(StoryBible.created_at.desc())
        ).first()

    def _active_style_bible(self, project: Project) -> StyleBible | None:
        if project.active_style_bible_id is not None:
            style_bible = self.session.get(StyleBible, project.active_style_bible_id)
            if style_bible is not None:
                return style_bible
        return self.session.exec(
            select(StyleBible)
            .where(StyleBible.project_id == project.id)
            .order_by(StyleBible.created_at.desc())
        ).first()

    def _page_plan(self, project_id: uuid.UUID, page_number: int) -> PagePlan | None:
        return self.session.exec(
            select(PagePlan)
            .where(PagePlan.project_id == project_id, PagePlan.page_number == page_number)
            .order_by(PagePlan.created_at.desc())
        ).first()

    def _panel_plan(self, page_plan: PagePlan | None, reading_order: int) -> PanelPlan | None:
        if page_plan is None:
            return None
        return self.session.exec(
            select(PanelPlan)
            .where(PanelPlan.page_plan_id == page_plan.id, PanelPlan.panel_order == reading_order)
            .order_by(PanelPlan.created_at.desc())
        ).first()

    def _scene_for_panel(self, chapter: Chapter | None, panel_plan: PanelPlan | None) -> Scene | None:
        if chapter is None:
            return None
        scenes = self.session.exec(
            select(Scene)
            .where(Scene.chapter_id == chapter.id)
            .order_by(Scene.scene_order.asc(), Scene.created_at.asc())
        ).all()
        if not scenes:
            return None
        if panel_plan is None:
            return scenes[0]
        panel_names = {name.casefold() for name in panel_plan.characters}
        for scene in scenes:
            if panel_names.intersection({name.casefold() for name in scene.characters}):
                return scene
        return scenes[0]

    def _character_cards(
        self,
        project_id: uuid.UUID,
        panel_plan: PanelPlan | None,
        scene: Scene | None,
    ) -> list[CharacterCard]:
        cards = list(
            self.session.exec(
                select(CharacterCard)
                .where(CharacterCard.project_id == project_id)
                .order_by(CharacterCard.name.asc(), CharacterCard.created_at.asc())
            ).all()
        )
        requested_names = set(panel_plan.characters if panel_plan else [])
        if not requested_names and scene is not None:
            requested_names = set(scene.characters)
        if not requested_names:
            return cards

        normalized = {name.casefold() for name in requested_names}
        matched = [
            card
            for card in cards
            if card.name.casefold() in normalized
            or any(alias.casefold() in normalized for alias in card.aliases)
        ]
        return matched or cards

    def _locations(
        self,
        project_id: uuid.UUID,
        story_bible: StoryBible | None,
        panel_plan: PanelPlan | None,
    ) -> list[Location]:
        query = select(Location).where(Location.project_id == project_id)
        if story_bible is not None:
            query = query.where(Location.story_bible_id == story_bible.id)
        locations = list(self.session.exec(query.order_by(Location.name.asc())).all())
        if panel_plan is None or not panel_plan.location:
            return locations
        requested = panel_plan.location.casefold()
        matched = [location for location in locations if location.name.casefold() == requested]
        return matched or locations

    def _key_objects(self, project_id: uuid.UUID, story_bible: StoryBible | None) -> list[KeyObject]:
        query = select(KeyObject).where(KeyObject.project_id == project_id)
        if story_bible is not None:
            query = query.where(KeyObject.story_bible_id == story_bible.id)
        return list(self.session.exec(query.order_by(KeyObject.name.asc())).all())

    def _best_character_state(
        self,
        character_id: uuid.UUID,
        chapter_id: uuid.UUID | None,
        scene_id: uuid.UUID | None,
        page_id: uuid.UUID,
    ) -> CharacterState | None:
        states = list(
            self.session.exec(
                select(CharacterState)
                .where(CharacterState.character_id == character_id)
                .order_by(CharacterState.created_at.desc())
            ).all()
        )
        if chapter_id is not None:
            states = [state for state in states if state.chapter_id == chapter_id]
        if not states:
            return None

        def score(state: CharacterState) -> tuple[int, datetime]:
            value = 0
            if state.page_id == page_id:
                value += 8
            elif state.page_id is None:
                value += 2
            if scene_id is not None and state.scene_id == scene_id:
                value += 4
            return value, state.updated_at

        return sorted(states, key=score, reverse=True)[0]

    def _reference_assets(self, card: CharacterCard) -> list[CharacterReferenceAsset]:
        assets = list(
            self.session.exec(
                select(CharacterReferenceAsset)
                .where(CharacterReferenceAsset.character_card_id == card.id)
                .order_by(CharacterReferenceAsset.created_at.desc())
            ).all()
        )
        if not card.reference_asset_ids:
            return assets
        wanted = set(card.reference_asset_ids)
        selected = [asset for asset in assets if str(asset.id) in wanted]
        return selected or assets

    def _approved_panel_assets(self, card: CharacterCard) -> list[Asset]:
        asset_ids = parse_uuid_list(card.approved_panel_asset_ids)
        if not asset_ids:
            return []
        return list(
            self.session.exec(
                select(Asset)
                .where(Asset.id.in_(asset_ids))
                .order_by(Asset.created_at.desc())
            ).all()
        )

    def _previous_summaries(self, page: Page, page_plan: PagePlan | None, panel: Panel) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        if page_plan is not None:
            previous_panel_plans = self.session.exec(
                select(PanelPlan)
                .where(PanelPlan.page_plan_id == page_plan.id, PanelPlan.panel_order < panel.reading_order)
                .order_by(PanelPlan.panel_order.desc())
            ).all()
            for panel_plan in previous_panel_plans[:3]:
                summaries.append(
                    {
                        "panel_id": str(panel.id),
                        "reading_order": panel_plan.panel_order,
                        "prompt": panel_plan.visual_notes,
                        "summary": panel_plan.story_beat,
                    }
                )
            previous_page_plans = self.session.exec(
                select(PagePlan)
                .where(PagePlan.project_id == page.project_id, PagePlan.page_number < page.page_number)
                .order_by(PagePlan.page_number.desc())
            ).all()
            for previous_page_plan in previous_page_plans[:2]:
                summaries.append(
                    {
                        "panel_id": str(panel.id),
                        "reading_order": previous_page_plan.page_number,
                        "prompt": previous_page_plan.pacing,
                        "summary": previous_page_plan.summary,
                    }
                )
        return summaries


def character_required_anchor_names(card: CharacterCard) -> list[str]:
    labels = ["name"]
    for field_name in [
        "canonical_visual_summary",
        "silhouette_keywords",
        "face_anchor_description",
        "hair_anchor_description",
        "eye_anchor_description",
        "body_anchor_description",
        "outfit_anchor_description",
        "recurring_props",
        "forbidden_changes",
        "forbidden_variations",
    ]:
        value = getattr(card, field_name)
        if value:
            labels.append(f"{card.name}:{field_name}")
    return labels


def character_anchor_values(card: dict[str, Any]) -> list[str]:
    values: list[str] = [str(card.get("name", ""))]
    for field_name in [
        "canonical_visual_summary",
        "face_anchor_description",
        "hair_anchor_description",
        "eye_anchor_description",
        "body_anchor_description",
        "outfit_anchor_description",
        "color_notes_even_for_bw",
    ]:
        value = str(card.get(field_name) or "").strip()
        if value:
            values.append(value)
    for field_name in ["silhouette_keywords", "recurring_props", "forbidden_changes", "forbidden_variations"]:
        values.extend(str(item) for item in card.get(field_name, []) if str(item).strip())
    return dedupe_strings(values)


def state_anchor_values(state: dict[str, Any] | None) -> list[str]:
    if state is None:
        return []
    values: list[str] = []
    for field_name in ["outfit_state", "injury_state", "emotional_state", "prop_state", "visibility_notes", "continuity_notes"]:
        value = str(state.get(field_name) or "").strip()
        if value:
            values.append(value)
    return dedupe_strings(values)


def story_memory_to_dict(
    story_bible: StoryBible | None,
    chapter: Chapter | None,
    scene: Scene | None,
    page_plan: PagePlan | None,
    panel_plan: PanelPlan | None,
) -> dict[str, Any]:
    return {
        "story_bible": story_bible_to_dict(story_bible),
        "chapter": chapter_to_dict(chapter),
        "scene": scene_to_dict(scene),
        "page_plan": page_plan_to_dict(page_plan),
        "panel_plan": panel_plan_to_dict(panel_plan),
    }


def story_bible_to_dict(story: StoryBible | None) -> dict[str, Any] | None:
    if story is None:
        return None
    return {
        "id": str(story.id),
        "logline": story.logline,
        "synopsis": story.synopsis,
        "genre": story.genre,
        "themes": story.themes,
        "target_audience": story.target_audience,
        "tone": story.tone,
        "main_conflict": story.main_conflict,
        "world_rules": story.world_rules,
        "chapter_outline": story.chapter_outline,
        "continuity_rules": story.continuity_rules,
    }


def chapter_to_dict(chapter: Chapter | None) -> dict[str, Any] | None:
    if chapter is None:
        return None
    return {
        "id": str(chapter.id),
        "chapter_number": chapter.chapter_number,
        "title": chapter.title,
        "summary": chapter.summary,
        "goal": chapter.goal,
    }


def scene_to_dict(scene: Scene | None) -> dict[str, Any] | None:
    if scene is None:
        return None
    return {
        "id": str(scene.id),
        "scene_order": scene.scene_order,
        "title": scene.title,
        "summary": scene.summary,
        "location_name": scene.location_name,
        "emotional_turn": scene.emotional_turn,
        "characters": scene.characters,
    }


def page_plan_to_dict(page_plan: PagePlan | None) -> dict[str, Any] | None:
    if page_plan is None:
        return None
    return {
        "id": str(page_plan.id),
        "chapter_id": str(page_plan.chapter_id),
        "page_number": page_plan.page_number,
        "summary": page_plan.summary,
        "pacing": page_plan.pacing,
        "panel_count": page_plan.panel_count,
    }


def panel_plan_to_dict(panel_plan: PanelPlan | None) -> dict[str, Any] | None:
    if panel_plan is None:
        return None
    return {
        "id": str(panel_plan.id),
        "panel_order": panel_plan.panel_order,
        "story_beat": panel_plan.story_beat,
        "shot_type": panel_plan.shot_type,
        "camera_angle": panel_plan.camera_angle,
        "characters": panel_plan.characters,
        "location": panel_plan.location,
        "dialogue": panel_plan.dialogue,
        "narration": panel_plan.narration,
        "visual_notes": panel_plan.visual_notes,
        "emotional_intent": panel_plan.emotional_intent,
    }


def style_bible_to_dict(style: StyleBible | None) -> dict[str, Any] | None:
    if style is None:
        return None
    return {
        "id": str(style.id),
        "name": style.name,
        "style_name": style.style_name,
        "style_intent": style.style_intent,
        "line_weight": style.line_weight,
        "line_variation": style.line_variation,
        "line_texture": style.line_texture,
        "face_shape_language": style.face_shape_language,
        "eye_design_language": style.eye_design_language,
        "nose_mouth_simplification": style.nose_mouth_simplification,
        "anatomy_proportions": style.anatomy_proportions,
        "hair_rendering": style.hair_rendering,
        "clothing_fold_style": style.clothing_fold_style,
        "background_density": style.background_density,
        "architecture_detail": style.architecture_detail,
        "shadow_strategy": style.shadow_strategy,
        "screentone_strategy": style.screentone_strategy,
        "hatching_strategy": style.hatching_strategy,
        "black_fill_ratio": style.black_fill_ratio,
        "speedline_style": style.speedline_style,
        "impact_frame_style": style.impact_frame_style,
        "panel_border_style": style.panel_border_style,
        "gutter_style": style.gutter_style,
        "sfx_shape_language": style.sfx_shape_language,
        "bubble_style": style.bubble_style,
        "emotional_visual_rules": style.emotional_visual_rules,
        "positive_prompt_fragments": style.positive_prompt_fragments,
        "negative_prompt_fragments": style.negative_prompt_fragments,
        "forbidden_artist_references": style.forbidden_artist_references,
        "forbidden_franchise_references": style.forbidden_franchise_references,
        "linework": style.linework or style.line_art,
        "screentone": style.screentone,
        "hatching": style.hatching,
        "black_white_balance": style.black_white_balance,
        "face_language": style.face_language,
        "anatomy_style": style.anatomy_style,
        "background_detail": style.background_detail,
        "panel_rhythm": style.panel_rhythm or style.paneling,
        "sfx_style": style.sfx_style,
        "typography_notes": style.typography_notes or style.lettering,
        "forbidden_references": style.forbidden_references,
        "prompt_style_positive": style.prompt_style_positive or style.visual_style,
        "prompt_style_negative": style.prompt_style_negative,
        "negative_prompts": style.negative_prompts,
    }


def character_card_to_dict(card: CharacterCard) -> dict[str, Any]:
    return {
        "id": str(card.id),
        "project_id": str(card.project_id),
        "name": card.name,
        "aliases": card.aliases,
        "age_range": card.age_range,
        "role": card.role,
        "personality": card.personality,
        "face_description": card.face_description,
        "hair_description": card.hair_description,
        "eye_description": card.eye_description,
        "body_type": card.body_type,
        "outfit_default": card.outfit_default,
        "accessories": card.accessories,
        "scars_marks": card.scars_marks,
        "voice_style": card.voice_style,
        "forbidden_changes": card.forbidden_changes,
        "continuity_rules": card.continuity_rules,
        "canonical_visual_summary": card.canonical_visual_summary,
        "silhouette_keywords": card.silhouette_keywords,
        "face_anchor_description": card.face_anchor_description,
        "hair_anchor_description": card.hair_anchor_description,
        "eye_anchor_description": card.eye_anchor_description,
        "body_anchor_description": card.body_anchor_description,
        "outfit_anchor_description": card.outfit_anchor_description,
        "color_notes_even_for_bw": card.color_notes_even_for_bw,
        "recurring_props": card.recurring_props,
        "allowed_variations": card.allowed_variations,
        "forbidden_variations": card.forbidden_variations,
        "current_story_state": card.current_story_state,
        "injury_state": card.injury_state,
        "emotional_baseline": card.emotional_baseline,
        "reference_asset_ids": card.reference_asset_ids,
        "approved_panel_asset_ids": card.approved_panel_asset_ids,
        "created_at": card.created_at.isoformat(),
        "updated_at": card.updated_at.isoformat(),
    }


def character_state_to_dict(state: CharacterState | None) -> dict[str, Any] | None:
    if state is None:
        return None
    return {
        "id": str(state.id),
        "character_id": str(state.character_id),
        "chapter_id": str(state.chapter_id),
        "scene_id": str(state.scene_id),
        "page_id": str(state.page_id) if state.page_id is not None else None,
        "outfit_state": state.outfit_state,
        "injury_state": state.injury_state,
        "emotional_state": state.emotional_state,
        "prop_state": state.prop_state,
        "visibility_notes": state.visibility_notes,
        "continuity_notes": state.continuity_notes,
        "created_at": state.created_at.isoformat(),
        "updated_at": state.updated_at.isoformat(),
    }


def character_reference_asset_to_dict(asset: CharacterReferenceAsset) -> dict[str, Any]:
    return {
        "id": str(asset.id),
        "project_id": str(asset.project_id),
        "character_card_id": str(asset.character_card_id),
        "filename": asset.filename,
        "kind": asset.kind,
        "content_type": asset.content_type,
        "size_bytes": asset.size_bytes,
        "storage_key": asset.storage_key,
        "metadata_json": asset.metadata_json,
        "created_at": asset.created_at.isoformat(),
        "updated_at": asset.updated_at.isoformat(),
    }


def asset_to_dict(asset: Asset) -> dict[str, Any]:
    return {
        "id": str(asset.id),
        "project_id": str(asset.project_id) if asset.project_id is not None else None,
        "filename": asset.filename,
        "kind": asset.kind,
        "content_type": asset.content_type,
        "size_bytes": asset.size_bytes,
        "storage_key": asset.storage_key,
        "metadata_json": asset.metadata_json,
        "created_at": asset.created_at.isoformat(),
        "updated_at": asset.updated_at.isoformat(),
    }


def location_to_story_result(location: Location) -> dict[str, Any]:
    return {
        "id": str(location.id),
        "name": location.name,
        "description": location.description,
        "visual_notes": location.visual_notes,
        "rules": location.rules,
    }


def key_object_to_story_result(key_object: KeyObject) -> dict[str, Any]:
    return {
        "id": str(key_object.id),
        "name": key_object.name,
        "description": key_object.description,
        "significance": key_object.significance,
        "visual_notes": key_object.visual_notes,
    }


def reference_asset_to_prompt_reference(asset: CharacterReferenceAsset, kind: str) -> dict[str, Any]:
    return {
        "id": str(asset.id),
        "kind": kind,
        "filename": asset.filename,
        "content_type": asset.content_type,
        "storage_key": asset.storage_key,
        "metadata": asset.metadata_json,
    }


def asset_to_prompt_reference(asset: Asset, kind: str) -> dict[str, Any]:
    return {
        "id": str(asset.id),
        "kind": kind,
        "filename": asset.filename,
        "content_type": asset.content_type,
        "storage_key": asset.storage_key,
        "metadata": asset.metadata_json,
    }


def parse_uuid_list(values: list[str]) -> list[uuid.UUID]:
    parsed: list[uuid.UUID] = []
    for value in values:
        try:
            parsed.append(uuid.UUID(str(value)))
        except ValueError:
            continue
    return parsed


def dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def dedupe_references(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for value in values:
        key = str(value.get("id") or value.get("storage_key"))
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
