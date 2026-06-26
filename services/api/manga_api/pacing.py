from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from manga_api.models import Chapter, PagePlan, PanelPlan, Project
from manga_api.schemas import (
    PacingAnalysisResult,
    PacingPageAnalysis,
    PacingPanelAnalysis,
    PacingRebalanceResult,
    PacingRecommendation,
)
from manga_api.versioning import VersioningService


ACTION_WORDS = {
    "attack",
    "battle",
    "blast",
    "break",
    "charge",
    "chase",
    "clash",
    "crash",
    "cut",
    "dash",
    "duel",
    "explode",
    "fight",
    "impact",
    "kick",
    "punch",
    "slash",
    "speed",
    "strike",
    "sword",
}
EMOTION_WORDS = {
    "afraid",
    "anger",
    "cry",
    "despair",
    "fear",
    "grief",
    "hope",
    "lonely",
    "love",
    "rage",
    "regret",
    "sad",
    "tender",
    "tired",
    "tremble",
}
REVEAL_WORDS = {
    "appears",
    "discovers",
    "final",
    "ghost",
    "hidden",
    "secret",
    "truth",
    "turn",
    "twist",
    "unknown",
    "unmask",
    "reveal",
}
HORROR_WORDS = {"blood", "curse", "dark", "dread", "haunt", "horror", "shrine", "silence", "stalk", "terror"}
ROMANCE_WORDS = {"blush", "confess", "gentle", "heart", "love", "pause", "romance", "tender"}
COMEDY_WORDS = {"awkward", "bit", "comedy", "funny", "gag", "joke", "reaction", "ridiculous"}


@dataclass
class PageBundle:
    page: PagePlan
    panels: list[PanelPlan]


