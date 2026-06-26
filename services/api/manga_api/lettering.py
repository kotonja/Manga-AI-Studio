from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from manga_api.models import Bubble, CharacterCard, Page, PagePlan, Panel, PanelPlan, SFXElement
from manga_api.schemas import TextFitResult


ACTION_WORDS = ("slash", "strike", "impact", "crash", "run", "fight", "shatter", "sword", "explosion", "burst")


@dataclass(frozen=True)
class Box:
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


class LetteringPlanner:
    def __init__(self, session: Session) -> None:
        self.session = session

    def generate_for_page(self, page_id: uuid.UUID | str) -> dict[str, Any]:
        page = self._require_page(page_id)
        layout = page.layout_json or {}
        reading_direction = str(layout.get("reading_direction", "rtl"))
        panels = self._panels(page.id)
        page_plan = self._page_plan(page)
        panel_plans = self._panel_plans(page_plan)
        panel_plans_by_order = {panel_plan.panel_order: panel_plan for panel_plan in panel_plans}
        existing_bubbles = self._bubbles_by_panel([panel.id for panel in panels])
        existing_sfx = self._sfx_by_panel(page.id)
        created_bubble_ids: list[uuid.UUID] = []
        created_sfx_ids: list[uuid.UUID] = []
        warnings: list[str] = []

        for panel in panels:
            panel_plan = panel_plans_by_order.get(panel.reading_order)
            bubbles = existing_bubbles.get(panel.id, [])
            if bubbles:
                for index, bubble in enumerate(bubbles):
                    self._normalize_bubble(page, panel, bubble, reading_direction, index)
                    fit = fit_text_to_box(
                        bubble.text,
                        bubble.width,
                        bubble.height,
                        font_size=bubble.font_size,
                        vertical_text=bubble.vertical_text,
                        manual_override=bubble.locked,
                    )
                    if fit.warning:
                        warnings.append(f"Bubble {bubble.id}: {fit.warning}")
                    if not bubble.locked:
                        bubble.font_size = fit.font_size
                    touch(bubble)
                    self.session.add(bubble)
                continue

            text = None
            bubble_type = "speech"
            if panel_plan is not None:
                if panel_plan.dialogue:
                    text = panel_plan.dialogue
                    bubble_type = "speech"
                elif panel_plan.narration:
                    text = panel_plan.narration
                    bubble_type = "narration"
            if not text:
                continue

            bubble = self._create_bubble_for_panel(page, panel, panel_plan, text, bubble_type, reading_direction)
            self.session.add(bubble)
            self.session.flush()
            created_bubble_ids.append(bubble.id)

        for panel in panels:
            panel_plan = panel_plans_by_order.get(panel.reading_order)
            if existing_sfx.get(panel.id) or not should_create_sfx(page_plan, panel_plan):
                continue
            sfx = self._create_sfx_for_panel(page, panel, panel_plan)
            self.session.add(sfx)
            self.session.flush()
            created_sfx_ids.append(sfx.id)

        self.session.commit()
        return {
            "page_id": page.id,
            "bubbles": self._all_bubbles(page.id),
            "sfx": self._all_sfx(page.id),
            "warnings": warnings,
            "created_bubble_ids": created_bubble_ids,
            "created_sfx_ids": created_sfx_ids,
        }

    def page_lettering(self, page_id: uuid.UUID | str) -> dict[str, Any]:
        page = self._require_page(page_id)
        warnings: list[str] = []
        for bubble in self._all_bubbles(page.id):
            fit = fit_text_to_box(
                bubble.text,
                bubble.width,
                bubble.height,
                font_size=bubble.font_size,
                vertical_text=bubble.vertical_text,
                manual_override=True,
            )
            if fit.warning:
                warnings.append(f"Bubble {bubble.id}: {fit.warning}")
        return {
            "page_id": page.id,
            "bubbles": self._all_bubbles(page.id),
            "sfx": self._all_sfx(page.id),
            "warnings": warnings,
        }

    def _require_page(self, page_id: uuid.UUID | str) -> Page:
        page = self.session.get(Page, uuid.UUID(str(page_id)))
        if page is None:
            raise ValueError("Page not found")
        return page

    def _panels(self, page_id: uuid.UUID) -> list[Panel]:
        return list(
            self.session.exec(
                select(Panel)
                .where(Panel.page_id == page_id)
                .order_by(Panel.reading_order.asc(), Panel.created_at.asc())
            ).all()
        )

    def _page_plan(self, page: Page) -> PagePlan | None:
        return self.session.exec(
            select(PagePlan)
            .where(PagePlan.project_id == page.project_id, PagePlan.page_number == page.page_number)
            .order_by(PagePlan.created_at.desc())
        ).first()

    def _panel_plans(self, page_plan: PagePlan | None) -> list[PanelPlan]:
        if page_plan is None:
            return []
        return list(
            self.session.exec(
                select(PanelPlan)
                .where(PanelPlan.page_plan_id == page_plan.id)
                .order_by(PanelPlan.panel_order.asc())
            ).all()
        )

    def _bubbles_by_panel(self, panel_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[Bubble]]:
        bubbles_by_panel = {panel_id: [] for panel_id in panel_ids}
        if not panel_ids:
            return bubbles_by_panel
        bubbles = self.session.exec(
            select(Bubble)
            .where(Bubble.panel_id.in_(panel_ids))
            .order_by(Bubble.z_index.asc(), Bubble.created_at.asc())
        ).all()
        for bubble in bubbles:
            bubbles_by_panel.setdefault(bubble.panel_id, []).append(bubble)
        return bubbles_by_panel

    def _sfx_by_panel(self, page_id: uuid.UUID) -> dict[uuid.UUID, list[SFXElement]]:
        elements = self._all_sfx(page_id)
        by_panel: dict[uuid.UUID, list[SFXElement]] = {}
        for element in elements:
            if element.panel_id is not None:
                by_panel.setdefault(element.panel_id, []).append(element)
        return by_panel

    def _all_bubbles(self, page_id: uuid.UUID) -> list[Bubble]:
        panels = self._panels(page_id)
        panel_ids = [panel.id for panel in panels]
        if not panel_ids:
            return []
        return list(
            self.session.exec(
                select(Bubble)
                .where(Bubble.panel_id.in_(panel_ids))
                .order_by(Bubble.z_index.asc(), Bubble.created_at.asc())
            ).all()
        )

    def _all_sfx(self, page_id: uuid.UUID) -> list[SFXElement]:
        return list(
            self.session.exec(
                select(SFXElement)
                .where(SFXElement.page_id == page_id)
                .order_by(SFXElement.z_index.asc(), SFXElement.created_at.asc())
            ).all()
        )

    def _normalize_bubble(self, page: Page, panel: Panel, bubble: Bubble, reading_direction: str, index: int) -> None:
        bubble.bubble_type = bubble.bubble_type or bubble.kind or "speech"
        bubble.kind = bubble.kind or bubble.bubble_type
        bubble.reading_direction = bubble.reading_direction or reading_direction
        bubble.shape = bubble.shape or shape_for_type(bubble.bubble_type)
        if not bubble.tail_target:
            bubble.tail_target = speaker_tail_target(panel, None)
        box = clamp_box(Box(bubble.x, bubble.y, bubble.width, bubble.height), page.width, page.height)
        bubble.x = box.x
        bubble.y = box.y
        bubble.width = box.width
        bubble.height = box.height
        bubble.position = {"x": bubble.x, "y": bubble.y}
        bubble.size = {"width": bubble.width, "height": bubble.height}
        bubble.z_index = bubble.z_index or index

    def _create_bubble_for_panel(
        self,
        page: Page,
        panel: Panel,
        panel_plan: PanelPlan | None,
        text: str,
        bubble_type: str,
        reading_direction: str,
    ) -> Bubble:
        speaker_id = self._speaker_character_id(page.project_id, panel_plan)
        box = suggested_bubble_box(page, panel, bubble_type, reading_direction)
        fit = fit_text_to_box(text, box.width, box.height, font_size=26 if bubble_type != "narration" else 22)
        return Bubble(
            panel_id=panel.id,
            kind=bubble_type,
            bubble_type=bubble_type,
            speaker_character_id=speaker_id,
            x=box.x,
            y=box.y,
            width=box.width,
            height=box.height,
            text=text,
            language="en",
            reading_direction=reading_direction,
            shape=shape_for_type(bubble_type),
            position={"x": box.x, "y": box.y},
            size={"width": box.width, "height": box.height},
            tail_target=speaker_tail_target(panel, speaker_id),
            font_size=fit.font_size,
            text_align="center",
            vertical_text=reading_direction == "vertical-rl",
            z_index=20 if bubble_type == "narration" else 30,
        )

    def _speaker_character_id(self, project_id: uuid.UUID, panel_plan: PanelPlan | None) -> uuid.UUID | None:
        if panel_plan is None or not panel_plan.characters:
            return None
        wanted = {name.casefold() for name in panel_plan.characters}
        cards = self.session.exec(
            select(CharacterCard)
            .where(CharacterCard.project_id == project_id)
            .order_by(CharacterCard.name.asc())
        ).all()
        for card in cards:
            names = {card.name.casefold(), *(alias.casefold() for alias in card.aliases)}
            if names.intersection(wanted):
                return card.id
        return None

    def _create_sfx_for_panel(self, page: Page, panel: Panel, panel_plan: PanelPlan | None) -> SFXElement:
        width = max(160, min(360, round(panel.width * 0.38)))
        height = max(80, min(220, round(panel.height * 0.22)))
        x = panel.x + max(24, round(panel.width * 0.32))
        y = panel.y + max(24, round(panel.height * 0.36))
        box = clamp_box(Box(x, y, width, height), page.width, page.height)
        return SFXElement(
            page_id=page.id,
            panel_id=panel.id,
            text="SFX!",
            meaning=panel_plan.story_beat if panel_plan is not None else "action emphasis",
            style="impact",
            position={"x": box.x, "y": box.y},
            size={"width": box.width, "height": box.height},
            rotation=-8.0,
            warp_style="jagged",
            stroke_width=5.0,
            fill="#ffffff",
            outline="#111111",
            z_index=40,
        )


