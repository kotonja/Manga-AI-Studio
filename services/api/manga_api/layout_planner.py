from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from manga_api.models import LayoutTemplate, Page, PagePlan, Panel, PanelPlan, StyleBible
from manga_api.schemas import (
    LayoutPoint,
    LayoutSlot,
    LayoutSuggestionRead,
    LayoutValidationIssue,
    PageType,
    PanelLayoutInput,
    ReadingDirection,
    SuggestedPanelLayout,
)


DEFAULT_PAGE_WIDTH = 1600
DEFAULT_PAGE_HEIGHT = 2400
DEFAULT_SAFE_MARGIN = 80
KEY_BEAT_WORDS = (
    "reveal",
    "protect",
    "impact",
    "strike",
    "fight",
    "clash",
    "truth",
    "turn",
    "ghost",
    "danger",
    "resolve",
    "confession",
)
ACTION_WORDS = ("action", "fight", "strike", "slash", "chase", "impact", "explosion", "run", "battle")
DIALOGUE_WORDS = ("dialogue", "conversation", "argue", "whisper", "explain", "confess", "speak")


@dataclass(frozen=True)
class RectSpec:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def area(self) -> int:
        return self.width * self.height


class LayoutValidationError(ValueError):
    def __init__(self, issues: list[LayoutValidationIssue]) -> None:
        super().__init__("Layout validation failed")
        self.issues = issues