class PacingAnalyzer:
    def __init__(self, session: Session) -> None:
        self.session = session

    def analyze_project(self, project_id: uuid.UUID | str, *, persist: bool = True) -> PacingAnalysisResult:
        project = self._require(Project, project_id, "Project not found")
        bundles = self._project_bundles(project.id)
        return self._analyze_bundles(project.id, None, bundles, persist=persist)

    def analyze_chapter(self, chapter_id: uuid.UUID | str, *, persist: bool = True) -> PacingAnalysisResult:
        chapter = self._require(Chapter, chapter_id, "Chapter not found")
        bundles = self._chapter_bundles(chapter.id)
        return self._analyze_bundles(chapter.project_id, chapter.id, bundles, persist=persist)

    def rebalance_chapter(self, chapter_id: uuid.UUID | str) -> PacingRebalanceResult:
        chapter = self._require(Chapter, chapter_id, "Chapter not found")
        project = self._require(Project, chapter.project_id, "Project not found")
        version = VersioningService(self.session).create_snapshot(
            project,
            label=f"Pacing before chapter {chapter.chapter_number} rebalance",
            reason="before_pacing_rebalance",
        )
        before = self.analyze_chapter(chapter.id, persist=True)
        updated_pages: set[uuid.UUID] = set()
        updated_panels: set[uuid.UUID] = set()
        bundles = {bundle.page.id: bundle for bundle in self._chapter_bundles(chapter.id)}

        for recommendation in before.recommendations:
            bundle = bundles.get(recommendation.target_id) if recommendation.target_type == "page_plan" else None
            if bundle is None and recommendation.page_number is not None:
                bundle = next((candidate for candidate in bundles.values() if candidate.page.page_number == recommendation.page_number), None)
            if bundle is None:
                continue
            page = bundle.page
            if recommendation.code == "overcrowded_dialogue":
                page.recommended_page_type = "dialogue_scene"
                page.panel_count = min(max(3, page.panel_count), 6)
                page.pacing_notes = append_note(page.pacing_notes, "Trim dialogue or split the scene; keep one silent reaction beat.")
                panel = max(bundle.panels, key=lambda item: dialogue_weight(item), default=None)
                if panel is not None:
                    panel.dialogue_weight = min(panel.dialogue_weight, 65)
                    panel.visual_notes = append_note(panel.visual_notes, "Lettering pass should shorten this line.")
                    updated_panels.add(panel.id)
                    self.session.add(panel)
            elif recommendation.code == "boring_page":
                page.recommended_page_type = "reveal_page"
                page.emotional_intensity = max(page.emotional_intensity, 55)
                page.reveal_level = max(page.reveal_level, 45)
                page.pacing_notes = append_note(page.pacing_notes, "Add a stronger turn, contrast panel, or reveal image.")
            elif recommendation.code in {"suggest_splash_reveal", "page_turn_reveal"}:
                page.recommended_page_type = "reveal_page" if page.reveal_level >= page.action_intensity else "splash"
                page.page_turn_importance = max(page.page_turn_importance, 80)
                page.pacing_notes = append_note(page.pacing_notes, "Hold this beat for the page turn; use one dominant panel.")
                panel = max(bundle.panels, key=lambda item: item.beat_importance + item.impact_level, default=None)
                if panel is not None:
                    panel.recommended_panel_size = "dominant"
                    panel.time_duration = "held reveal"
                    updated_panels.add(panel.id)
                    self.session.add(panel)
            elif recommendation.code == "add_silent_panel":
                panel = min(bundle.panels, key=lambda item: dialogue_weight(item), default=None)
                if panel is not None:
                    panel.silence = True
                    panel.dialogue_weight = 0
                    panel.time_duration = "held pause"
                    panel.transition_type = "aspect_to_aspect"
                    panel.visual_notes = append_note(panel.visual_notes, "Silent beat: hold face, object, or environment without dialogue.")
                    updated_panels.add(panel.id)
                    self.session.add(panel)
                page.silence_level = max(page.silence_level, 55)
                page.pacing_notes = append_note(page.pacing_notes, "Add a silent beat before the next story action.")
            elif recommendation.code == "panel_count_change":
                if page.dialogue_density >= 70 or page.panel_count > 7:
                    page.panel_count = min(page.panel_count, 6)
                else:
                    page.panel_count = max(page.panel_count, 3)
                page.pacing_notes = append_note(page.pacing_notes, "Adjust planned panel count to match the beat importance.")
            else:
                page.pacing_notes = append_note(page.pacing_notes, recommendation.message)

            updated_pages.add(page.id)
            touch(page)
            self.session.add(page)

        self.session.commit()
        after = self.analyze_chapter(chapter.id, persist=True)
        return PacingRebalanceResult(
            **after.model_dump(),
            updated_page_plan_ids=sorted(updated_pages, key=str),
            updated_panel_plan_ids=sorted(updated_panels, key=str),
            version_ids=[version.id],
        )

    def _analyze_bundles(
        self,
        project_id: uuid.UUID,
        chapter_id: uuid.UUID | None,
        bundles: list[PageBundle],
        *,
        persist: bool,
    ) -> PacingAnalysisResult:
        pages: list[PacingPageAnalysis] = []
        recommendations: list[PacingRecommendation] = []
        for bundle in bundles:
            page_analysis = self._analyze_page(bundle)
            pages.append(page_analysis)
            recommendations.extend(self._page_recommendations(page_analysis))
            if persist:
                self._apply_page_analysis(bundle, page_analysis)

        if persist:
            self.session.commit()

        summary = build_summary(pages, recommendations)
        return PacingAnalysisResult(
            project_id=project_id,
            chapter_id=chapter_id,
            pages=pages,
            recommendations=recommendations,
            summary=summary,
        )

    def _analyze_page(self, bundle: PageBundle) -> PacingPageAnalysis:
        page = bundle.page
        panels = bundle.panels
        combined = " ".join(
            [
                page.summary,
                page.pacing,
                *[
                    " ".join(
                        [
                            panel.story_beat,
                            panel.visual_notes,
                            panel.emotional_intent,
                            panel.dialogue or "",
                            panel.narration or "",
                        ]
                    )
                    for panel in panels
                ],
            ]
        ).lower()
        dialogue_words = sum(word_count(panel.dialogue or "") + word_count(panel.narration or "") for panel in panels)
        panel_count = len(panels)
        action_intensity = score_keywords(combined, ACTION_WORDS, base=18, per_hit=12)
        emotional_intensity = max(score_keywords(combined, EMOTION_WORDS, base=24, per_hit=10), min(100, exclamation_count(combined) * 12 + 25))
        reveal_level = score_keywords(combined, REVEAL_WORDS, base=12, per_hit=13)
        dialogue_density = clamp(int(dialogue_words * 3.5 + panel_count * 4))
        silence_level = clamp(85 - dialogue_density + score_keywords(combined, {"silent", "silence", "pause", "still"}, base=0, per_hit=18))
        page_turn_importance = clamp(int(reveal_level * 0.7 + emotional_intensity * 0.25 + (18 if page.page_number % 2 == 0 else 0)))
        recommended_page_type = recommended_page_type_for(combined, action_intensity, emotional_intensity, dialogue_density, silence_level, reveal_level)
        page_role = page_role_for(combined, recommended_page_type, action_intensity, dialogue_density, reveal_level)

        panel_analyses = [self._analyze_panel(panel, index, panel_count) for index, panel in enumerate(panels)]
        notes = [
            f"Role: {page_role.replace('_', ' ')}.",
            f"Emotion {emotional_intensity}, action {action_intensity}, dialogue {dialogue_density}, reveal {reveal_level}.",
        ]
        if silence_level >= 60:
            notes.append("Silence opportunity is strong; hold a reaction, object, or environment.")
        if page_turn_importance >= 70:
            notes.append("Strong page-turn candidate.")
        if dialogue_density >= 70:
            notes.append("Dialogue density is high; trim or split lines.")

        return PacingPageAnalysis(
            page_plan_id=page.id,
            page_number=page.page_number,
            page_role=page_role,
            emotional_intensity=emotional_intensity,
            action_intensity=action_intensity,
            dialogue_density=dialogue_density,
            silence_level=silence_level,
            reveal_level=reveal_level,
            page_turn_importance=page_turn_importance,
            recommended_page_type=recommended_page_type,
            pacing_notes=" ".join(notes),
            panel_count=panel_count,
            panels=panel_analyses,
        )

    def _analyze_panel(self, panel: PanelPlan, index: int, panel_count: int) -> PacingPanelAnalysis:
        combined = " ".join(
            [
                panel.story_beat,
                panel.visual_notes,
                panel.emotional_intent,
                panel.dialogue or "",
                panel.narration or "",
                panel.shot_type,
                panel.camera_angle,
            ]
        ).lower()
        dialogue = dialogue_weight(panel)
        motion = score_keywords(combined, ACTION_WORDS | {"moving", "pan", "tilt", "zoom", "tracking"}, base=12, per_hit=11)
        impact = max(motion, score_keywords(combined, REVEAL_WORDS | {"impact", "hit", "shock"}, base=10, per_hit=15))
        emotion = score_keywords(combined, EMOTION_WORDS | HORROR_WORDS | ROMANCE_WORDS, base=18, per_hit=10)
        silence = dialogue == 0 and (emotion >= 45 or impact >= 45 or "silent" in combined or "pause" in combined)
        importance = clamp(int(impact * 0.45 + emotion * 0.35 + min(100, word_count(panel.story_beat) * 4) * 0.2))
        if index == panel_count - 1:
            importance = max(importance, impact, 55 if any(word in combined for word in REVEAL_WORDS) else importance)
        size = "dominant" if importance >= 80 else "large" if importance >= 65 else "small" if dialogue >= 75 else "medium"
        transition = "action_to_action" if motion >= 65 else "aspect_to_aspect" if silence else "subject_to_subject" if index > 0 else "scene_to_scene"
        duration = "held pause" if silence else "instant" if impact >= 75 else "long beat" if dialogue >= 70 else "normal"
        camera_motion = "tracking" if motion >= 65 else "push-in" if impact >= 60 else "still"
        notes = []
        if dialogue >= 70:
            notes.append("Dialogue-heavy panel.")
        if silence:
            notes.append("Silent pacing beat.")
        if impact >= 70:
            notes.append("Impact panel candidate.")

        return PacingPanelAnalysis(
            panel_plan_id=panel.id,
            panel_order=panel.panel_order,
            beat_importance=importance,
            time_duration=duration,
            camera_motion=camera_motion,
            motion_intensity=motion,
            dialogue_weight=dialogue,
            silence=silence,
            impact_level=impact,
            recommended_panel_size=size,
            transition_type=transition,
            notes=notes,
        )

    def _apply_page_analysis(self, bundle: PageBundle, analysis: PacingPageAnalysis) -> None:
        page = bundle.page
        page.page_role = analysis.page_role
        page.emotional_intensity = analysis.emotional_intensity
        page.action_intensity = analysis.action_intensity
        page.dialogue_density = analysis.dialogue_density
        page.silence_level = analysis.silence_level
        page.reveal_level = analysis.reveal_level
        page.page_turn_importance = analysis.page_turn_importance
        page.recommended_page_type = str(analysis.recommended_page_type)
        page.pacing_notes = analysis.pacing_notes
        page.panel_count = len(bundle.panels)
        touch(page)
        self.session.add(page)
        panels_by_id = {panel.id: panel for panel in bundle.panels}
        for panel_analysis in analysis.panels:
            panel = panels_by_id.get(panel_analysis.panel_plan_id)
            if panel is None:
                continue
            panel.beat_importance = panel_analysis.beat_importance
            panel.time_duration = panel_analysis.time_duration
            panel.camera_motion = panel_analysis.camera_motion
            panel.motion_intensity = panel_analysis.motion_intensity
            panel.dialogue_weight = panel_analysis.dialogue_weight
            panel.silence = panel_analysis.silence
            panel.impact_level = panel_analysis.impact_level
            panel.recommended_panel_size = panel_analysis.recommended_panel_size
            panel.transition_type = panel_analysis.transition_type
            touch(panel)
            self.session.add(panel)

    def _page_recommendations(self, analysis: PacingPageAnalysis) -> list[PacingRecommendation]:
        recommendations: list[PacingRecommendation] = []
        if analysis.dialogue_density >= 70 or analysis.panel_count > 7:
            recommendations.append(
                recommendation(
                    "overcrowded_dialogue",
                    "warning",
                    analysis,
                    "This page is dialogue-heavy or overcrowded.",
                    "suggest_dialogue_cuts",
                    {"dialogue_density": analysis.dialogue_density, "panel_count": analysis.panel_count},
                )
            )
        if analysis.emotional_intensity < 35 and analysis.action_intensity < 30 and analysis.reveal_level < 30 and analysis.dialogue_density < 45:
            recommendations.append(
                recommendation(
                    "boring_page",
                    "info",
                    analysis,
                    "This page may read flat; add a turn, contrast image, or sharper emotional beat.",
                    "increase_story_turn",
                    {},
                )
            )
        if analysis.reveal_level >= 65 or any(panel.impact_level >= 80 for panel in analysis.panels):
            recommendations.append(
                recommendation(
                    "suggest_splash_reveal",
                    "info",
                    analysis,
                    "A reveal or impact beat is strong enough for a splash or dominant panel.",
                    "suggest_splash_or_reveal_page",
                    {"recommended_page_type": analysis.recommended_page_type},
                )
            )
        if (analysis.emotional_intensity >= 60 or analysis.reveal_level >= 55) and analysis.silence_level < 55:
            recommendations.append(
                recommendation(
                    "add_silent_panel",
                    "info",
                    analysis,
                    "Add a silent panel to let the emotional turn breathe.",
                    "suggest_silent_panel",
                    {},
                )
            )
        if analysis.dialogue_density >= 75 or analysis.panel_count > 7 or (analysis.panel_count < 3 and analysis.emotional_intensity < 40):
            recommendations.append(
                recommendation(
                    "panel_count_change",
                    "info",
                    analysis,
                    "Panel count should change to better support this page's rhythm.",
                    "suggest_panel_count_change",
                    {"panel_count": analysis.panel_count},
                )
            )
        if analysis.page_turn_importance >= 65 and analysis.reveal_level >= 55:
            recommendations.append(
                recommendation(
                    "page_turn_reveal",
                    "info",
                    analysis,
                    "This is a strong page-turn reveal candidate.",
                    "hold_for_page_turn",
                    {"page_turn_importance": analysis.page_turn_importance},
                )
            )
        return recommendations

    def _project_bundles(self, project_id: uuid.UUID) -> list[PageBundle]:
        page_plans = self.session.exec(
            select(PagePlan)
            .where(PagePlan.project_id == project_id)
            .order_by(PagePlan.page_number.asc(), PagePlan.created_at.asc())
        ).all()
        return [self._bundle(page_plan) for page_plan in page_plans]

    def _chapter_bundles(self, chapter_id: uuid.UUID) -> list[PageBundle]:
        page_plans = self.session.exec(
            select(PagePlan)
            .where(PagePlan.chapter_id == chapter_id)
            .order_by(PagePlan.page_number.asc(), PagePlan.created_at.asc())
        ).all()
        return [self._bundle(page_plan) for page_plan in page_plans]

    def _bundle(self, page_plan: PagePlan) -> PageBundle:
        panels = self.session.exec(
            select(PanelPlan)
            .where(PanelPlan.page_plan_id == page_plan.id)
            .order_by(PanelPlan.panel_order.asc(), PanelPlan.created_at.asc())
        ).all()
        return PageBundle(page=page_plan, panels=list(panels))

    def _require(self, model, row_id: uuid.UUID | str, message: str):
        row = self.session.get(model, uuid.UUID(str(row_id)))
        if row is None:
            raise ValueError(message)
        return row