def fit_text_to_box(
    text: str,
    width: int,
    height: int,
    *,
    font_size: int = 24,
    vertical_text: bool = False,
    manual_override: bool = False,
    min_font_size: int = 8,
) -> TextFitResult:
    cleaned = " ".join(text.split())
    if not cleaned:
        return TextFitResult(text=text, font_size=font_size, lines=[""], warning="Text is empty", overflow=True)
    for size in range(font_size, min_font_size - 1, -1):
        lines = wrap_text(cleaned, width, size, vertical_text)
        needed_height = text_block_height(lines, size, vertical_text)
        if needed_height <= max(1, height - 20):
            warning = None
            if size < font_size and not manual_override:
                warning = f"Text fit by shrinking from {font_size}px to {size}px."
            return TextFitResult(text=text, font_size=size, lines=lines, warning=warning, overflow=False)
    lines = wrap_text(cleaned, width, min_font_size, vertical_text)
    return TextFitResult(
        text=text,
        font_size=font_size if manual_override else min_font_size,
        lines=lines,
        warning="Text is too long for the current lettering box.",
        overflow=True,
    )


def wrap_text(text: str, width: int, font_size: int, vertical_text: bool = False) -> list[str]:
    if vertical_text:
        max_chars = max(1, int(width / max(1, font_size * 1.15)))
        return [text[index : index + max_chars] for index in range(0, len(text), max_chars)]
    max_chars = max(4, int(width / max(1, font_size * 0.56)))
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines or [""]


