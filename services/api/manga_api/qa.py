from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from sqlmodel import Session, select

from manga_api.compositor import get_latest_composite_asset
from manga_api.config import get_settings
from manga_api.lettering import fit_text_to_box
from manga_api.models import (
    Asset,
    Bubble,
    CharacterCard,
    GenerationJob,
    KeyObject,
    Page,
    PagePlan,
    Panel,
    PanelPlan,
    PanelRenderPrompt,
    Project,
    QAReport,
    Render,
    StoryBible,
    StyleBible,
)
from manga_api.reference_pack import ReferencePackBuilder, character_anchor_values, state_anchor_values
from manga_api.style_guard import evaluate_style_safety

QA_EXPORT_PRESETS: dict[str, tuple[int, int]] = {
    "draft": (640, 960),
    "web": (1200, 1800),
    "print": (1600, 2400),
}

DEFAULT_MAX_PANEL_OVERLAP_RATIO = 0.08
DEFAULT_MAX_BUBBLE_PANEL_COVERAGE = 0.35
MIN_PANEL_SHORT_SIDE = 96
MIN_RENDER_SHORT_SIDE = 512
MAX_BUBBLES_PER_PANEL = 3
SAFE_MARGIN_FALLBACK = 80


@dataclass(frozen=True)
class QAOptions:
    export_preset: str = "draft"
    max_bubble_panel_coverage: float = DEFAULT_MAX_BUBBLE_PANEL_COVERAGE
    max_panel_overlap_ratio: float = DEFAULT_MAX_PANEL_OVERLAP_RATIO


@dataclass(frozen=True)
class QADraft:
    target_type: str
    target_id: uuid.UUID
    overall_score: int
    scores: dict[str, Any]
    issues: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]
    blocking: bool


class AIQAProvider(Protocol):
    name: str

    def generate_report(self, context: dict[str, Any]) -> QADraft:
        """Return a QA report draft for the supplied target context."""


class MockQAProvider:
    name = "mock"

    def generate_report(self, context: dict[str, Any]) -> QADraft:
        issues: list[dict[str, Any]] = context["issues"]
        recommendations: list[dict[str, Any]] = context["recommendations"]
        scores: dict[str, Any] = context["scores"]
        blocking = any(issue.get("blocking") for issue in issues)
        penalties = sum(issue_penalty(issue) for issue in issues)
        overall_score = max(0, min(100, 100 - penalties))
        return QADraft(
            target_type=context["target_type"],
            target_id=context["target_id"],
            overall_score=overall_score,
            scores=scores,
            issues=issues,
            recommendations=recommendations,
            blocking=blocking,
        )


class OpenAIQAProvider:
    name = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.model_name = settings.openai_model

    def generate_report(self, context: dict[str, Any]) -> QADraft:
        raise RuntimeError("OpenAI multimodal QA critique is not implemented yet")