def recommendation(
    code: str,
    severity: str,
    analysis: PacingPageAnalysis,
    message: str,
    action: str,
    details: dict[str, Any],
) -> PacingRecommendation:
    return PacingRecommendation(
        code=code,
        severity=severity,
        target_type="page_plan",
        target_id=analysis.page_plan_id,
        page_number=analysis.page_number,
        message=message,
        suggested_action=action,
        details=details,
    )


def build_summary(pages: list[PacingPageAnalysis], recommendations: list[PacingRecommendation]) -> dict[str, Any]:
    count = max(1, len(pages))
    return {
        "page_count": len(pages),
        "average_emotional_intensity": round(sum(page.emotional_intensity for page in pages) / count, 1),
        "average_action_intensity": round(sum(page.action_intensity for page in pages) / count, 1),
        "average_dialogue_density": round(sum(page.dialogue_density for page in pages) / count, 1),
        "average_silence_level": round(sum(page.silence_level for page in pages) / count, 1),
        "page_turn_candidates": [page.page_number for page in pages if page.page_turn_importance >= 65],
        "recommendation_count": len(recommendations),
        "warning_count": sum(1 for item in recommendations if item.severity in {"warning", "blocking"}),
    }


def recommended_page_type_for(
    text: str,
    action: int,
    emotion: int,
    dialogue: int,
    silence: int,
    reveal: int,
) -> str:
    if any(word in text for word in HORROR_WORDS) and reveal >= 45:
        return "horror_build"
    if any(word in text for word in COMEDY_WORDS):
        return "comedy_reaction"
    if any(word in text for word in ROMANCE_WORDS) and emotion >= 45:
        return "romantic_pause"
    if reveal >= 65:
        return "reveal_page"
    if action >= 70:
        return "action_sequence"
    if emotion >= 75 and silence >= 55:
        return "silent_page"
    if dialogue >= 65:
        return "dialogue_scene"
    return "standard"