def text_block_height(lines: list[str], font_size: int, vertical_text: bool = False) -> int:
    if vertical_text:
        longest = max((len(line) for line in lines), default=1)
        return math.ceil(longest * font_size * 1.05)
    return math.ceil(len(lines) * font_size * 1.22)


def suggested_bubble_box(page: Page, panel: Panel, bubble_type: str, reading_direction: str) -> Box:
    if bubble_type == "narration":
        width = min(panel.width - 40, max(260, round(panel.width * 0.56)))
        height = min(panel.height - 30, max(72, round(panel.height * 0.16)))
        x = panel.x + 24
        y = panel.y + 24
        return clamp_box(Box(x, y, width, height), page.width, page.height)
    width = min(panel.width - 40, max(220, round(panel.width * 0.38)))
    height = min(panel.height - 40, max(110, round(panel.height * 0.24)))
    x = panel.x + 28
    if reading_direction in {"rtl", "vertical-rl"}:
        x = panel.x + panel.width - width - 28
    y = panel.y + 34
    return clamp_box(Box(x, y, width, height), page.width, page.height)


def speaker_tail_target(panel: Panel, speaker_character_id: uuid.UUID | None) -> dict[str, Any]:
    return {
        "x": panel.x + round(panel.width * 0.5),
        "y": panel.y + round(panel.height * 0.72),
        "speaker_character_id": str(speaker_character_id) if speaker_character_id is not None else None,
    }


