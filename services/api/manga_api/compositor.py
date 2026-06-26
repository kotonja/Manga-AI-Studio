from __future__ import annotations

import uuid
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Protocol

from PIL import Image, ImageDraw, ImageFont
from sqlmodel import Session, select

from manga_api.lettering import fit_text_to_box
from manga_api.models import Asset, Bubble, GenerationJob, Page, Panel, Project, Render, SFXElement
from manga_api.provenance import ProvenanceService


class StorageClient(Protocol):
    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        """Persist bytes to object storage."""

    def get_bytes(self, key: str) -> bytes:
        """Read bytes from object storage."""

    def public_url(self, key: str) -> str:
        """Return a browser-accessible URL for a stored object."""


@dataclass(frozen=True)
class CompositeResult:
    asset: Asset
    data: bytes
    width: int
    height: int
    public_url: str | None


class PageCompositor:
    def __init__(self, session: Session, storage: StorageClient | None = None) -> None:
        self.session = session
        self.storage = storage

    def compose_page(self, page_id: uuid.UUID | str) -> CompositeResult:
        page = self.session.get(Page, uuid.UUID(str(page_id)))
        if page is None:
            raise ValueError("Page not found")

        project = self.session.get(Project, page.project_id)
        if project is None:
            raise ValueError("Page references a missing project")

        layout = page.layout_json or {}
        reading_direction = str(layout.get("reading_direction", "rtl"))
        panels = self.session.exec(
            select(Panel)
            .where(Panel.page_id == page.id)
            .order_by(Panel.reading_order.asc(), Panel.created_at.asc())
        ).all()
        bubbles_by_panel = self._load_bubbles_by_panel([panel.id for panel in panels])
        sfx_elements = self._load_sfx(page.id)
        renders_by_panel = self._latest_renders_by_panel([panel.id for panel in panels])

        image = Image.new("RGB", (page.width, page.height), "white")
        draw = ImageDraw.Draw(image)

        for panel in panels:
            self._draw_panel(image, draw, panel, renders_by_panel.get(panel.id))

        for panel in panels:
            for bubble in bubbles_by_panel.get(panel.id, []):
                self._draw_bubble(draw, bubble)
        for element in sfx_elements:
            self._draw_sfx(image, element)

        output = BytesIO()
        image.save(output, format="PNG")
        data = output.getvalue()
        storage_key = f"pages/{project.id}/{page.id}/composite-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}.png"
        public_url: str | None = None
        if self.storage is not None:
            self.storage.put_bytes(key=storage_key, data=data, content_type="image/png")
            public_url = self.storage.public_url(storage_key)
        render_asset_ids = {
            str(panel_id): str(render.asset_id)
            for panel_id, render in renders_by_panel.items()
            if render.asset_id is not None
        }
        approved_render_asset_ids = {
            panel_id: asset_id
            for panel_id, asset_id in render_asset_ids.items()
            if self._render_asset_is_approved(uuid.UUID(asset_id))
        }

        asset = Asset(
            project_id=project.id,
            filename=f"page-{page.page_number}-composite.png",
            kind="page_composite",
            content_type="image/png",
            size_bytes=len(data),
            storage_key=storage_key,
            metadata_json={
                "page_id": str(page.id),
                "page_number": page.page_number,
                "width": page.width,
                "height": page.height,
                "reading_direction": reading_direction,
                "bleed": int(layout.get("bleed", 0)),
                "safe_margin": int(layout.get("safe_margin", 80)),
                "panel_count": len(panels),
                "bubble_count": sum(len(bubbles) for bubbles in bubbles_by_panel.values()),
                "sfx_count": len(sfx_elements),
                "panel_render_asset_ids": render_asset_ids,
                "approved_render_asset_ids": approved_render_asset_ids,
                "public_url": public_url,
            },
        )
        self.session.add(asset)
        self.session.flush()
        ProvenanceService(self.session).record_asset(
            asset,
            source_type="internal_mock",
            provider_name="manga-ai-compositor",
            model_name="pillow",
            declared_rights="Composed by Manga AI Studio from project layouts, lettering, and panel render assets.",
            license_type="project_composite",
            allow_training=False,
            allow_commercial_use=True,
            ai_disclosure_required=bool(render_asset_ids),
        )
        self.session.commit()
        self.session.refresh(asset)
        return CompositeResult(asset=asset, data=data, width=page.width, height=page.height, public_url=public_url)

    def _draw_panel(self, image: Image.Image, draw: ImageDraw.ImageDraw, panel: Panel, render: Render | None) -> None:
        points = panel_polygon(panel)
        bbox = polygon_bbox(points)
        source = self._load_render_image(render, panel)
        fitted = fit_image(source, bbox[2] - bbox[0], bbox[3] - bbox[1])

        mask = Image.new("L", image.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.polygon(points, fill=255)
        panel_layer = Image.new("RGB", image.size, "white")
        panel_layer.paste(fitted, (bbox[0], bbox[1]))
        image.paste(panel_layer, (0, 0), mask)

        draw.line([*points, points[0]], fill="black", width=max(3, min(panel.width, panel.height) // 80), joint="curve")

    def _load_render_image(self, render: Render | None, panel: Panel) -> Image.Image:
        if render is None or self.storage is None:
            return panel_placeholder(panel)
        try:
            data = self.storage.get_bytes(render.storage_key)
            return Image.open(BytesIO(data)).convert("RGB")
        except Exception:
            return panel_placeholder(panel)

    def _draw_bubble(self, draw: ImageDraw.ImageDraw, bubble: Bubble) -> None:
        box = (bubble.x, bubble.y, bubble.x + bubble.width, bubble.y + bubble.height)
        kind = (bubble.bubble_type or bubble.kind).lower()

        if kind == "narration":
            draw.rounded_rectangle(box, radius=6, fill="white", outline="black", width=3)
        elif kind == "thought":
            draw.ellipse(box, fill="white", outline="black", width=3)
            tail_x = bubble.x + max(16, bubble.width // 5)
            tail_y = bubble.y + bubble.height + 8
            draw.ellipse((tail_x, tail_y, tail_x + 20, tail_y + 20), fill="white", outline="black", width=2)
            draw.ellipse((tail_x - 22, tail_y + 20, tail_x - 8, tail_y + 34), fill="white", outline="black", width=2)
        elif kind == "shout":
            points = burst_points(bubble.x, bubble.y, bubble.width, bubble.height)
            draw.polygon(points, fill="white", outline="black")
            draw.line([*points, points[0]], fill="black", width=3)
        else:
            draw.ellipse(box, fill="white", outline="black", width=3)
            tail = [
                (bubble.x + bubble.width * 0.35, bubble.y + bubble.height * 0.85),
                (bubble.x + bubble.width * 0.48, bubble.y + bubble.height + 36),
                (bubble.x + bubble.width * 0.58, bubble.y + bubble.height * 0.85),
            ]
            draw.polygon(tail, fill="white", outline="black")
            draw.line(tail + [tail[0]], fill="black", width=2)

        text_box = (bubble.x + 18, bubble.y + 14, bubble.x + bubble.width - 18, bubble.y + bubble.height - 14)
        if kind == "shout":
            text_box = (bubble.x + 26, bubble.y + 22, bubble.x + bubble.width - 26, bubble.y + bubble.height - 22)
        draw_fitted_text(draw, bubble.text, text_box, preferred_size=bubble.font_size, vertical_text=bubble.vertical_text)

    def _draw_sfx(self, image: Image.Image, element: SFXElement) -> None:
        x = int(element.position.get("x", 0))
        y = int(element.position.get("y", 0))
        width = int(element.size.get("width", 240))
        height = int(element.size.get("height", 120))
        font = load_font(max(18, int(height * 0.52)))
        text = element.text
        layer = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(layer)
        text_box = draw.textbbox((0, 0), text, font=font, stroke_width=int(element.stroke_width))
        text_width_value = text_box[2] - text_box[0]
        text_height_value = text_box[3] - text_box[1]
        draw.text(
            ((width - text_width_value) / 2, (height - text_height_value) / 2),
            text,
            fill=element.fill,
            font=font,
            stroke_width=int(element.stroke_width),
            stroke_fill=element.outline,
        )
        rotated = layer.rotate(float(element.rotation), expand=True, resample=Image.Resampling.BICUBIC)
        paste_x = int(x + width / 2 - rotated.width / 2)
        paste_y = int(y + height / 2 - rotated.height / 2)
        image.paste(rotated, (paste_x, paste_y), rotated)

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

    def _load_sfx(self, page_id: uuid.UUID) -> list[SFXElement]:
        return list(
            self.session.exec(
                select(SFXElement)
                .where(SFXElement.page_id == page_id)
                .order_by(SFXElement.z_index.asc(), SFXElement.created_at.asc())
            ).all()
        )

    def _latest_renders_by_panel(self, panel_ids: list[uuid.UUID]) -> dict[uuid.UUID, Render]:
        fallback_by_panel: dict[uuid.UUID, Render] = {}
        approved_by_panel: dict[uuid.UUID, Render] = {}
        if not panel_ids:
            return fallback_by_panel
        renders = self.session.exec(
            select(Render, GenerationJob)
            .join(GenerationJob, GenerationJob.id == Render.job_id)
            .where(Render.panel_id.in_(panel_ids), GenerationJob.status == "succeeded")
            .order_by(Render.created_at.desc())
        ).all()
        for render, _job in renders:
            fallback_by_panel.setdefault(render.panel_id, render)
            if render.asset_id is not None and self._render_asset_is_approved(render.asset_id):
                approved_by_panel.setdefault(render.panel_id, render)
        return {**fallback_by_panel, **approved_by_panel}

    def _render_asset_is_approved(self, asset_id: uuid.UUID) -> bool:
        asset = self.session.get(Asset, asset_id)
        return bool(asset is not None and (asset.metadata_json or {}).get("approved"))


def get_latest_composite_asset(session: Session, page_id: uuid.UUID) -> Asset | None:
    assets = session.exec(
        select(Asset)
        .where(Asset.kind == "page_composite")
        .order_by(Asset.created_at.desc())
    ).all()
    for asset in assets:
        if asset.metadata_json.get("page_id") == str(page_id):
            return asset
    return None


def panel_polygon(panel: Panel) -> list[tuple[int, int]]:
    raw_points = panel.polygon or [
        {"x": panel.x, "y": panel.y},
        {"x": panel.x + panel.width, "y": panel.y},
        {"x": panel.x + panel.width, "y": panel.y + panel.height},
        {"x": panel.x, "y": panel.y + panel.height},
    ]
    return [(int(point["x"]), int(point["y"])) for point in raw_points]


def polygon_bbox(points: list[tuple[int, int]]) -> tuple[int, int, int, int]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def fit_image(image: Image.Image, width: int, height: int) -> Image.Image:
    if width <= 0 or height <= 0:
        return Image.new("RGB", (1, 1), "white")
    fitted = image.copy()
    fitted.thumbnail((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), "white")
    x = (width - fitted.width) // 2
    y = (height - fitted.height) // 2
    canvas.paste(fitted, (x, y))
    return canvas


def panel_placeholder(panel: Panel) -> Image.Image:
    image = Image.new("RGB", (max(1, panel.width), max(1, panel.height)), (246, 246, 240))
    draw = ImageDraw.Draw(image)
    for offset in range(-panel.height, panel.width, max(32, min(panel.width, panel.height) // 12)):
        draw.line((offset, panel.height, offset + panel.height, 0), fill=(222, 222, 214), width=2)
    draw.text((18, 18), f"Panel {panel.reading_order}", fill=(24, 24, 24), font=load_font(22))
    return image


def burst_points(x: int, y: int, width: int, height: int) -> list[tuple[int, int]]:
    cx = x + width / 2
    cy = y + height / 2
    points: list[tuple[int, int]] = []
    steps = 18
    for index in range(steps):
        angle = index * 6.283185307179586 / steps
        radius_x = width / (2.0 if index % 2 == 0 else 2.45)
        radius_y = height / (2.0 if index % 2 == 0 else 2.45)
        px = int(cx + radius_x * math.cos(angle))
        py = int(cy + radius_y * math.sin(angle))
        points.append((px, py))
    return points


def draw_fitted_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    *,
    preferred_size: int = 34,
    vertical_text: bool = False,
) -> None:
    x1, y1, x2, y2 = box
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    fit = fit_text_to_box(text, width, height, font_size=min(preferred_size, max(14, height // 2)), vertical_text=vertical_text)
    if not fit.overflow:
        font = load_font(fit.font_size)
        line_height = text_height(draw, font) + max(2, fit.font_size // 6)
        total_height = line_height * len(fit.lines)
        y = y1 + (height - total_height) // 2
        for line in fit.lines:
            line_width = text_width(draw, line, font)
            draw.text((x1 + (width - line_width) // 2, y), line, fill="black", font=font)
            y += line_height
        return
    for size in range(min(preferred_size, max(14, height // 2)), 8, -1):
        font = load_font(size)
        lines = wrap_text(draw, text, font, width)
        line_height = text_height(draw, font) + max(2, size // 6)
        total_height = line_height * len(lines)
        if total_height <= height:
            y = y1 + (height - total_height) // 2
            for line in lines:
                line_width = text_width(draw, line, font)
                draw.text((x1 + (width - line_width) // 2, y), line, fill="black", font=font)
                y += line_height
            return

    font = load_font(9)
    lines = wrap_text(draw, text, font, width)
    y = y1
    for line in lines[: max(1, height // 12)]:
        draw.text((x1, y), line, fill="black", font=font)
        y += 12


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def text_height(draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), "Ag", font=font)
    return box[3] - box[1]


def load_font(size: int) -> ImageFont.ImageFont:
    for path in [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()