class LayoutPlanner:
    def __init__(self, session: Session | None = None) -> None:
        self.session = session

    def generate_layout(
        self,
        page_plan: PagePlan | None,
        style_bible: StyleBible | None,
        reading_direction: ReadingDirection | str,
        *,
        page: Page | None = None,
        page_type: PageType | str | None = None,
        template: LayoutTemplate | None = None,
        locked_panels: list[Panel] | None = None,
        safe_margin: int | None = None,
        bleed: int | None = None,
        min_gutter: int = 12,
    ) -> LayoutSuggestionRead:
        width = page.width if page is not None else DEFAULT_PAGE_WIDTH
        height = page.height if page is not None else DEFAULT_PAGE_HEIGHT
        layout_json = page.layout_json if page is not None else {}
        resolved_safe_margin = int(safe_margin if safe_margin is not None else layout_json.get("safe_margin", DEFAULT_SAFE_MARGIN))
        resolved_bleed = int(bleed if bleed is not None else layout_json.get("bleed", 0))
        resolved_direction = normalize_reading_direction(reading_direction)
        panel_plans = self._load_panel_plans(page_plan)
        resolved_page_type = normalize_page_type(page_type) or self._infer_page_type(page_plan, panel_plans)
        locked = sorted(locked_panels or [], key=lambda panel: panel.reading_order)
        desired_count = self._desired_panel_count(page_plan, panel_plans, resolved_page_type, len(locked))
        reasoning: list[str] = [
            f"Page type: {resolved_page_type}",
            f"Reading direction: {resolved_direction}",
            f"Safe margin: {resolved_safe_margin}px, gutter: {min_gutter}px",
        ]

        if style_bible is not None:
            style_hint = style_bible.panel_rhythm or style_bible.panel_border_style or style_bible.gutter_style
            if style_hint:
                reasoning.append(f"Style rhythm considered: {style_hint[:140]}")

        if template is not None:
            rects_by_order = self._rects_from_template(template, width, height, resolved_safe_margin, min_gutter)
            desired_count = max(desired_count, len(rects_by_order))
            reasoning.append(f"Template applied: {template.name}")
        else:
            rects_by_order = self._fallback_rects(
                desired_count,
                resolved_page_type,
                resolved_direction,
                width,
                height,
                resolved_safe_margin,
                min_gutter,
            )
            reasoning.append("Deterministic fallback layout generated from page type, pacing, and reading direction.")

        key_order = self._key_beat_order(panel_plans, page_plan, resolved_page_type)
        if key_order and key_order in rects_by_order:
            self._promote_key_beat(rects_by_order, key_order)
            reasoning.append(f"Panel {key_order} receives the dominant frame for the key beat.")

        panels = self._build_suggested_panels(
            rects_by_order,
            page_plan,
            panel_plans,
            resolved_page_type,
            resolved_direction,
            locked,
            desired_count,
        )
        panels = resolve_locked_overlaps(panels, width, height, resolved_safe_margin, min_gutter, resolved_direction)
        issues = validate_suggested_layout(
            panels,
            width,
            height,
            min_gutter,
            resolved_direction,
            resolved_page_type,
            key_order=key_order,
            safe_margin=resolved_safe_margin,
        )
        blocking = [issue for issue in issues if issue.severity == "error"]
        if blocking:
            raise LayoutValidationError(issues)

        return LayoutSuggestionRead(
            page_id=page.id if page is not None else uuid.UUID(int=0),
            width=width,
            height=height,
            bleed=resolved_bleed,
            safe_margin=resolved_safe_margin,
            reading_direction=resolved_direction,
            page_type=resolved_page_type,
            template_id=template.id if template is not None else None,
            layout_reasoning=reasoning,
            validation_issues=issues,
            panels=panels,
        )

    def _load_panel_plans(self, page_plan: PagePlan | None) -> list[PanelPlan]:
        if page_plan is None or self.session is None:
            return []
        return list(
            self.session.exec(
                select(PanelPlan)
                .where(PanelPlan.page_plan_id == page_plan.id)
                .order_by(PanelPlan.panel_order.asc(), PanelPlan.created_at.asc())
            ).all()
        )

    def _infer_page_type(self, page_plan: PagePlan | None, panel_plans: list[PanelPlan]) -> PageType:
        text = " ".join(
            [
                page_plan.summary if page_plan is not None else "",
                page_plan.pacing if page_plan is not None else "",
                " ".join(panel.story_beat for panel in panel_plans),
                " ".join(panel.emotional_intent for panel in panel_plans),
            ]
        ).lower()
        panel_count = page_plan.panel_count if page_plan is not None and page_plan.panel_count else len(panel_plans)
        dialogue_count = sum(1 for panel in panel_plans if panel.dialogue)
        if panel_count == 1 or "splash" in text:
            return "splash"
        if "reveal" in text or "turning point" in text:
            return "reveal_page"
        if any(word in text for word in ACTION_WORDS):
            return "action_sequence"
        if dialogue_count >= max(2, len(panel_plans) // 2) or any(word in text for word in DIALOGUE_WORDS):
            return "dialogue_scene"
        if "silent" in text or (panel_plans and dialogue_count == 0 and "quiet" in text):
            return "silent_page"
        if "horror" in text or "dread" in text:
            return "horror_build"
        if "romantic" in text or "tender" in text:
            return "romantic_pause"
        return "standard"

    def _desired_panel_count(
        self,
        page_plan: PagePlan | None,
        panel_plans: list[PanelPlan],
        page_type: PageType,
        locked_count: int,
    ) -> int:
        if page_type == "splash" and locked_count == 0:
            return 1
        planned_count = page_plan.panel_count if page_plan is not None else 0
        return max(1, locked_count, len(panel_plans), planned_count or 0)

    def _rects_from_template(
        self,
        template: LayoutTemplate,
        width: int,
        height: int,
        safe_margin: int,
        min_gutter: int,
    ) -> dict[int, RectSpec]:
        raw_panels = template.layout_json.get("panels") if isinstance(template.layout_json, dict) else None
        if not isinstance(raw_panels, list) or not raw_panels:
            return self._fallback_rects(
                template.panel_count,
                normalize_page_type(template.page_type) or "standard",
                normalize_reading_direction(template.reading_direction),
                width,
                height,
                safe_margin,
                min_gutter,
            )

        content = content_rect(width, height, safe_margin)
        rects: dict[int, RectSpec] = {}
        for index, raw in enumerate(raw_panels, start=1):
            if not isinstance(raw, dict):
                continue
            order = int(raw.get("reading_order") or raw.get("panel_order") or index)
            x = float(raw.get("x", 0))
            y = float(raw.get("y", 0))
            panel_width = float(raw.get("width", 0))
            panel_height = float(raw.get("height", 0))
            if 0 <= x <= 1 and 0 < panel_width <= 1:
                x = content.x + x * content.width
                panel_width = panel_width * content.width
            if 0 <= y <= 1 and 0 < panel_height <= 1:
                y = content.y + y * content.height
                panel_height = panel_height * content.height
            rects[order] = RectSpec(round(x), round(y), max(1, round(panel_width)), max(1, round(panel_height)))
        return rects

    def _fallback_rects(
        self,
        count: int,
        page_type: PageType,
        reading_direction: ReadingDirection,
        width: int,
        height: int,
        safe_margin: int,
        min_gutter: int,
    ) -> dict[int, RectSpec]:
        content = content_rect(width, height, safe_margin)
        gutter = max(8, min_gutter)
        if page_type == "splash" or count == 1:
            return {1: content}

        if page_type in {"reveal_page", "horror_build", "romantic_pause"} and count >= 3:
            return assign_reading_order(
                [
                    RectSpec(content.x, content.y, (content.width - gutter) // 2, round(content.height * 0.35) - gutter),
                    RectSpec(content.x + (content.width + gutter) // 2, content.y, (content.width - gutter) // 2, round(content.height * 0.35) - gutter),
                    RectSpec(content.x, content.y + round(content.height * 0.35), content.width, content.height - round(content.height * 0.35)),
                    *grid_rects_for_extra(content, gutter, count - 3, start_y_ratio=0.74),
                ][:count],
                reading_direction,
            )

        if page_type == "action_sequence" and count >= 4:
            top_height = round(content.height * 0.5)
            lower_height = content.height - top_height - gutter
            lower_count = count - 1
            lower_rects = row_rects(
                RectSpec(content.x, content.y + top_height + gutter, content.width, lower_height),
                lower_count,
                gutter,
            )
            return assign_reading_order(
                [RectSpec(content.x, content.y, content.width, top_height), *lower_rects],
                reading_direction,
            )

        if page_type == "dialogue_scene" and count >= 3:
            return assign_reading_order(dialogue_rects(content, count, gutter), reading_direction)

        return assign_reading_order(general_rects(content, count, gutter), reading_direction)

    def _key_beat_order(
        self,
        panel_plans: list[PanelPlan],
        page_plan: PagePlan | None,
        page_type: PageType,
    ) -> int | None:
        if not panel_plans:
            return 1 if page_type in {"splash", "reveal_page", "action_sequence"} else None
        best_order = panel_plans[-1].panel_order if page_type in {"reveal_page", "horror_build"} else panel_plans[0].panel_order
        best_score = -1
        for panel in panel_plans:
            text = " ".join([panel.story_beat, panel.visual_notes, panel.emotional_intent]).lower()
            score = sum(2 for word in KEY_BEAT_WORDS if word in text)
            if panel.shot_type.lower() in {"splash", "wide", "establishing"}:
                score += 1
            if panel.dialogue:
                score += 0
            if page_plan is not None and any(word in page_plan.summary.lower() for word in KEY_BEAT_WORDS):
                score += 1
            if score > best_score:
                best_order = panel.panel_order
                best_score = score
        return best_order if best_score > 0 or page_type in {"splash", "reveal_page", "action_sequence"} else None

    def _promote_key_beat(self, rects_by_order: dict[int, RectSpec], key_order: int) -> None:
        largest_order = max(rects_by_order, key=lambda order: rects_by_order[order].area)
        if largest_order != key_order:
            rects_by_order[largest_order], rects_by_order[key_order] = rects_by_order[key_order], rects_by_order[largest_order]

    def _build_suggested_panels(
        self,
        rects_by_order: dict[int, RectSpec],
        page_plan: PagePlan | None,
        panel_plans: list[PanelPlan],
        page_type: PageType,
        reading_direction: ReadingDirection,
        locked_panels: list[Panel],
        desired_count: int,
    ) -> list[SuggestedPanelLayout]:
        locked_by_order = {panel.reading_order: panel for panel in locked_panels}
        plans_by_order = {panel.panel_order: panel for panel in panel_plans}
        used_orders = sorted(set(rects_by_order) | set(locked_by_order))
        if len(used_orders) < desired_count:
            for order in range(1, desired_count + 1):
                if order not in used_orders:
                    used_orders.append(order)
        panels: list[SuggestedPanelLayout] = []
        fallback_rect = next(iter(rects_by_order.values()), RectSpec(80, 80, 640, 480))
        for order in sorted(used_orders)[: max(desired_count, len(used_orders))]:
            locked_panel = locked_by_order.get(order)
            rect = panel_rect(locked_panel) if locked_panel is not None else rects_by_order.get(order, fallback_rect)
            plan = plans_by_order.get(order)
            story_beat = plan.story_beat if plan is not None else (page_plan.summary if page_plan is not None else None)
            emotional_beat = plan.emotional_intent if plan is not None else page_type.replace("_", " ")
            prompt = plan.visual_notes if plan is not None else story_beat
            panels.append(
                SuggestedPanelLayout(
                    id=locked_panel.id if locked_panel is not None else None,
                    x=rect.x,
                    y=rect.y,
                    width=rect.width,
                    height=rect.height,
                    polygon=rect_polygon(rect),
                    reading_order=order,
                    prompt=prompt,
                    story_beat=story_beat,
                    emotional_beat=emotional_beat,
                    importance=importance_for_plan(plan, page_type),
                    locked=locked_panel is not None,
                    bubble_slots=bubble_slots_for_panel(rect, plan, page_type, reading_direction),
                    sfx_slots=sfx_slots_for_panel(rect, plan, page_type),
                )
            )
        return sorted(panels, key=lambda panel: panel.reading_order)


def validate_panel_inputs(
    panels: list[PanelLayoutInput],
    page_width: int,
    page_height: int,
    *,
    min_gutter: int = 8,
    reading_direction: ReadingDirection | str = "rtl",
) -> list[LayoutValidationIssue]:
    suggested = [
        SuggestedPanelLayout(
            id=panel.id,
            x=panel.x,
            y=panel.y,
            width=panel.width,
            height=panel.height,
            polygon=panel.polygon,
            reading_order=panel.reading_order,
            prompt=panel.prompt,
        )
        for panel in panels
    ]
    return validate_suggested_layout(
        suggested,
        page_width,
        page_height,
        min_gutter,
        normalize_reading_direction(reading_direction),
        "standard",
        key_order=None,
        safe_margin=0,
        include_reading_order_warning=False,
    )


def validate_suggested_layout(
    panels: list[SuggestedPanelLayout],
    page_width: int,
    page_height: int,
    min_gutter: int,
    reading_direction: ReadingDirection,
    page_type: PageType,
    *,
    key_order: int | None,
    safe_margin: int,
    include_reading_order_warning: bool = True,
) -> list[LayoutValidationIssue]:
    issues: list[LayoutValidationIssue] = []
    orders = [panel.reading_order for panel in panels]
    if len(orders) != len(set(orders)):
        issues.append(error_issue("duplicate_panel_order", "Panel reading order must be unique per page."))

    for panel in panels:
        if panel.x < 0 or panel.y < 0 or panel.x + panel.width > page_width or panel.y + panel.height > page_height:
            issues.append(error_issue("panel_outside_bounds", "Panel must stay inside page bounds.", panel.reading_order))
        for point in panel.polygon:
            if point.x < 0 or point.y < 0 or point.x > page_width or point.y > page_height:
                issues.append(error_issue("polygon_outside_bounds", "Panel polygon must stay inside page bounds.", panel.reading_order))

    for index, first in enumerate(panels):
        first_rect = RectSpec(first.x, first.y, first.width, first.height)
        for second in panels[index + 1 :]:
            second_rect = RectSpec(second.x, second.y, second.width, second.height)
            if overlap_area(first_rect, second_rect) > 0:
                issues.append(
                    error_issue(
                        "panel_overlap",
                        f"Panel {first.reading_order} overlaps panel {second.reading_order}.",
                        first.reading_order,
                    )
                )
                continue
            if gutter_too_small(first_rect, second_rect, min_gutter):
                issues.append(
                    error_issue(
                        "minimum_gutter",
                        f"Panels {first.reading_order} and {second.reading_order} need at least {min_gutter}px gutter.",
                        first.reading_order,
                    )
                )

    if include_reading_order_warning:
        expected = expected_reading_order(panels, reading_direction)
        if expected and expected != orders:
            issues.append(
                LayoutValidationIssue(
                    severity="warning",
                    code="reading_order_flow",
                    message=f"Panel order may not match {reading_direction} reading flow.",
                )
            )

    if key_order is not None and panels:
        largest_order = max(panels, key=lambda panel: panel.width * panel.height).reading_order
        if largest_order != key_order:
            issues.append(
                LayoutValidationIssue(
                    severity="warning",
                    code="key_beat_not_largest",
                    message=f"Panel {key_order} is the key beat but panel {largest_order} is larger.",
                    panel_order=key_order,
                )
            )

    if page_type == "splash":
        dominant = max((panel.width * panel.height for panel in panels), default=0)
        available = max(1, (page_width - safe_margin * 2) * (page_height - safe_margin * 2))
        if dominant / available < 0.6:
            issues.append(error_issue("splash_requires_dominant_panel", "Splash pages should have one dominant panel."))

    if page_type == "dialogue_scene":
        dialogue_panels = [panel for panel in panels if panel.bubble_slots]
        if not dialogue_panels:
            issues.append(error_issue("dialogue_needs_bubble_space", "Dialogue pages should preserve bubble space."))

    return issues


def normalize_reading_direction(value: ReadingDirection | str | None) -> ReadingDirection:
    if value in {"rtl", "ltr", "vertical-rl"}:
        return value  # type: ignore[return-value]
    return "rtl"


def normalize_page_type(value: PageType | str | None) -> PageType | None:
    allowed = {
        "standard",
        "splash",
        "double_spread_left",
        "double_spread_right",
        "silent_page",
        "action_sequence",
        "dialogue_scene",
        "reveal_page",
        "comedy_reaction",
        "horror_build",
        "romantic_pause",
        "exposition_page",
    }
    if value in allowed:
        return value  # type: ignore[return-value]
    return None


def content_rect(width: int, height: int, safe_margin: int) -> RectSpec:
    margin = min(max(0, safe_margin), max(0, min(width, height) // 3))
    return RectSpec(margin, margin, max(1, width - margin * 2), max(1, height - margin * 2))


def rect_polygon(rect: RectSpec) -> list[LayoutPoint]:
    return [
        LayoutPoint(x=rect.x, y=rect.y),
        LayoutPoint(x=rect.right, y=rect.y),
        LayoutPoint(x=rect.right, y=rect.bottom),
        LayoutPoint(x=rect.x, y=rect.bottom),
    ]


def panel_rect(panel: Panel) -> RectSpec:
    return RectSpec(panel.x, panel.y, panel.width, panel.height)


def assign_reading_order(rects: list[RectSpec], reading_direction: ReadingDirection) -> dict[int, RectSpec]:
    if reading_direction == "ltr":
        ordered = sorted(rects, key=lambda rect: (rect.y, rect.x))
    elif reading_direction == "vertical-rl":
        ordered = sorted(rects, key=lambda rect: (-rect.x, rect.y))
    else:
        ordered = sorted(rects, key=lambda rect: (rect.y, -rect.x))
    return {index: rect for index, rect in enumerate(ordered, start=1)}


def general_rects(content: RectSpec, count: int, gutter: int) -> list[RectSpec]:
    if count == 2:
        return row_rects(content, 2, gutter)
    if count == 3:
        top_height = (content.height - gutter) // 2
        bottom_height = content.height - top_height - gutter
        return [
            *row_rects(RectSpec(content.x, content.y, content.width, top_height), 2, gutter),
            RectSpec(content.x, content.y + top_height + gutter, content.width, bottom_height),
        ]
    columns = 2 if count <= 6 else 3
    rows = (count + columns - 1) // columns
    rect_width = (content.width - gutter * (columns - 1)) // columns
    rect_height = (content.height - gutter * (rows - 1)) // rows
    rects: list[RectSpec] = []
    for row in range(rows):
        for column in range(columns):
            if len(rects) >= count:
                return rects
            rects.append(
                RectSpec(
                    content.x + column * (rect_width + gutter),
                    content.y + row * (rect_height + gutter),
                    rect_width,
                    rect_height,
                )
            )
    return rects


def dialogue_rects(content: RectSpec, count: int, gutter: int) -> list[RectSpec]:
    rows = count
    rect_height = (content.height - gutter * (rows - 1)) // rows
    return [
        RectSpec(content.x, content.y + row * (rect_height + gutter), content.width, rect_height)
        for row in range(rows)
    ]


def row_rects(content: RectSpec, count: int, gutter: int) -> list[RectSpec]:
    if count <= 0:
        return []
    rect_width = (content.width - gutter * (count - 1)) // count
    return [
        RectSpec(content.x + index * (rect_width + gutter), content.y, rect_width, content.height)
        for index in range(count)
    ]


def grid_rects_for_extra(content: RectSpec, gutter: int, count: int, *, start_y_ratio: float) -> list[RectSpec]:
    if count <= 0:
        return []
    start_y = content.y + round(content.height * start_y_ratio)
    area = RectSpec(content.x, start_y, content.width, max(1, content.bottom - start_y))
    return general_rects(area, count, gutter)


def resolve_locked_overlaps(
    panels: list[SuggestedPanelLayout],
    page_width: int,
    page_height: int,
    safe_margin: int,
    min_gutter: int,
    reading_direction: ReadingDirection,
) -> list[SuggestedPanelLayout]:
    if not any(panel.locked for panel in panels):
        return panels
    gutter = max(8, min_gutter)
    content = content_rect(page_width, page_height, safe_margin)
    candidate_rects = [
        *general_rects(content, max(len(panels) + 4, 4), gutter),
        *general_rects(content, max(len(panels) + 8, 6), gutter),
    ]
    candidate_rects = list(assign_reading_order(candidate_rects, reading_direction).values())
    placed: list[RectSpec] = []
    resolved: list[SuggestedPanelLayout] = []
    for panel in sorted(panels, key=lambda item: item.reading_order):
        current = RectSpec(panel.x, panel.y, panel.width, panel.height)
        if panel.locked:
            placed.append(current)
            resolved.append(panel)
            continue
        selected = current
        if conflicts_with_any(current, placed, gutter):
            for candidate in candidate_rects:
                if not conflicts_with_any(candidate, placed, gutter):
                    selected = candidate
                    break
        placed.append(selected)
        if selected == current:
            resolved.append(panel)
        else:
            resolved.append(
                panel.model_copy(
                    update={
                        "x": selected.x,
                        "y": selected.y,
                        "width": selected.width,
                        "height": selected.height,
                        "polygon": rect_polygon(selected),
                        "bubble_slots": move_slots(panel.bubble_slots, current, selected),
                        "sfx_slots": move_slots(panel.sfx_slots, current, selected),
                    }
                )
            )
    return sorted(resolved, key=lambda panel: panel.reading_order)


def conflicts_with_any(rect: RectSpec, placed: list[RectSpec], gutter: int) -> bool:
    return any(overlap_area(rect, existing) > 0 or gutter_too_small(rect, existing, gutter) for existing in placed)


def move_slots(slots: list[LayoutSlot], source: RectSpec, target: RectSpec) -> list[LayoutSlot]:
    if not slots:
        return []
    dx = target.x - source.x
    dy = target.y - source.y
    return [
        slot.model_copy(update={"x": max(target.x, slot.x + dx), "y": max(target.y, slot.y + dy)})
        for slot in slots
    ]


def importance_for_plan(plan: PanelPlan | None, page_type: PageType) -> float:
    if page_type == "splash":
        return 3.0
    if plan is None:
        return 1.0
    text = " ".join([plan.story_beat, plan.visual_notes, plan.emotional_intent]).lower()
    return 1.0 + sum(0.35 for word in KEY_BEAT_WORDS if word in text)


def bubble_slots_for_panel(
    rect: RectSpec,
    plan: PanelPlan | None,
    page_type: PageType,
    reading_direction: ReadingDirection,
) -> list[LayoutSlot]:
    has_text = plan is not None and bool(plan.dialogue or plan.narration)
    if not has_text and page_type not in {"dialogue_scene", "exposition_page"}:
        return []
    slot_width = min(max(180, round(rect.width * 0.42)), max(180, rect.width - 40))
    slot_height = min(max(72, round(rect.height * 0.2)), max(72, rect.height - 40))
    inset = max(24, round(min(rect.width, rect.height) * 0.05))
    slot_x = rect.x + inset
    if reading_direction in {"rtl", "vertical-rl"}:
        slot_x = rect.right - slot_width - inset
    kind = "narration" if plan is not None and plan.narration and not plan.dialogue else "speech"
    text = plan.dialogue or plan.narration if plan is not None else None
    return [
        LayoutSlot(
            kind=kind,
            x=max(rect.x, slot_x),
            y=rect.y + inset,
            width=slot_width,
            height=slot_height,
            text=text,
            notes="Reserved lettering space",
        )
    ]


def sfx_slots_for_panel(rect: RectSpec, plan: PanelPlan | None, page_type: PageType) -> list[LayoutSlot]:
    text = " ".join(
        [
            page_type,
            plan.story_beat if plan is not None else "",
            plan.visual_notes if plan is not None else "",
        ]
    ).lower()
    if page_type != "action_sequence" and not any(word in text for word in ACTION_WORDS):
        return []
    return [
        LayoutSlot(
            kind="sfx",
            x=rect.x + round(rect.width * 0.28),
            y=rect.y + round(rect.height * 0.34),
            width=max(120, round(rect.width * 0.36)),
            height=max(72, round(rect.height * 0.18)),
            text="SFX",
            notes="Impact lettering slot",
        )
    ]


def expected_reading_order(panels: list[SuggestedPanelLayout], reading_direction: ReadingDirection) -> list[int]:
    rects = [RectSpec(panel.x, panel.y, panel.width, panel.height) for panel in panels]
    ordered_rects = assign_reading_order(rects, reading_direction)
    lookup = {(panel.x, panel.y, panel.width, panel.height): panel.reading_order for panel in panels}
    expected: list[int] = []
    for rect in ordered_rects.values():
        order = lookup.get((rect.x, rect.y, rect.width, rect.height))
        if order is not None:
            expected.append(order)
    return expected


def overlap_area(first: RectSpec, second: RectSpec) -> int:
    overlap_width = max(0, min(first.right, second.right) - max(first.x, second.x))
    overlap_height = max(0, min(first.bottom, second.bottom) - max(first.y, second.y))
    return overlap_width * overlap_height


def gutter_too_small(first: RectSpec, second: RectSpec, min_gutter: int) -> bool:
    if min_gutter <= 0:
        return False
    horizontal_overlap = min(first.bottom, second.bottom) > max(first.y, second.y)
    vertical_overlap = min(first.right, second.right) > max(first.x, second.x)
    if horizontal_overlap:
        gap = max(second.x - first.right, first.x - second.right)
        if 0 <= gap < min_gutter:
            return True
    if vertical_overlap:
        gap = max(second.y - first.bottom, first.y - second.bottom)
        if 0 <= gap < min_gutter:
            return True
    return False


def error_issue(code: str, message: str, panel_order: int | None = None) -> LayoutValidationIssue:
    return LayoutValidationIssue(severity="error", code=code, message=message, panel_order=panel_order)