def should_create_sfx(page_plan: PagePlan | None, panel_plan: PanelPlan | None) -> bool:
    text = " ".join(
        [
            page_plan.pacing if page_plan is not None else "",
            page_plan.summary if page_plan is not None else "",
            panel_plan.story_beat if panel_plan is not None else "",
            panel_plan.visual_notes if panel_plan is not None else "",
            panel_plan.emotional_intent if panel_plan is not None else "",
        ]
    ).lower()
    return any(word in text for word in ACTION_WORDS)


def shape_for_type(bubble_type: str) -> str:
    if bubble_type == "narration":
        return "box"
    if bubble_type == "thought":
        return "cloud"
    if bubble_type == "shout":
        return "burst"
    if bubble_type in {"radio", "monster"}:
        return "jagged"
    return "oval"


def clamp_box(box: Box, page_width: int, page_height: int) -> Box:
    width = min(max(1, box.width), max(1, page_width))
    height = min(max(1, box.height), max(1, page_height))
    x = max(0, min(box.x, page_width - width))
    y = max(0, min(box.y, page_height - height))
    return Box(x, y, width, height)


def lettering_svg_for_page(session: Session, page_id: uuid.UUID | str) -> str:
    page = session.get(Page, uuid.UUID(str(page_id)))
    if page is None:
        raise ValueError("Page not found")
    planner = LetteringPlanner(session)
    data = planner.page_lettering(page.id)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page.width}" height="{page.height}" viewBox="0 0 {page.width} {page.height}">',
        '<g id="bubbles">',
    ]
    for bubble in data["bubbles"]:
        parts.append(bubble_to_svg(bubble))
    parts.append("</g>")
    parts.append('<g id="sfx">')
    for element in data["sfx"]:
        parts.append(sfx_to_svg(element))
    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def bubble_to_svg(bubble: Bubble) -> str:
    bubble_type = bubble.bubble_type or bubble.kind
    shape = bubble.shape or shape_for_type(bubble_type)
    fit = fit_text_to_box(bubble.text, bubble.width, bubble.height, font_size=bubble.font_size, vertical_text=bubble.vertical_text, manual_override=True)
    parts = [
        f'<g data-bubble-id="{bubble.id}" data-bubble-type="{escape_xml(bubble_type)}" '
        f'data-z-index="{bubble.z_index}" data-text="{escape_xml(bubble.text)}">'
    ]
    if shape == "box":
        parts.append(
            f'<rect x="{bubble.x}" y="{bubble.y}" width="{bubble.width}" height="{bubble.height}" rx="4" fill="white" stroke="black" stroke-width="3" />'
        )
    elif shape in {"burst", "jagged"}:
        points = burst_points(bubble.x, bubble.y, bubble.width, bubble.height)
        parts.append(f'<polygon points="{points}" fill="white" stroke="black" stroke-width="3" />')
    else:
        parts.append(
            f'<ellipse cx="{bubble.x + bubble.width / 2}" cy="{bubble.y + bubble.height / 2}" rx="{bubble.width / 2}" ry="{bubble.height / 2}" fill="white" stroke="black" stroke-width="3" />'
        )
    if bubble.tail_target:
        tx = int(bubble.tail_target.get("x", bubble.x + bubble.width / 2))
        ty = int(bubble.tail_target.get("y", bubble.y + bubble.height))
        parts.append(
            f'<path d="M {bubble.x + bubble.width / 2:.0f} {bubble.y + bubble.height * 0.84:.0f} L {tx} {ty}" fill="none" stroke="black" stroke-width="2" />'
        )
    parts.append(svg_text_block(bubble.x, bubble.y, bubble.width, bubble.height, fit, bubble))
    parts.append("</g>")
    return "\n".join(parts)