def page_role_for(text: str, page_type: str, action: int, dialogue: int, reveal: int) -> str:
    if page_type == "horror_build":
        return "horror_tension"
    if page_type == "comedy_reaction":
        return "comedy_timing"
    if page_type == "romantic_pause":
        return "romance_pause"
    if reveal >= 65:
        return "page_turn_reveal"
    if action >= 70:
        return "battle_impact"
    if dialogue >= 65:
        return "dialogue_exchange"
    if "silent" in text or "silence" in text:
        return "silent_beat"
    return "story_progression"


def dialogue_weight(panel: PanelPlan) -> int:
    return clamp((word_count(panel.dialogue or "") + word_count(panel.narration or "")) * 5)


def score_keywords(text: str, keywords: set[str], *, base: int, per_hit: int) -> int:
    hits = sum(1 for keyword in keywords if keyword in text)
    return clamp(base + hits * per_hit)


def word_count(text: str) -> int:
    return len([word for word in text.replace("\n", " ").split(" ") if word.strip()])


def exclamation_count(text: str) -> int:
    return text.count("!")


def clamp(value: int) -> int:
    return max(0, min(100, value))


def append_note(existing: str, note: str) -> str:
    existing = (existing or "").strip()
    if note in existing:
        return existing
    return f"{existing} {note}".strip()[:5000]


def touch(row: Any) -> None:
    row.updated_at = datetime.now(timezone.utc)