class PageQAService:
    def __init__(self, session: Session, provider: AIQAProvider | None = None) -> None:
        self.session = session
        self.provider = provider or MockQAProvider()

    def run_page_qa(self, page_id: uuid.UUID | str, options: QAOptions | None = None) -> QAReport:
        parsed_page_id = uuid.UUID(str(page_id))
        page = self.session.get(Page, parsed_page_id)
        if page is None:
            raise ValueError("Page not found")

        options = options or QAOptions()
        context = self._build_page_context(page, options)
        draft = self.provider.generate_report(context)
        summary = summarize_issues(draft.issues, "page", page.id)
        report = QAReport(
            target_type=draft.target_type,
            target_id=draft.target_id,
            issue_code=summary["issue_code"],
            issue_category=summary["issue_category"],
            severity=summary["severity"],
            confidence=summary["confidence"],
            page_id=page.id,
            panel_id=summary["panel_id"],
            auto_fix_available=summary["auto_fix_available"],
            auto_fix_action=summary["auto_fix_action"],
            overall_score=draft.overall_score,
            scores=draft.scores,
            issues=draft.issues,
            recommendations=draft.recommendations,
            blocking=draft.blocking,
        )
        self.session.add(report)
        self.session.commit()
        self.session.refresh(report)
        return report

    def _build_page_context(self, page: Page, options: QAOptions) -> dict[str, Any]:
        panels = self.session.exec(
            select(Panel)
            .where(Panel.page_id == page.id)
            .order_by(Panel.reading_order.asc(), Panel.created_at.asc())
        ).all()
        panel_ids = [panel.id for panel in panels]
        bubbles_by_panel = self._load_bubbles_by_panel(panel_ids)
        renders_by_panel = self._latest_renders_by_panel(panel_ids)
        render_jobs_by_panel = self._latest_render_jobs_by_panel(panel_ids)
        render_prompts_by_panel = self._latest_render_prompts_by_panel(panel_ids)
        issues: list[dict[str, Any]] = []
        recommendations: list[dict[str, Any]] = []

        page_plan = self.session.exec(
            select(PagePlan)
            .where(PagePlan.project_id == page.project_id, PagePlan.page_number == page.page_number)
            .order_by(PagePlan.created_at.desc())
        ).first()
        if page_plan is None:
            add_issue(
                issues,
                "page_plan_missing",
                "warning",
                "No page plan is available to verify panel count.",
                "page",
                page.id,
                blocking=False,
            )
            add_recommendation(recommendations, "Add or regenerate a page plan before final QA.", "page", page.id)
        elif page_plan.panel_count != len(panels):
            add_issue(
                issues,
                "panel_count_mismatch",
                "error",
                f"Page plan expects {page_plan.panel_count} panels, but layout has {len(panels)}.",
                "page",
                page.id,
                blocking=True,
                details={"expected": page_plan.panel_count, "actual": len(panels)},
            )
            add_recommendation(recommendations, "Update the page plan or add/remove panels to match it.", "page", page.id)

        panel_plans_by_order = self._panel_plans_by_order(page_plan)
        self._check_page_story(page, page_plan, issues, recommendations)
        self._check_reading_order(page, panels, issues, recommendations)

        for panel in panels:
            self._check_panel_bounds(page, panel, issues, recommendations)
            self._check_panel_size_and_margin(page, panel, issues, recommendations)
            if panel.id not in renders_by_panel:
                add_issue(
                    issues,
                    "panel_render_missing",
                    "error",
                    f"Panel {panel.reading_order} does not have a completed render asset.",
                    "panel",
                    panel.id,
                    panel_id=panel.id,
                    blocking=True,
                )
                add_recommendation(recommendations, f"Render panel {panel.reading_order} before export QA.", "panel", panel.id)
            else:
                self._check_render_quality(page, panel, renders_by_panel[panel.id], issues, recommendations)
            panel_plan = panel_plans_by_order.get(panel.reading_order)
            self._check_panel_story(page, panel, panel_plan, bubbles_by_panel.get(panel.id, []), issues, recommendations)
            self._check_consistency_pack(panel, render_jobs_by_panel.get(panel.id), render_prompts_by_panel.get(panel.id), issues, recommendations)

            for bubble in bubbles_by_panel.get(panel.id, []):
                self._check_bubble(page, panel, bubble, options, issues, recommendations)
            self._check_panel_bubble_density(page, panel, bubbles_by_panel.get(panel.id, []), issues, recommendations)

        self._check_panel_overlap(panels, options, issues, recommendations)
        self._check_composite(page, options, issues, recommendations)
        self._check_safety_and_style(page, issues, recommendations)
        for issue in issues:
            issue.setdefault("page_id", str(page.id))

        scores = score_categories(issues)
        return {
            "target_type": "page",
            "target_id": page.id,
            "provider": self.provider.name,
            "options": {
                "export_preset": options.export_preset,
                "max_bubble_panel_coverage": options.max_bubble_panel_coverage,
                "max_panel_overlap_ratio": options.max_panel_overlap_ratio,
            },
            "scores": scores,
            "issues": issues,
            "recommendations": recommendations,
        }

    def _panel_plans_by_order(self, page_plan: PagePlan | None) -> dict[int, PanelPlan]:
        if page_plan is None:
            return {}
        plans = self.session.exec(
            select(PanelPlan)
            .where(PanelPlan.page_plan_id == page_plan.id)
            .order_by(PanelPlan.panel_order.asc(), PanelPlan.created_at.asc())
        ).all()
        return {plan.panel_order: plan for plan in plans}

    def _check_page_story(
        self,
        page: Page,
        page_plan: PagePlan | None,
        issues: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> None:
        if page_plan is None:
            return
        if not page_plan.summary.strip():
            add_issue(
                issues,
                "page_story_beat_missing",
                "warning",
                "Page plan does not describe a clear story beat.",
                "page",
                page.id,
            )
            add_recommendation(recommendations, "Add a page summary that states the story turn.", "page", page.id)

    def _check_reading_order(
        self,
        page: Page,
        panels: list[Panel],
        issues: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> None:
        orders = [panel.reading_order for panel in panels]
        expected = list(range(1, len(panels) + 1))
        if len(set(orders)) != len(orders) or sorted(orders) != expected:
            add_issue(
                issues,
                "impossible_reading_order",
                "blocking",
                "Panel reading order must be unique and sequential.",
                "page",
                page.id,
                blocking=True,
                details={"orders": orders, "expected": expected},
            )
            add_recommendation(recommendations, "Renumber panels so reading order is 1..N without duplicates.", "page", page.id)

    def _check_panel_bounds(
        self,
        page: Page,
        panel: Panel,
        issues: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> None:
        outside = panel.x < 0 or panel.y < 0 or panel.x + panel.width > page.width or panel.y + panel.height > page.height
        polygon_outside = any(
            point.get("x", 0) < 0
            or point.get("y", 0) < 0
            or point.get("x", 0) > page.width
            or point.get("y", 0) > page.height
            for point in (panel.polygon or [])
        )
        if outside or polygon_outside:
            add_issue(
                issues,
                "panel_out_of_bounds",
                "error",
                f"Panel {panel.reading_order} extends outside the page bounds.",
                "panel",
                panel.id,
                panel_id=panel.id,
                blocking=True,
                details={"page_width": page.width, "page_height": page.height},
            )
            add_recommendation(recommendations, f"Move or resize panel {panel.reading_order} inside the page.", "panel", panel.id)

    def _check_panel_size_and_margin(
        self,
        page: Page,
        panel: Panel,
        issues: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> None:
        if min(panel.width, panel.height) < MIN_PANEL_SHORT_SIDE:
            add_issue(
                issues,
                "panel_too_tiny",
                "warning",
                f"Panel {panel.reading_order} is too small for reliable rendering and lettering.",
                "panel",
                panel.id,
                panel_id=panel.id,
                details={"width": panel.width, "height": panel.height, "min_short_side": MIN_PANEL_SHORT_SIDE},
            )
            add_recommendation(recommendations, f"Enlarge panel {panel.reading_order} or merge it with a nearby beat.", "panel", panel.id)

        layout = page.layout_json or {}
        safe_margin = int(layout.get("safe_margin", SAFE_MARGIN_FALLBACK))
        if panel.x < safe_margin or panel.y < safe_margin or panel.x + panel.width > page.width - safe_margin or panel.y + panel.height > page.height - safe_margin:
            add_issue(
                issues,
                "panel_unsafe_margin",
                "warning",
                f"Panel {panel.reading_order} crosses the page safe margin.",
                "panel",
                panel.id,
                panel_id=panel.id,
                details={"safe_margin": safe_margin},
            )
            add_recommendation(recommendations, "Keep important panel content inside the safe margin before export.", "panel", panel.id)

    def _check_render_quality(
        self,
        page: Page,
        panel: Panel,
        render: Render,
        issues: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> None:
        expected_ratio = panel.width / max(1, panel.height)
        actual_ratio = render.width / max(1, render.height)
        if abs(expected_ratio - actual_ratio) / max(expected_ratio, 0.01) > 0.25:
            add_issue(
                issues,
                "render_wrong_aspect_ratio",
                "warning",
                f"Panel {panel.reading_order} render aspect ratio does not match the panel frame.",
                "panel",
                panel.id,
                panel_id=panel.id,
                details={"panel_ratio": expected_ratio, "render_ratio": actual_ratio},
            )
            add_recommendation(recommendations, "Rerender the panel preserving layout size.", "panel", panel.id)

        if min(render.width, render.height) < MIN_RENDER_SHORT_SIDE:
            add_issue(
                issues,
                "render_resolution_too_low",
                "warning",
                f"Panel {panel.reading_order} render is below the minimum draft resolution.",
                "panel",
                panel.id,
                panel_id=panel.id,
                details={"width": render.width, "height": render.height, "min_short_side": MIN_RENDER_SHORT_SIDE},
            )
            add_recommendation(recommendations, "Rerender at draft or final quality before publishing.", "panel", panel.id)

    def _check_panel_story(
        self,
        page: Page,
        panel: Panel,
        panel_plan: PanelPlan | None,
        bubbles: list[Bubble],
        issues: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> None:
        if panel_plan is None:
            return
        if not panel_plan.story_beat.strip():
            add_issue(
                issues,
                "panel_story_beat_missing",
                "warning",
                f"Panel {panel.reading_order} has no clear story beat.",
                "panel",
                panel.id,
                panel_id=panel.id,
            )
        if not panel_plan.emotional_intent.strip():
            add_issue(
                issues,
                "panel_emotional_intent_missing",
                "warning",
                f"Panel {panel.reading_order} has no emotional intent.",
                "panel",
                panel.id,
                panel_id=panel.id,
            )
            add_recommendation(recommendations, "Add emotional intent to the panel plan so acting and composition can be checked.", "panel", panel.id)
        if panel_plan.dialogue and not panel_plan.characters:
            add_issue(
                issues,
                "dialogue_speaker_missing",
                "warning",
                f"Panel {panel.reading_order} has dialogue but no speaker in the panel plan.",
                "panel",
                panel.id,
                panel_id=panel.id,
            )
            add_recommendation(recommendations, "Assign a speaker character to dialogue in the panel plan.", "panel", panel.id)
        for bubble in bubbles:
            if (bubble.bubble_type or bubble.kind) == "speech" and bubble.text.strip() and bubble.speaker_character_id is None:
                add_issue(
                    issues,
                    "dialogue_speaker_missing",
                    "warning",
                    "A dialogue bubble has no speaker assigned.",
                    "bubble",
                    bubble.id,
                    panel_id=panel.id,
                    bubble_id=bubble.id,
                )
                break

    def _check_panel_overlap(
        self,
        panels: list[Panel],
        options: QAOptions,
        issues: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> None:
        for index, first in enumerate(panels):
            for second in panels[index + 1:]:
                overlap = rect_overlap(first, second)
                if overlap <= 0:
                    continue
                smaller_area = max(1, min(first.width * first.height, second.width * second.height))
                ratio = overlap / smaller_area
                if ratio > options.max_panel_overlap_ratio:
                    add_issue(
                        issues,
                        "panel_overlap_excessive",
                        "error",
                        f"Panels {first.reading_order} and {second.reading_order} overlap by {ratio:.0%} of the smaller panel.",
                        "panel",
                        first.id,
                        panel_id=first.id,
                        blocking=True,
                        details={"other_panel_id": str(second.id), "overlap_ratio": ratio},
                    )
                    add_recommendation(recommendations, "Adjust panel gutters so panels do not materially overlap.", "page", first.page_id)

    def _check_bubble(
        self,
        page: Page,
        panel: Panel,
        bubble: Bubble,
        options: QAOptions,
        issues: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> None:
        if bubble.x < 0 or bubble.y < 0 or bubble.x + bubble.width > page.width or bubble.y + bubble.height > page.height:
            add_issue(
                issues,
                "bubble_out_of_bounds",
                "error",
                "A bubble extends outside the page bounds.",
                "bubble",
                bubble.id,
                panel_id=panel.id,
                bubble_id=bubble.id,
                blocking=True,
            )
            add_recommendation(recommendations, "Move the bubble fully inside the page canvas.", "bubble", bubble.id)

        if not bubble.text.strip():
            add_issue(
                issues,
                "bubble_text_missing",
                "error",
                "A bubble has no lettering text.",
                "bubble",
                bubble.id,
                panel_id=panel.id,
                bubble_id=bubble.id,
                blocking=True,
            )
            add_recommendation(recommendations, "Add dialogue or narration text to the empty bubble.", "bubble", bubble.id)
        else:
            fit = fit_text_to_box(
                bubble.text,
                bubble.width,
                bubble.height,
                font_size=bubble.font_size,
                vertical_text=bubble.vertical_text,
                manual_override=True,
            )
            if fit.overflow:
                add_issue(
                    issues,
                    "bubble_text_overflow",
                    "warning",
                    "Bubble text is too long for the current lettering box.",
                    "bubble",
                    bubble.id,
                    panel_id=panel.id,
                    bubble_id=bubble.id,
                    details={"font_size": bubble.font_size, "width": bubble.width, "height": bubble.height},
                )
                add_recommendation(recommendations, "Shrink the bubble font, enlarge the bubble, or split the dialogue.", "bubble", bubble.id)

        coverage = (bubble.width * bubble.height) / max(1, panel.width * panel.height)
        if coverage > options.max_bubble_panel_coverage:
            add_issue(
                issues,
                "bubble_covers_panel",
                "warning",
                f"A bubble covers {coverage:.0%} of panel {panel.reading_order}.",
                "bubble",
                bubble.id,
                panel_id=panel.id,
                bubble_id=bubble.id,
                blocking=False,
                details={"coverage": coverage, "max_coverage": options.max_bubble_panel_coverage},
            )
            add_recommendation(recommendations, "Reduce the bubble size or split the text across bubbles.", "bubble", bubble.id)

    def _check_panel_bubble_density(
        self,
        page: Page,
        panel: Panel,
        bubbles: list[Bubble],
        issues: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> None:
        if len(bubbles) > MAX_BUBBLES_PER_PANEL:
            add_issue(
                issues,
                "too_many_bubbles_in_panel",
                "warning",
                f"Panel {panel.reading_order} has {len(bubbles)} bubbles, which may crowd the art.",
                "panel",
                panel.id,
                panel_id=panel.id,
                details={"bubble_count": len(bubbles), "max_bubbles": MAX_BUBBLES_PER_PANEL},
            )
            add_recommendation(recommendations, "Split dialogue across panels or use a narration box outside the main action.", "panel", panel.id)

    def _check_consistency_pack(
        self,
        panel: Panel,
        render_job: GenerationJob | None,
        render_prompt: PanelRenderPrompt | None,
        issues: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> None:
        try:
            reference_pack = ReferencePackBuilder(self.session).build_for_panel(panel.id)
        except ValueError as exc:
            add_issue(
                issues,
                "reference_pack_build_failed",
                "error",
                f"Could not build reference pack for panel {panel.reading_order}: {exc}",
                "panel",
                panel.id,
                panel_id=panel.id,
                blocking=False,
            )
            add_recommendation(recommendations, "Repair page, story, and panel links before running consistency QA.", "panel", panel.id)
            return

        missing_state_ids = reference_pack.get("missing_character_state_ids", [])
        if missing_state_ids:
            add_issue(
                issues,
                "character_state_missing",
                "warning",
                f"Panel {panel.reading_order} is missing active character state for {len(missing_state_ids)} character(s).",
                "panel",
                panel.id,
                panel_id=panel.id,
                blocking=False,
                details={"character_ids": missing_state_ids},
            )
            add_recommendation(recommendations, "Add chapter/scene/page character state before final rendering.", "panel", panel.id)

        prompt_json: dict[str, Any] | None = None
        prompt_text = ""
        if render_prompt is not None:
            prompt_json = render_prompt.structured_context if isinstance(render_prompt.structured_context, dict) else {}
            prompt_text = f"{render_prompt.positive_prompt}\n{render_prompt.negative_prompt}"
            if render_prompt.reference_pack:
                prompt_text = f"{prompt_text}\n{render_prompt.reference_pack}"
        elif render_job is not None:
            input_payload = render_job.input_payload if isinstance(render_job.input_payload, dict) else {}
            prompt_json = input_payload.get("prompt_json") if isinstance(input_payload.get("prompt_json"), dict) else None
            prompt_text = str(input_payload.get("prompt") or "")

        if render_job is None and render_prompt is None:
            return

        if not prompt_json or not prompt_json.get("reference_pack"):
            add_issue(
                issues,
                "reference_pack_missing",
                "warning",
                f"Panel {panel.reading_order} render metadata does not include a reference pack.",
                "panel",
                panel.id,
                panel_id=panel.id,
                blocking=False,
            )
            add_recommendation(recommendations, f"Re-render panel {panel.reading_order} with the consistency-aware renderer.", "panel", panel.id)
            return

        missing_anchors = missing_prompt_anchors(reference_pack, prompt_text)
        if missing_anchors:
            add_issue(
                issues,
                "character_anchor_missing_in_prompt",
                "warning",
                f"Panel {panel.reading_order} prompt omits {len(missing_anchors)} required character anchor(s).",
                "panel",
                panel.id,
                panel_id=panel.id,
                blocking=False,
                details={"missing_anchors": missing_anchors[:12]},
            )
            add_recommendation(recommendations, "Regenerate the panel prompt with character anchors and current state included.", "panel", panel.id)

        missing_state_anchors = missing_state_prompt_values(reference_pack, prompt_text)
        if missing_state_anchors:
            add_issue(
                issues,
                "outfit_injury_mismatch",
                "warning",
                f"Panel {panel.reading_order} prompt omits outfit or injury continuity details.",
                "panel",
                panel.id,
                panel_id=panel.id,
                details={"missing_state_anchors": missing_state_anchors[:12]},
            )
            add_recommendation(recommendations, "Rebuild the panel prompt with current outfit and injury state.", "panel", panel.id)

        missing_objects = missing_required_key_objects(reference_pack, prompt_text)
        if missing_objects:
            add_issue(
                issues,
                "key_object_missing_in_prompt",
                "warning",
                f"Panel {panel.reading_order} prompt is missing required key object references.",
                "panel",
                panel.id,
                panel_id=panel.id,
                details={"missing_key_objects": missing_objects[:12]},
            )
            add_recommendation(recommendations, "Rebuild the panel prompt with required object anchors.", "panel", panel.id)

    def _check_composite(
        self,
        page: Page,
        options: QAOptions,
        issues: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> None:
        composite = get_latest_composite_asset(self.session, page.id)
        preset = QA_EXPORT_PRESETS.get(options.export_preset, QA_EXPORT_PRESETS["draft"])
        if composite is None:
            add_issue(
                issues,
                "composite_missing",
                "error",
                "No final composed page exists yet.",
                "page",
                page.id,
                blocking=True,
                details={"export_preset": options.export_preset},
            )
            add_recommendation(recommendations, "Compose the page before export QA.", "page", page.id)
            return

        width = int(composite.metadata_json.get("width", page.width))
        height = int(composite.metadata_json.get("height", page.height))
        if width < preset[0] or height < preset[1]:
            add_issue(
                issues,
                "export_resolution_too_low",
                "error",
                f"Composite resolution {width}x{height} is below the {options.export_preset} preset.",
                "page",
                page.id,
                blocking=True,
                details={"width": width, "height": height, "minimum_width": preset[0], "minimum_height": preset[1]},
            )
            add_recommendation(recommendations, "Increase page size or select a lower export preset.", "page", page.id)

        render_asset_ids = composite.metadata_json.get("panel_render_asset_ids", {})
        approved_asset_ids = composite.metadata_json.get("approved_render_asset_ids", {})
        if isinstance(render_asset_ids, dict) and isinstance(approved_asset_ids, dict):
            unapproved_panel_ids = [
                panel_id
                for panel_id, asset_id in render_asset_ids.items()
                if asset_id and approved_asset_ids.get(panel_id) != asset_id
            ]
            if unapproved_panel_ids:
                add_issue(
                    issues,
                    "unapproved_render_used_in_composite",
                    "warning",
                    "The composed page includes render assets that have not been approved.",
                    "page",
                    page.id,
                    details={"panel_ids": unapproved_panel_ids},
                )
                add_recommendation(recommendations, "Approve the chosen render versions or rerun composition after approval.", "page", page.id)

    def _check_safety_and_style(
        self,
        page: Page,
        issues: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> None:
        project = self.session.get(Project, page.project_id)
        if project is None:
            return
        story = self.session.exec(
            select(StoryBible)
            .where(StoryBible.project_id == project.id)
            .order_by(StoryBible.created_at.desc())
        ).first()
        style = self.session.get(StyleBible, project.active_style_bible_id) if project.active_style_bible_id else None
        if style is None:
            style = self.session.exec(
                select(StyleBible)
                .where(StyleBible.project_id == project.id)
                .order_by(StyleBible.created_at.desc())
            ).first()
        characters = self.session.exec(
            select(CharacterCard)
            .where(CharacterCard.project_id == project.id)
            .order_by(CharacterCard.name.asc())
        ).all()
        payload = {
            "project_description": project.description or "",
            "project_style_prompt": project.style_prompt or "",
            "story_synopsis": story.synopsis if story else "",
            "story_logline": story.logline if story else "",
            "style": style_to_safety_payload(style),
            "characters": [character_to_safety_payload(character) for character in characters],
        }
        safety = evaluate_style_safety(payload)
        for guard_issue in safety.issues:
            guard_code = "forbidden_franchise_reference_detected" if "franchise" in guard_issue.code else "forbidden_style_reference_detected"
            category = "safety" if "franchise" in guard_issue.code else "style"
            severity = "blocking" if guard_issue.severity == "error" else "warning"
            add_issue(
                issues,
                guard_code,
                severity,
                guard_issue.message,
                "page",
                page.id,
                blocking=severity == "blocking",
                details={
                    "guard_code": guard_issue.code,
                    "field": guard_issue.field,
                    "matched_text": guard_issue.matched_text,
                    "suggested_style": safety.suggested_style,
                },
                category=category,
                confidence=0.95,
            )
            add_recommendation(recommendations, "Rewrite risky references into original visual attributes.", "page", page.id)

    def _load_bubbles_by_panel(self, panel_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[Bubble]]:
        bubbles_by_panel: dict[uuid.UUID, list[Bubble]] = {panel_id: [] for panel_id in panel_ids}
        if not panel_ids:
            return bubbles_by_panel
        bubbles = self.session.exec(
            select(Bubble)
            .where(Bubble.panel_id.in_(panel_ids))
            .order_by(Bubble.created_at.asc())
        ).all()
        for bubble in bubbles:
            bubbles_by_panel.setdefault(bubble.panel_id, []).append(bubble)
        return bubbles_by_panel

    def _latest_renders_by_panel(self, panel_ids: list[uuid.UUID]) -> dict[uuid.UUID, Render]:
        renders_by_panel: dict[uuid.UUID, Render] = {}
        if not panel_ids:
            return renders_by_panel
        renders = self.session.exec(
            select(Render, GenerationJob)
            .join(GenerationJob, GenerationJob.id == Render.job_id)
            .where(Render.panel_id.in_(panel_ids), GenerationJob.status == "succeeded")
            .order_by(Render.created_at.desc())
        ).all()
        for render, _job in renders:
            renders_by_panel.setdefault(render.panel_id, render)
        return renders_by_panel

    def _latest_render_jobs_by_panel(self, panel_ids: list[uuid.UUID]) -> dict[uuid.UUID, GenerationJob]:
        jobs_by_panel: dict[uuid.UUID, GenerationJob] = {}
        if not panel_ids:
            return jobs_by_panel
        jobs = self.session.exec(
            select(GenerationJob)
            .where(
                GenerationJob.panel_id.in_(panel_ids),
                GenerationJob.job_type == "render_panel",
                GenerationJob.status == "succeeded",
            )
            .order_by(GenerationJob.created_at.desc())
        ).all()
        for job in jobs:
            if job.panel_id is not None:
                jobs_by_panel.setdefault(job.panel_id, job)
        return jobs_by_panel

    def _latest_render_prompts_by_panel(self, panel_ids: list[uuid.UUID]) -> dict[uuid.UUID, PanelRenderPrompt]:
        prompts_by_panel: dict[uuid.UUID, PanelRenderPrompt] = {}
        if not panel_ids:
            return prompts_by_panel
        prompts = self.session.exec(
            select(PanelRenderPrompt)
            .where(PanelRenderPrompt.panel_id.in_(panel_ids))
            .order_by(PanelRenderPrompt.created_at.desc(), PanelRenderPrompt.id.desc())
        ).all()
        for prompt in prompts:
            prompts_by_panel.setdefault(prompt.panel_id, prompt)
        return prompts_by_panel


def get_qa_provider(provider_name: str) -> AIQAProvider:
    normalized = provider_name.lower().strip()
    if normalized == "mock":
        return MockQAProvider()
    if normalized == "openai":
        return OpenAIQAProvider()
    raise ValueError(f"Unsupported QA provider: {provider_name}")


def latest_qa_report(session: Session, target_type: str, target_id: uuid.UUID) -> QAReport | None:
    return session.exec(
        select(QAReport)
        .where(QAReport.target_type == target_type, QAReport.target_id == target_id)
        .order_by(QAReport.created_at.desc())
    ).first()


def build_qa_options(export_preset: str = "draft", max_bubble_panel_coverage: float | None = None) -> QAOptions:
    settings = get_settings()
    selected_preset = export_preset if export_preset in QA_EXPORT_PRESETS else settings.qa_export_preset
    if selected_preset not in QA_EXPORT_PRESETS:
        selected_preset = "draft"
    return QAOptions(
        export_preset=selected_preset,
        max_bubble_panel_coverage=max_bubble_panel_coverage or settings.qa_max_bubble_panel_coverage,
        max_panel_overlap_ratio=settings.qa_max_panel_overlap_ratio,
    )


def add_issue(
    issues: list[dict[str, Any]],
    code: str,
    severity: str,
    message: str,
    target_type: str,
    target_id: uuid.UUID | None,
    *,
    panel_id: uuid.UUID | None = None,
    bubble_id: uuid.UUID | None = None,
    blocking: bool = False,
    details: dict[str, Any] | None = None,
    category: str | None = None,
    confidence: float = 1.0,
) -> None:
    normalized_severity = "blocking" if severity == "error" and blocking else severity
    normalized_blocking = blocking or normalized_severity == "blocking"
    issue_category = category or ISSUE_CATEGORY_BY_CODE.get(code, "layout")
    auto_fix_action = auto_fix_action_for(code, target_type, target_id, panel_id, bubble_id)
    issues.append(
        {
            "id": f"{code}-{len(issues) + 1}",
            "code": code,
            "issue_code": code,
            "category": issue_category,
            "issue_category": issue_category,
            "severity": normalized_severity,
            "confidence": confidence,
            "message": message,
            "target_type": target_type,
            "target_id": str(target_id) if target_id is not None else None,
            "page_id": str(target_id) if target_type == "page" and target_id is not None else None,
            "panel_id": str(panel_id) if panel_id is not None else None,
            "bubble_id": str(bubble_id) if bubble_id is not None else None,
            "blocking": normalized_blocking,
            "auto_fix_available": bool(auto_fix_action),
            "auto_fix_action": auto_fix_action,
            "details": details or {},
        }
    )


def add_recommendation(
    recommendations: list[dict[str, Any]],
    message: str,
    target_type: str,
    target_id: uuid.UUID | None,
    *,
    details: dict[str, Any] | None = None,
) -> None:
    recommendations.append(
        {
            "id": f"recommendation-{len(recommendations) + 1}",
            "message": message,
            "target_type": target_type,
            "target_id": str(target_id) if target_id is not None else None,
            "details": details or {},
        }
    )


def rect_overlap(first: Panel, second: Panel) -> int:
    left = max(first.x, second.x)
    top = max(first.y, second.y)
    right = min(first.x + first.width, second.x + second.width)
    bottom = min(first.y + first.height, second.y + second.height)
    if right <= left or bottom <= top:
        return 0
    return (right - left) * (bottom - top)


ISSUE_CATEGORY_BY_CODE = {
    "page_plan_missing": "story",
    "page_story_beat_missing": "story",
    "panel_story_beat_missing": "story",
    "panel_emotional_intent_missing": "story",
    "dialogue_speaker_missing": "story",
    "panel_count_mismatch": "story",
    "panel_out_of_bounds": "layout",
    "panel_overlap_excessive": "layout",
    "impossible_reading_order": "layout",
    "panel_too_tiny": "layout",
    "panel_unsafe_margin": "layout",
    "panel_render_missing": "render",
    "render_wrong_aspect_ratio": "render",
    "render_resolution_too_low": "render",
    "unapproved_render_used_in_composite": "render",
    "bubble_out_of_bounds": "lettering",
    "bubble_text_missing": "lettering",
    "bubble_text_overflow": "lettering",
    "bubble_covers_panel": "lettering",
    "too_many_bubbles_in_panel": "lettering",
    "reference_pack_build_failed": "continuity",
    "character_state_missing": "continuity",
    "reference_pack_missing": "continuity",
    "character_anchor_missing_in_prompt": "continuity",
    "outfit_injury_mismatch": "continuity",
    "key_object_missing_in_prompt": "continuity",
    "composite_missing": "export",
    "export_resolution_too_low": "export",
    "forbidden_franchise_reference_detected": "safety",
    "forbidden_style_reference_detected": "style",
}


AUTO_FIX_BY_CODE = {
    "bubble_out_of_bounds": "move_bubble_inside_page",
    "bubble_text_overflow": "shrink_overflowing_text",
    "panel_count_mismatch": "regenerate_page_layout",
    "panel_overlap_excessive": "regenerate_page_layout",
    "panel_out_of_bounds": "regenerate_page_layout",
    "impossible_reading_order": "regenerate_page_layout",
    "character_anchor_missing_in_prompt": "rebuild_panel_prompt",
    "reference_pack_missing": "rebuild_panel_prompt",
    "outfit_injury_mismatch": "rebuild_panel_prompt",
    "key_object_missing_in_prompt": "rebuild_panel_prompt",
    "panel_render_missing": "mark_page_for_rerender",
    "render_wrong_aspect_ratio": "mark_page_for_rerender",
    "render_resolution_too_low": "mark_page_for_rerender",
    "composite_missing": "create_missing_composition",
}


def auto_fix_action_for(
    code: str,
    target_type: str,
    target_id: uuid.UUID | None,
    panel_id: uuid.UUID | None,
    bubble_id: uuid.UUID | None,
) -> dict[str, Any]:
    action_type = AUTO_FIX_BY_CODE.get(code)
    if action_type is None:
        return {}
    return {
        "type": action_type,
        "issue_code": code,
        "target_type": target_type,
        "target_id": str(target_id) if target_id is not None else None,
        "panel_id": str(panel_id) if panel_id is not None else None,
        "bubble_id": str(bubble_id) if bubble_id is not None else None,
        "safe": True,
    }


def score_categories(issues: list[dict[str, Any]]) -> dict[str, int]:
    categories = {
        "story": 100,
        "layout": 100,
        "render": 100,
        "lettering": 100,
        "consistency": 100,
        "export": 100,
        "safety": 100,
        "style": 100,
    }
    for issue in issues:
        category = str(issue.get("issue_category") or issue.get("category") or ISSUE_CATEGORY_BY_CODE.get(str(issue.get("code")), "layout"))
        categories.setdefault(category, 100)
        categories[category] = max(0, categories[category] - issue_penalty(issue))
    return categories


def missing_prompt_anchors(reference_pack: dict[str, Any], prompt_text: str) -> list[str]:
    normalized_prompt = prompt_text.casefold()
    missing: list[str] = []
    for entry in reference_pack.get("characters", []):
        card = entry.get("card", {})
        values = [*character_anchor_values(card), *state_anchor_values(entry.get("state"))]
        for value in values:
            cleaned = str(value).strip()
            if len(cleaned) < 4:
                continue
            if cleaned.casefold() not in normalized_prompt:
                missing.append(cleaned)
    return missing


def missing_state_prompt_values(reference_pack: dict[str, Any], prompt_text: str) -> list[str]:
    normalized_prompt = prompt_text.casefold()
    missing: list[str] = []
    for entry in reference_pack.get("characters", []):
        for value in state_anchor_values(entry.get("state")):
            cleaned = str(value).strip()
            if len(cleaned) < 4:
                continue
            if cleaned.casefold() not in normalized_prompt:
                missing.append(cleaned)
    return missing


def missing_required_key_objects(reference_pack: dict[str, Any], prompt_text: str) -> list[str]:
    normalized_prompt = prompt_text.casefold()
    story_memory = reference_pack.get("story_memory") or {}
    panel_plan = story_memory.get("panel_plan") or {}
    panel_text = " ".join(
        str(panel_plan.get(key) or "")
        for key in ["story_beat", "visual_notes", "dialogue", "narration"]
    ).casefold()
    missing: list[str] = []
    for key_object in reference_pack.get("key_objects", []):
        name = str(key_object.get("name") or "").strip()
        if len(name) < 2:
            continue
        if name.casefold() in panel_text and name.casefold() not in normalized_prompt:
            missing.append(name)
    return missing


def summarize_issues(issues: list[dict[str, Any]], target_type: str, target_id: uuid.UUID) -> dict[str, Any]:
    ordered = sorted(issues, key=lambda issue: severity_rank(str(issue.get("severity"))), reverse=True)
    primary = ordered[0] if ordered else {}
    panel_id = primary.get("panel_id")
    return {
        "target_type": target_type,
        "target_id": target_id,
        "issue_code": primary.get("issue_code") or primary.get("code"),
        "issue_category": primary.get("issue_category") or primary.get("category"),
        "severity": primary.get("severity"),
        "confidence": float(primary.get("confidence", 1.0)) if primary else 1.0,
        "panel_id": uuid.UUID(str(panel_id)) if panel_id else None,
        "auto_fix_available": any(bool(issue.get("auto_fix_available")) for issue in issues),
        "auto_fix_action": primary.get("auto_fix_action") if primary.get("auto_fix_available") else {},
    }


def severity_rank(severity: str) -> int:
    if severity in {"blocking", "error"}:
        return 3
    if severity == "warning":
        return 2
    if severity == "info":
        return 1
    return 0


def style_to_safety_payload(style: StyleBible | None) -> dict[str, Any]:
    if style is None:
        return {}
    return {
        "name": style.name,
        "style_name": style.style_name,
        "style_intent": style.style_intent,
        "linework": style.linework,
        "prompt_style_positive": style.prompt_style_positive,
        "positive_prompt_fragments": style.positive_prompt_fragments,
        "face_shape_language": style.face_shape_language,
        "eye_design_language": style.eye_design_language,
    }


def character_to_safety_payload(character: CharacterCard) -> dict[str, Any]:
    return {
        "name": character.name,
        "aliases": character.aliases,
        "role": character.role,
        "canonical_visual_summary": character.canonical_visual_summary,
        "face_description": character.face_description,
        "hair_description": character.hair_description,
        "outfit_default": character.outfit_default,
        "forbidden_changes": character.forbidden_changes,
        "forbidden_variations": character.forbidden_variations,
    }


def issue_penalty(issue: dict[str, Any]) -> int:
    severity = issue.get("severity")
    if severity in {"blocking", "error"}:
        return 18 if issue.get("blocking") else 12
    if severity == "warning":
        return 7
    return 2