def sfx_to_svg(element: SFXElement) -> str:
    x = int(element.position.get("x", 0))
    y = int(element.position.get("y", 0))
    width = int(element.size.get("width", 240))
    height = int(element.size.get("height", 120))
    cx = x + width / 2
    cy = y + height / 2
    font_size = max(20, int(height * 0.58))
    return (
        f'<g data-sfx-id="{element.id}" data-z-index="{element.z_index}" transform="rotate({element.rotation} {cx:.0f} {cy:.0f})">'
        f'<text x="{cx:.0f}" y="{cy:.0f}" text-anchor="middle" dominant-baseline="middle" '
        f'font-family="Manga Temple, Impact, sans-serif" font-size="{font_size}" font-weight="900" '
        f'fill="{escape_xml(element.fill)}" stroke="{escape_xml(element.outline)}" stroke-width="{element.stroke_width}" '
        f'paint-order="stroke fill">{escape_xml(element.text)}</text></g>'
    )


def svg_text_block(x: int, y: int, width: int, height: int, fit: TextFitResult, bubble: Bubble) -> str:
    anchor = {"left": "start", "center": "middle", "right": "end"}.get(bubble.text_align, "middle")
    text_x = x + width / 2
    if anchor == "start":
        text_x = x + 18
    elif anchor == "end":
        text_x = x + width - 18
    line_height = fit.font_size * 1.22
    start_y = y + (height - line_height * len(fit.lines)) / 2 + fit.font_size
    attrs = ""
    if bubble.vertical_text:
        attrs = ' writing-mode="vertical-rl" glyph-orientation-vertical="0"'
    tspans = []
    for index, line in enumerate(fit.lines):
        dy = 0 if index == 0 else line_height
        tspans.append(f'<tspan x="{text_x:.0f}" dy="{dy:.1f}">{escape_xml(line)}</tspan>')
    return (
        f'<text x="{text_x:.0f}" y="{start_y:.0f}" text-anchor="{anchor}" font-family="{escape_xml(bubble.font_family)}" '
        f'font-size="{fit.font_size}" font-weight="{escape_xml(bubble.font_weight)}"{attrs}>{"".join(tspans)}</text>'
    )


def burst_points(x: int, y: int, width: int, height: int) -> str:
    cx = x + width / 2
    cy = y + height / 2
    points = []
    for index in range(18):
        angle = index * math.tau / 18
        rx = width / (2.0 if index % 2 == 0 else 2.45)
        ry = height / (2.0 if index % 2 == 0 else 2.45)
        points.append(f"{cx + math.cos(angle) * rx:.0f},{cy + math.sin(angle) * ry:.0f}")
    return " ".join(points)


def touch(row: Any) -> None:
    row.updated_at = datetime.now(timezone.utc)


def escape_xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
