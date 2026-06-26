from __future__ import annotations

import base64
import hashlib
import json
import logging
import math
import random
import textwrap
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Protocol

import httpx
from PIL import Image, ImageDraw, ImageFont
from sqlmodel import Session, select

from manga_api.config import get_settings
from manga_api.models import (
    Asset,
    CharacterCard,
    CharacterReferenceAsset,
    GenerationJob,
    KeyObject,
    Location,
    Page,
    PagePlan,
    Panel,
    PanelRenderPrompt,
    PanelPlan,
    Project,
    Render,
    StoryBible,
    StyleBible,
    StyleSampleAsset,
)
from manga_api.provider_registry import (
    estimate_image_cost,
    provider_summary,
    validate_provider_request,
)
from manga_api.provenance import ProvenanceService
from manga_api.reference_pack import ReferencePackBuilder, character_anchor_values, dedupe_references, state_anchor_values

logger = logging.getLogger("manga_api.provider")


class ProviderError(RuntimeError):
    """Raised for expected provider configuration or generation failures."""


@dataclass(frozen=True)
class GeneratedImage:
    data: bytes
    width: int
    height: int
    content_type: str = "image/png"
    model_name: str | None = None
    seed: int | None = None
    provider_metadata: dict[str, Any] | None = None


class ImageProvider(Protocol):
    name: str
    model_name: str

    def generate_image(
        self,
        prompt: str,
        size: str,
        references: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> GeneratedImage:
        """Generate a new image from a prompt."""

    def edit_image(
        self,
        input_image: bytes,
        mask: bytes | None,
        prompt: str,
        options: dict[str, Any],
    ) -> GeneratedImage:
        """Edit an existing image."""


class ObjectStore(Protocol):
    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        """Persist bytes to object storage."""

    def public_url(self, key: str) -> str:
        """Return a browser-accessible URL for a stored object."""


class MockImageProvider:
    name = "mock"
    model_name = "mock-image-v1"

    def generate_image(
        self,
        prompt: str,
        size: str,
        references: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> GeneratedImage:
        width, height = parse_size(size)
        seed = int(options.get("seed") or stable_seed(prompt))
        rng = random.Random(seed)
        image = Image.new("RGB", (width, height), color=(248, 248, 244))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        border = max(8, min(width, height) // 30)
        prompt_lower = prompt.lower()
        page_number = options.get("page_number", "?")
        panel_order = options.get("panel_order", options.get("panel_number", "?"))

        self._draw_screentone(draw, width, height, rng)
        self._draw_ruined_city(draw, width, height, rng)

        if any(keyword in prompt_lower for keyword in ["sword", "katana", "ash", "spirit", "action", "run", "claw"]):
            self._draw_speed_lines(draw, width, height, rng)
        else:
            self._draw_rain_lines(draw, width, height, rng)

        self._draw_story_motif(draw, width, height, prompt_lower, rng, page_number, panel_order)
        self._draw_characters(draw, width, height, prompt_lower, font)
        if "lantern" in prompt_lower or "mio" in prompt_lower:
            self._draw_lantern(draw, width, height, rng)
        if any(keyword in prompt_lower for keyword in ["ash", "spirit", "claw"]):
            self._draw_ash_spirits(draw, width, height, rng)

        if options.get("render_internal_lettering"):
            bubble_text = self._bubble_text(page_number, panel_order)
            self._draw_demo_bubble(draw, width, height, bubble_text, font)

        draw.rectangle(
            (border, border, width - border, height - border),
            outline=(12, 14, 18),
            width=max(4, border // 3),
        )
        caption = f"PAGE {page_number} / PANEL {panel_order}"
        caption_box = (border * 2, height - border * 5, min(width - border * 2, border * 2 + 220), height - border * 2)
        draw.rectangle(caption_box, fill=(12, 14, 18))
        draw.text((caption_box[0] + 10, caption_box[1] + 8), caption, fill=(255, 255, 250), font=font)

        output = BytesIO()
        image.save(output, format="PNG")
        return GeneratedImage(
            data=output.getvalue(),
            width=width,
            height=height,
            model_name=self.model_name,
            seed=seed,
            provider_metadata={"references": len(references), "placeholder": True, "demo_asset_style": "mock_manga_panel_v2"},
        )

    def _draw_screentone(self, draw: ImageDraw.ImageDraw, width: int, height: int, rng: random.Random) -> None:
        spacing = max(10, min(width, height) // 36)
        radius = max(1, spacing // 6)
        for y in range(spacing, height, spacing):
            for x in range((y // spacing) % 2 * spacing // 2, width, spacing):
                if rng.random() < 0.72:
                    shade = rng.choice([205, 214, 224, 232])
                    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(shade, shade, shade))

    def _draw_ruined_city(self, draw: ImageDraw.ImageDraw, width: int, height: int, rng: random.Random) -> None:
        horizon = int(height * 0.58)
        for index in range(9):
            building_width = rng.randint(max(30, width // 12), max(60, width // 5))
            x0 = int(index * width / 8) - rng.randint(0, building_width // 2)
            x1 = min(width, x0 + building_width)
            y0 = rng.randint(max(20, height // 18), max(40, height // 3))
            tone = rng.choice([38, 45, 52, 68, 84])
            notch = rng.randint(0, max(8, building_width // 5))
            points = [(x0, horizon), (x0, y0 + notch), (x0 + building_width // 3, y0), (x1, y0 + notch), (x1, horizon)]
            draw.polygon(points, fill=(tone, tone, tone))
            for window_y in range(y0 + 18, horizon - 12, max(20, height // 14)):
                if rng.random() < 0.55:
                    window_x0 = max(0, x0 + 10)
                    window_x1 = min(width, x1 - 10, x0 + 24)
                    if window_x1 >= window_x0:
                        draw.rectangle((window_x0, window_y, window_x1, window_y + 5), fill=(235, 235, 226))
        draw.rectangle((0, horizon, width, height), fill=(238, 238, 232))
        for _ in range(16):
            x = rng.randint(0, width)
            y = rng.randint(horizon, height - 10)
            draw.line((x, y, min(width, x + rng.randint(25, 110)), y + rng.randint(-8, 8)), fill=(150, 154, 158), width=1)

    def _draw_speed_lines(self, draw: ImageDraw.ImageDraw, width: int, height: int, rng: random.Random) -> None:
        focus = (rng.randint(width // 3, width * 2 // 3), rng.randint(height // 3, height * 2 // 3))
        for _ in range(46):
            side = rng.choice(["left", "right", "top", "bottom"])
            if side == "left":
                start = (0, rng.randint(0, height))
            elif side == "right":
                start = (width, rng.randint(0, height))
            elif side == "top":
                start = (rng.randint(0, width), 0)
            else:
                start = (rng.randint(0, width), height)
            draw.line((start[0], start[1], focus[0], focus[1]), fill=(26, 29, 33), width=rng.randint(1, 4))

    def _draw_rain_lines(self, draw: ImageDraw.ImageDraw, width: int, height: int, rng: random.Random) -> None:
        for _ in range(90):
            x = rng.randint(-width // 5, width)
            y = rng.randint(0, height)
            length = rng.randint(max(16, height // 32), max(28, height // 12))
            draw.line((x, y, x + length // 3, y + length), fill=(154, 160, 168), width=1)

    def _draw_characters(self, draw: ImageDraw.ImageDraw, width: int, height: int, prompt_lower: str, font: ImageFont.ImageFont) -> None:
        names: list[tuple[str, int, bool]] = []
        if "ren aki" in prompt_lower or "swordsman" in prompt_lower or "protector" in prompt_lower:
            names.append(("Ren Aki", int(width * 0.42), False))
        if "mio" in prompt_lower or "ghost child" in prompt_lower or "companion" in prompt_lower:
            names.append(("Mio", int(width * 0.64), True))
        if not names:
            names.append(("Hero", int(width * 0.52), False))

        ground = int(height * 0.86)
        for label, center_x, ghost in names[:2]:
            scale = 0.72 if ghost else 1.0
            body_h = int(height * (0.31 * scale))
            body_w = int(width * (0.13 * scale))
            head_r = max(12, int(width * 0.035 * scale))
            tone = (22, 24, 29) if not ghost else (92, 96, 108)
            draw.ellipse((center_x - head_r, ground - body_h - head_r * 2, center_x + head_r, ground - body_h), fill=tone)
            draw.polygon(
                [
                    (center_x, ground - body_h + head_r // 2),
                    (center_x - body_w, ground),
                    (center_x + body_w, ground),
                ],
                fill=tone,
            )
            if not ghost:
                draw.line((center_x + body_w // 2, ground - body_h // 2, center_x + body_w * 2, ground - body_h - head_r), fill=(8, 10, 14), width=max(3, width // 90))
            if ghost:
                halo = max(18, head_r * 2)
                draw.ellipse(
                    (center_x - halo, ground - body_h - head_r * 2 - halo // 3, center_x + halo, ground - body_h + halo // 3),
                    outline=(235, 235, 226),
                    width=max(2, width // 180),
                )

    def _draw_lantern(self, draw: ImageDraw.ImageDraw, width: int, height: int, rng: random.Random) -> None:
        cx = int(width * 0.68)
        cy = int(height * 0.63)
        glow = max(34, min(width, height) // 8)
        for radius, tone in [(glow, 232), (glow // 2, 248)]:
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(tone, tone, tone), width=max(3, radius // 12))
        lantern = (cx - glow // 5, cy - glow // 3, cx + glow // 5, cy + glow // 3)
        draw.rounded_rectangle(lantern, radius=max(4, glow // 12), fill=(255, 255, 245), outline=(24, 26, 30), width=2)
        for line_x in [lantern[0] + (lantern[2] - lantern[0]) // 3, lantern[0] + (lantern[2] - lantern[0]) * 2 // 3]:
            draw.line((line_x, lantern[1], line_x, lantern[3]), fill=(112, 112, 104), width=1)
        draw.arc((lantern[0] + 4, lantern[1] - 10, lantern[2] - 4, lantern[1] + 10), 180, 360, fill=(24, 26, 30), width=2)

    def _draw_story_motif(
        self,
        draw: ImageDraw.ImageDraw,
        width: int,
        height: int,
        prompt_lower: str,
        rng: random.Random,
        page_number: Any,
        panel_order: Any,
    ) -> None:
        if "stair" in prompt_lower:
            base_y = int(height * 0.78)
            for step in range(7):
                x0 = int(width * 0.48) + step * max(10, width // 35)
                y0 = base_y - step * max(9, height // 36)
                draw.polygon(
                    [(x0, y0), (width, y0 - max(8, height // 80)), (width, y0 + max(10, height // 60)), (x0, y0 + max(18, height // 38))],
                    fill=(36 + step * 8, 36 + step * 8, 36 + step * 8),
                )
        if "bridge" in prompt_lower or str(page_number) == "4":
            y = int(height * 0.72)
            draw.polygon([(0, y), (width, y - height // 14), (width, y + height // 18), (0, y + height // 10)], fill=(28, 30, 34))
            for x in range(0, width, max(26, width // 16)):
                draw.line((x, y - height // 20, x + width // 20, y + height // 9), fill=(238, 238, 232), width=2)
        if "lantern" in prompt_lower or "mio" in prompt_lower:
            for radius in range(max(24, min(width, height) // 18), max(56, min(width, height) // 4), max(16, min(width, height) // 24)):
                cx = int(width * 0.68)
                cy = int(height * 0.62)
                tone = 245 - min(60, radius // 4)
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(tone, tone, tone), width=2)
        if str(page_number) == "1" and str(panel_order) == "1":
            draw.rectangle((0, int(height * 0.52), width, height), fill=(230, 230, 224))
            self._draw_rain_lines(draw, width, height, rng)

    def _draw_ash_spirits(self, draw: ImageDraw.ImageDraw, width: int, height: int, rng: random.Random) -> None:
        for _ in range(8):
            cx = rng.randint(int(width * 0.04), int(width * 0.94))
            cy = rng.randint(int(height * 0.18), int(height * 0.72))
            scale = rng.uniform(0.55, 1.15)
            points = []
            for index in range(9):
                angle = index * 6.283185307179586 / 9
                radius = int(min(width, height) * rng.uniform(0.018, 0.045) * scale)
                points.append((int(cx + math.cos(angle) * radius), int(cy + math.sin(angle) * radius * 1.8)))
            draw.polygon(points, fill=(12, 14, 18))
            for claw in range(3):
                x = cx + claw * int(8 * scale)
                draw.line((x, cy, x + int(22 * scale), cy + int(34 * scale)), fill=(12, 14, 18), width=max(2, int(3 * scale)))

    def _bubble_text(self, page_number: Any, panel_order: Any) -> str:
        snippets = {
            ("1", "1"): "Only rain answered.",
            ("1", "2"): "A small light moved.",
            ("1", "3"): "I was waiting.",
            ("2", "1"): "She cast no shadow.",
            ("2", "2"): "Stay behind me.",
            ("2", "3"): "They fear your light.",
            ("3", "1"): "Do not let it die.",
            ("3", "2"): "The city answered.",
            ("3", "3"): "When I move, run.",
            ("4", "1"): "I know a road.",
            ("4", "2"): "He was not alone.",
            ("4", "3"): "The road opened for two.",
        }
        return snippets.get((str(page_number), str(panel_order)), "Draft manga panel")

    def _draw_demo_bubble(self, draw: ImageDraw.ImageDraw, width: int, height: int, text: str, font: ImageFont.ImageFont) -> None:
        x0 = int(width * 0.08)
        y0 = int(height * 0.08)
        x1 = int(width * 0.55)
        y1 = int(height * 0.28)
        draw.rounded_rectangle((x0, y0, x1, y1), radius=max(14, min(width, height) // 24), fill=(255, 255, 250), outline=(12, 14, 18), width=max(2, min(width, height) // 120))
        draw.polygon([(x1 - 32, y1 - 4), (x1 + 18, y1 + 44), (x1 - 78, y1 - 18)], fill=(255, 255, 250), outline=(12, 14, 18))
        max_chars = max(18, (x1 - x0) // 8)
        lines: list[str] = []
        for raw_line in text.splitlines():
            lines.extend(textwrap.wrap(raw_line, width=max_chars)[:3])
        for index, line in enumerate(lines[:5]):
            draw.text((x0 + 18, y0 + 16 + index * 16), line, fill=(12, 14, 18), font=font)

    def edit_image(
        self,
        input_image: bytes,
        mask: bytes | None,
        prompt: str,
        options: dict[str, Any],
    ) -> GeneratedImage:
        return self.generate_image(prompt, options.get("size", "1024x1024"), [], options)


class OpenAIImageProvider:
    name = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.model_name = settings.openai_image_model

    def generate_image(
        self,
        prompt: str,
        size: str,
        references: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> GeneratedImage:
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY is required for OpenAI image rendering")

        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        request: dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "size": size,
            "n": 1,
        }
        if self.model_name.startswith("gpt-image"):
            request["output_format"] = options.get("output_format", "png")
            request["quality"] = options.get("quality", "auto")
        else:
            request["response_format"] = "b64_json"
            if "quality" in options:
                request["quality"] = options["quality"]

        response = client.images.generate(**request)
        first = response.data[0]
        b64_image = getattr(first, "b64_json", None)
        if not b64_image:
            raise ProviderError("OpenAI image response did not include base64 image data")
        data = base64.b64decode(b64_image)
        width, height = parse_size(size)
        usage = getattr(response, "usage", None)
        return GeneratedImage(
            data=data,
            width=width,
            height=height,
            model_name=self.model_name,
            seed=options.get("seed"),
            provider_metadata={"references": len(references), "usage": usage.model_dump() if hasattr(usage, "model_dump") else usage},
        )

    def edit_image(
        self,
        input_image: bytes,
        mask: bytes | None,
        prompt: str,
        options: dict[str, Any],
    ) -> GeneratedImage:
        raise ProviderError("OpenAI image editing is not implemented in Manga AI Studio yet")


class ComfyUIProvider:
    name = "comfyui"
    model_name = "comfyui-workflow"

    def __init__(self) -> None:
        self.base_url = (get_settings().comfyui_base_url or "").rstrip("/")

    def generate_image(
        self,
        prompt: str,
        size: str,
        references: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> GeneratedImage:
        if not self.base_url:
            raise ProviderError("COMFYUI_BASE_URL is required for ComfyUI rendering")

        workflow = options.get("workflow_template")
        if not workflow:
            raise ProviderError("ComfyUI workflow_template option is required")
        if isinstance(workflow, str):
            try:
                workflow = json.loads(workflow)
            except json.JSONDecodeError as exc:
                raise ProviderError("ComfyUI workflow_template must be valid JSON") from exc

        payload = {
            "prompt": workflow,
            "client_id": str(uuid.uuid4()),
            "extra_data": {
                "manga_ai_prompt": prompt,
                "size": size,
                "references": references,
            },
        }
        try:
            response = httpx.post(f"{self.base_url}/prompt", json=payload, timeout=20)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"ComfyUI queue request failed: {exc}") from exc

        raise ProviderError("ComfyUI accepted the workflow, but output retrieval is not implemented yet")

    def edit_image(
        self,
        input_image: bytes,
        mask: bytes | None,
        prompt: str,
        options: dict[str, Any],
    ) -> GeneratedImage:
        raise ProviderError("ComfyUI image editing is not implemented in Manga AI Studio yet")


class RenderOrchestrator:
    def __init__(self, session: Session, object_store: ObjectStore | None = None) -> None:
        self.session = session
        self.object_store = object_store

    def render_panel(
        self,
        panel_id: uuid.UUID | str,
        provider_name: str = "mock",
        *,
        options: dict[str, Any] | None = None,
        job: GenerationJob | uuid.UUID | str | None = None,
    ) -> GenerationJob:
        provider_name = provider_name.lower().strip()
        parsed_panel_id = uuid.UUID(str(panel_id))
        panel = self.session.get(Panel, parsed_panel_id)
        if panel is None:
            raise ValueError("Panel not found")

        page = self.session.get(Page, panel.page_id)
        if page is None:
            raise ValueError("Panel references a missing page")

        project = self.session.get(Project, page.project_id)
        if project is None:
            raise ValueError("Panel page references a missing project")

        render_job = self._resolve_job(job)
        if render_job is not None and render_job.panel_id not in (None, panel.id):
            raise ValueError("Render job references a different panel")

        provider_options = self._merge_options(render_job, options)
        if render_job is None:
            render_job = GenerationJob(
                project_id=project.id,
                page_id=page.id,
                panel_id=panel.id,
                provider=provider_name,
                job_type="render_panel",
                status="running",
            )
        render_job.project_id = project.id
        render_job.page_id = page.id
        render_job.panel_id = panel.id
        render_job.provider = provider_name
        render_job.job_type = "render_panel"
        render_job.status = "running"
        render_job.error_message = None
        render_job.updated_at = utc_now()
        self.session.add(render_job)
        self.session.flush()

        started_at = utc_now()
        safe_provider: dict[str, Any] | None = None
        prompt_record: PanelRenderPrompt | None = None
        size = normalize_size(panel.width, panel.height)
        cost_metadata: dict[str, Any] = {}
        try:
            safe_provider = provider_summary(provider_name)
            provider = get_image_provider(provider_name)
            prompt_record = self._resolve_prompt_record(panel.id, provider_name, provider_options)
            prompt_json = prompt_record.structured_context
            prompt_text = prompt_record.positive_prompt
            size = prompt_record.size or normalize_size(panel.width, panel.height)
            seed = int(prompt_record.seed or provider_options.get("seed") or stable_seed(json.dumps(prompt_json, sort_keys=True)))
            validation_warnings = validate_provider_request(provider_name, size)
            blocking_warnings = [
                warning
                for warning in validation_warnings
                if "not configured" in warning.lower() or "exceeds" in warning.lower() or "unsupported" in warning.lower()
            ]
            if blocking_warnings:
                raise ProviderError("; ".join(blocking_warnings))
            provider_options = {
                **provider_options,
                "panel_render_prompt_id": str(prompt_record.id),
                "render_mode": prompt_record.quality_mode,
                "quality_mode": prompt_record.quality_mode,
                "seed": seed,
                "panel_id": str(panel.id),
                "page_id": str(page.id),
                "project_id": str(project.id),
                "page_number": page.page_number,
                "panel_order": panel.reading_order,
                "panel_width": panel.width,
                "panel_height": panel.height,
            }
            references = prompt_json.get("references", [])
            estimated_cost = estimate_image_cost(provider.name, size, prompt_record.quality_mode)
            cost_metadata = build_render_cost_metadata(
                provider=provider.name,
                model=provider.model_name,
                size=size,
                quality_mode=prompt_record.quality_mode,
                estimated_cost=estimated_cost,
                started_at=started_at,
            )
            render_job.input_payload = {
                "panel_render_prompt_id": str(prompt_record.id),
                "prompt_json": prompt_json,
                "prompt": prompt_text,
                "negative_prompt": prompt_record.negative_prompt,
                "provider": provider.name,
                "model_name": provider.model_name,
                "size": size,
                "references": references,
                "options": provider_options,
                "provider_capabilities": safe_provider,
                "cost_metadata": cost_metadata,
            }
            self.session.add(render_job)
            self.session.flush()

            generated: GeneratedImage | None = None
            last_error: Exception | None = None
            attempts = max(1, int(provider_options.get("retries", 0)) + 1)
            logger.info(
                "image provider call started",
                extra={
                    "job_id": str(render_job.id),
                    "project_id": str(project.id),
                    "page_id": str(page.id),
                    "panel_id": str(panel.id),
                    "provider": provider.name,
                },
            )
            for attempt in range(attempts):
                try:
                    generated = provider.generate_image(prompt_text, size, references, {**provider_options, "attempt": attempt + 1})
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt >= attempts - 1:
                        raise
            if generated is None:
                raise last_error or ProviderError("Provider did not return an image")
            completed_at = utc_now()
            cost_metadata = {
                **cost_metadata,
                "model": generated.model_name or provider.model_name,
                "actual_usage": (generated.provider_metadata or {}).get("usage"),
                "completed_at": completed_at.isoformat(),
                "duration_ms": int((completed_at - started_at).total_seconds() * 1000),
            }
            logger.info(
                "image provider call succeeded",
                extra={
                    "job_id": str(render_job.id),
                    "project_id": str(project.id),
                    "page_id": str(page.id),
                    "panel_id": str(panel.id),
                    "provider": provider.name,
                },
            )
            storage_key = f"renders/{project.id}/{render_job.id}.png"
            public_url: str | None = None
            if self.object_store is not None:
                self.object_store.put_bytes(key=storage_key, data=generated.data, content_type=generated.content_type)
                public_url = self.object_store.public_url(storage_key)

            asset = Asset(
                project_id=project.id,
                filename=f"panel-{panel.id}.png",
                kind="render",
                content_type=generated.content_type,
                size_bytes=len(generated.data),
                storage_key=storage_key,
                metadata_json={
                    "job_id": str(render_job.id),
                    "panel_id": str(panel.id),
                    "provider": provider.name,
                    "model_name": generated.model_name or provider.model_name,
                    "seed": generated.seed,
                    "panel_render_prompt_id": str(prompt_record.id),
                    "render_mode": prompt_record.quality_mode,
                    "approved": False,
                    "options": provider_options,
                    "provider_metadata": generated.provider_metadata or {},
                    "cost_metadata": cost_metadata,
                },
            )
            self.session.add(asset)
            self.session.flush()
            ProvenanceService(self.session).record_asset(
                asset,
                source_type="internal_mock" if provider.name == "mock" else "ai_generated",
                provider_name=provider.name,
                model_name=generated.model_name or provider.model_name,
                prompt_id=prompt_record.id,
                generation_job_id=render_job.id,
                declared_rights="Generated inside Manga AI Studio using the configured render provider.",
                license_type="project_generated",
                allow_training=False,
                allow_commercial_use=True,
                ai_disclosure_required=True,
            )

            render = Render(
                job_id=render_job.id,
                panel_id=panel.id,
                asset_id=asset.id,
                storage_key=storage_key,
                public_url=public_url,
                width=generated.width,
                height=generated.height,
                mime_type=generated.content_type,
            )
            render_job.status = "succeeded"
            render_job.output_payload = {
                "asset_id": str(asset.id),
                "render_id": str(render.id),
                "storage_key": storage_key,
                "public_url": public_url,
                "provider": provider.name,
                "model_name": generated.model_name or provider.model_name,
                "seed": generated.seed,
                "panel_render_prompt_id": str(prompt_record.id),
                "render_mode": prompt_record.quality_mode,
                "options": provider_options,
                "cost_metadata": cost_metadata,
            }
            render_job.updated_at = utc_now()
            self.session.add(render)
            self.session.add(render_job)
            self.session.commit()
            self.session.refresh(render_job)
            return render_job
        except Exception as exc:
            completed_at = utc_now()
            if not cost_metadata:
                try:
                    summary = safe_provider or provider_summary(provider_name)
                    model_name = summary.get("model_name")
                except Exception:
                    summary = {"name": provider_name, "configured": False, "missing_env_vars": []}
                    model_name = None
                quality_mode = prompt_record.quality_mode if prompt_record is not None else str(provider_options.get("quality_mode") or provider_options.get("render_mode") or "draft")
                cost_metadata = build_render_cost_metadata(
                    provider=provider_name,
                    model=str(model_name or provider_name),
                    size=size,
                    quality_mode=quality_mode,
                    estimated_cost=estimate_image_cost(provider_name, size, quality_mode) if summary.get("name") else {},
                    started_at=started_at,
                )
            cost_metadata = {
                **cost_metadata,
                "completed_at": completed_at.isoformat(),
                "duration_ms": int((completed_at - started_at).total_seconds() * 1000),
            }
            error_metadata = safe_provider_error(exc, provider_name, safe_provider)
            render_job.status = "failed"
            render_job.error_message = error_metadata["user_message"]
            render_job.output_payload = {
                **(render_job.output_payload or {}),
                "provider": provider_name,
                "model_name": cost_metadata.get("model"),
                "panel_render_prompt_id": str(prompt_record.id) if prompt_record is not None else None,
                "render_mode": cost_metadata.get("quality_mode"),
                "requested_size": cost_metadata.get("requested_size"),
                "cost_metadata": cost_metadata,
                "error_metadata": error_metadata,
                "retry_available": True,
                "retry_provider": "mock",
            }
            render_job.updated_at = utc_now()
            self.session.add(render_job)
            self.session.commit()
            self.session.refresh(render_job)
            logger.warning(
                "image provider call failed",
                extra={
                    "job_id": str(render_job.id),
                    "project_id": str(project.id),
                    "page_id": str(page.id),
                    "panel_id": str(panel.id),
                    "provider": provider_name,
                },
            )
            return render_job

    def _resolve_prompt_record(
        self,
        panel_id: uuid.UUID,
        provider_name: str,
        provider_options: dict[str, Any],
    ) -> PanelRenderPrompt:
        prompt_id = provider_options.get("panel_render_prompt_id")
        if prompt_id:
            prompt_record = self.session.get(PanelRenderPrompt, uuid.UUID(str(prompt_id)))
            if prompt_record is None:
                raise ValueError("Panel render prompt not found")
            if prompt_record.panel_id != panel_id:
                raise ValueError("Panel render prompt references a different panel")
            return prompt_record

        from manga_api.panel_render_director import PanelRenderDirector

        return PanelRenderDirector(self.session).build_prompt(
            panel_id,
            provider_name=provider_name,
            render_mode=str(provider_options.get("render_mode") or provider_options.get("quality_mode") or "draft"),
            seed=provider_options.get("seed"),
            advanced_prompt_override=provider_options.get("advanced_prompt_override"),
            additional_user_instruction=provider_options.get("additional_user_instruction"),
            camera_instruction=provider_options.get("camera_instruction"),
            expression_instruction=provider_options.get("expression_instruction"),
            preserve_layout=bool(provider_options.get("preserve_layout", True)),
        )

    def _resolve_job(self, job: GenerationJob | uuid.UUID | str | None) -> GenerationJob | None:
        if job is None:
            return None
        if isinstance(job, GenerationJob):
            return job
        return self.session.get(GenerationJob, uuid.UUID(str(job)))

    @staticmethod
    def _merge_options(job: GenerationJob | None, options: dict[str, Any] | None) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        if job is not None and isinstance(job.input_payload, dict):
            job_options = job.input_payload.get("options")
            if isinstance(job_options, dict):
                merged.update(job_options)
        if options:
            merged.update(options)
        return merged


def build_render_cost_metadata(
    *,
    provider: str,
    model: str,
    size: str,
    quality_mode: str,
    estimated_cost: dict[str, Any],
    started_at: datetime,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "model": model,
        "requested_size": size,
        "quality_mode": quality_mode,
        "estimated_cost": estimated_cost,
        "actual_usage": None,
        "started_at": started_at.isoformat(),
        "completed_at": None,
    }


def safe_provider_error(exc: Exception, provider_name: str, provider: dict[str, Any] | None = None) -> dict[str, Any]:
    raw_message = str(exc) or type(exc).__name__
    scrubbed = scrub_secret_like_text(raw_message)
    configured = bool(provider.get("configured")) if provider else False
    missing_env_vars = list(provider.get("missing_env_vars", [])) if provider else []
    if missing_env_vars:
        user_message = f"{provider_name} is not configured. Missing: {', '.join(missing_env_vars)}."
    elif isinstance(exc, ProviderError):
        user_message = scrubbed[:500]
    else:
        user_message = f"{provider_name} render failed. Check provider settings or retry with mock."
    return {
        "provider": provider_name,
        "error_type": type(exc).__name__,
        "safe_message": scrubbed[:2000],
        "user_message": user_message[:1000],
        "configured": configured,
        "missing_env_vars": missing_env_vars,
        "retry_with_mock_available": True,
    }


def scrub_secret_like_text(value: str) -> str:
    scrubbed = value
    markers = ["sk-", "OPENAI_API_KEY=", "api_key=", "Authorization:"]
    for marker in markers:
        index = scrubbed.find(marker)
        while index != -1:
            end = index + len(marker)
            while end < len(scrubbed) and not scrubbed[end].isspace() and scrubbed[end] not in "',;":
                end += 1
            scrubbed = scrubbed[:index] + marker + "[redacted]" + scrubbed[end:]
            index = scrubbed.find(marker, index + len(marker) + 10)
    return scrubbed


def get_image_provider(provider_name: str) -> ImageProvider:
    normalized = provider_name.lower()
    if normalized == "mock":
        return MockImageProvider()
    if normalized == "openai":
        return OpenAIImageProvider()
    if normalized == "comfyui":
        return ComfyUIProvider()
    raise ProviderError(f"Unsupported image provider: {provider_name}")


def assemble_panel_prompt(session: Session, project: Project, page: Page, panel: Panel) -> dict[str, Any]:
    reference_pack = ReferencePackBuilder(session).build_for_panel(panel.id)
    story_bible = session.exec(
        select(StoryBible)
        .where(StoryBible.project_id == project.id)
        .order_by(StoryBible.created_at.desc())
    ).first()
    style_bible = None
    if project.active_style_bible_id is not None:
        style_bible = session.get(StyleBible, project.active_style_bible_id)
    if style_bible is None:
        style_bible = session.exec(
            select(StyleBible)
            .where(StyleBible.project_id == project.id)
            .order_by(StyleBible.created_at.desc())
        ).first()

    page_plan = session.exec(
        select(PagePlan)
        .where(PagePlan.project_id == project.id, PagePlan.page_number == page.page_number)
        .order_by(PagePlan.created_at.desc())
    ).first()
    panel_plan = None
    if page_plan is not None:
        panel_plan = session.exec(
            select(PanelPlan)
            .where(PanelPlan.page_plan_id == page_plan.id, PanelPlan.panel_order == panel.reading_order)
        ).first()

    character_cards = session.exec(
        select(CharacterCard)
        .where(CharacterCard.project_id == project.id)
        .order_by(CharacterCard.name.asc())
    ).all()
    character_refs = session.exec(
        select(CharacterReferenceAsset)
        .where(CharacterReferenceAsset.project_id == project.id)
        .order_by(CharacterReferenceAsset.created_at.desc())
    ).all()
    style_refs = []
    if style_bible is not None:
        style_refs = session.exec(
            select(StyleSampleAsset)
            .where(StyleSampleAsset.style_bible_id == style_bible.id)
            .order_by(StyleSampleAsset.created_at.desc())
        ).all()
    locations = []
    key_objects = []
    if story_bible is not None:
        locations = session.exec(
            select(Location)
            .where(Location.story_bible_id == story_bible.id)
            .order_by(Location.name.asc())
        ).all()
        key_objects = session.exec(
            select(KeyObject)
            .where(KeyObject.story_bible_id == story_bible.id)
            .order_by(KeyObject.name.asc())
        ).all()

    base_references = [
        *[asset_to_reference(asset, "character") for asset in character_refs],
        *[asset_to_reference(asset, "style") for asset in style_refs],
    ]
    references = dedupe_references([*reference_pack.get("approved_visual_references", []), *base_references])
    consistency_requirements = build_consistency_requirements(reference_pack, panel_plan, style_bible)
    return {
        "project": {
            "id": str(project.id),
            "name": project.name,
            "description": project.description,
            "style_prompt": project.style_prompt,
        },
        "style_bible": style_bible_to_prompt(style_bible),
        "story_bible": story_bible_to_prompt(story_bible),
        "page_plan": page_plan_to_prompt(page_plan),
        "panel_plan": panel_plan_to_prompt(panel_plan),
        "characters": [character_card_to_prompt(card) for card in character_cards],
        "locations": [location_to_prompt(location) for location in locations],
        "key_objects": [key_object_to_prompt(key_object) for key_object in key_objects],
        "reference_pack": reference_pack,
        "consistency_requirements": consistency_requirements,
        "negative_prompt": consistency_requirements["negative_prompt"],
        "panel_layout": {
            "page_id": str(page.id),
            "page_number": page.page_number,
            "page_width": page.width,
            "page_height": page.height,
            "layout": page.layout_json,
            "panel_id": str(panel.id),
            "x": panel.x,
            "y": panel.y,
            "width": panel.width,
            "height": panel.height,
            "polygon": panel.polygon,
            "reading_order": panel.reading_order,
            "prompt": panel.prompt,
        },
        "references": references,
    }


def prompt_json_to_text(prompt_json: dict[str, Any]) -> str:
    parts = [
        "Render a finished black-and-white manga panel.",
        f"Project: {prompt_json['project']['name']}",
        f"Panel layout: {prompt_json['panel_layout']}",
    ]
    for key in ["style_bible", "story_bible", "page_plan", "panel_plan"]:
        value = prompt_json.get(key)
        if value:
            parts.append(f"{key}: {json.dumps(value, ensure_ascii=True)}")
    consistency = prompt_json.get("consistency_requirements") or {}
    if consistency:
        parts.extend(
            [
                f"Character identity anchors: {json.dumps(consistency.get('character_identity_anchors', []), ensure_ascii=True)}",
                f"Outfit/injury continuity: {json.dumps(consistency.get('outfit_injury_continuity', []), ensure_ascii=True)}",
                f"Scene lighting: {consistency.get('scene_lighting', '')}",
                f"Location anchors: {json.dumps(consistency.get('location_anchors', []), ensure_ascii=True)}",
                f"Forbidden changes: {json.dumps(consistency.get('forbidden_changes', []), ensure_ascii=True)}",
                f"Composition/camera: {json.dumps(consistency.get('composition_camera', {}), ensure_ascii=True)}",
                f"Negative prompt: {consistency.get('negative_prompt', '')}",
            ]
        )
    if prompt_json.get("characters"):
        parts.append(f"characters: {json.dumps(prompt_json['characters'], ensure_ascii=True)}")
    if prompt_json.get("locations"):
        parts.append(f"locations: {json.dumps(prompt_json['locations'], ensure_ascii=True)}")
    if prompt_json.get("key_objects"):
        parts.append(f"key_objects: {json.dumps(prompt_json['key_objects'], ensure_ascii=True)}")
    if prompt_json.get("reference_pack"):
        parts.append(f"reference_pack: {json.dumps(prompt_json['reference_pack'], ensure_ascii=True)}")
    return "\n".join(parts)


def build_consistency_requirements(
    reference_pack: dict[str, Any],
    panel_plan: PanelPlan | None,
    style_bible: StyleBible | None,
) -> dict[str, Any]:
    identity_anchors: list[str] = []
    outfit_injury: list[str] = []
    forbidden_changes: list[str] = []
    for entry in reference_pack.get("characters", []):
        card = entry.get("card", {})
        state = entry.get("state")
        identity_anchors.extend(character_anchor_values(card))
        outfit_injury.extend(state_anchor_values(state))
        if card.get("outfit_default"):
            outfit_injury.append(f"default outfit: {card['outfit_default']}")
        if card.get("injury_state"):
            outfit_injury.append(f"card injury state: {card['injury_state']}")
        forbidden_changes.extend(str(item) for item in card.get("forbidden_changes", []))
        forbidden_changes.extend(str(item) for item in card.get("forbidden_variations", []))

    location_anchors: list[str] = []
    for location in reference_pack.get("locations", []):
        location_anchors.append(location.get("name", ""))
        if location.get("visual_notes"):
            location_anchors.append(location["visual_notes"])
        location_anchors.extend(location.get("rules", []))

    story_memory = reference_pack.get("story_memory", {})
    scene = story_memory.get("scene") or {}
    page_plan_memory = story_memory.get("page_plan") or {}
    panel_plan_memory = story_memory.get("panel_plan") or {}
    scene_lighting = infer_scene_lighting(scene, page_plan_memory, panel_plan_memory)
    negative_prompt_parts: list[str] = []
    if style_bible is not None:
        negative_prompt_parts.append(style_bible.prompt_style_negative)
        negative_prompt_parts.extend(style_bible.negative_prompt_fragments)
        negative_prompt_parts.extend(style_bible.forbidden_artist_references)
        negative_prompt_parts.extend(style_bible.forbidden_franchise_references)
        negative_prompt_parts.extend(style_bible.negative_prompts)
        negative_prompt_parts.extend(style_bible.forbidden_references)
    negative_prompt_parts.extend(forbidden_changes)

    return {
        "character_identity_anchors": clean_strings(identity_anchors),
        "outfit_injury_continuity": clean_strings(outfit_injury),
        "scene_lighting": scene_lighting,
        "location_anchors": clean_strings(location_anchors),
        "forbidden_changes": clean_strings(forbidden_changes),
        "composition_camera": {
            "shot_type": panel_plan.shot_type if panel_plan else panel_plan_memory.get("shot_type"),
            "camera_angle": panel_plan.camera_angle if panel_plan else panel_plan_memory.get("camera_angle"),
            "story_beat": panel_plan.story_beat if panel_plan else panel_plan_memory.get("story_beat"),
            "visual_notes": panel_plan.visual_notes if panel_plan else panel_plan_memory.get("visual_notes"),
            "emotional_intent": panel_plan.emotional_intent if panel_plan else panel_plan_memory.get("emotional_intent"),
        },
        "style_bible": reference_pack.get("style_bible"),
        "negative_prompt": "; ".join(clean_strings(negative_prompt_parts)),
    }


def infer_scene_lighting(scene: dict[str, Any], page_plan: dict[str, Any], panel_plan: dict[str, Any]) -> str:
    hints = [
        str(scene.get("summary") or ""),
        str(scene.get("emotional_turn") or ""),
        str(page_plan.get("summary") or ""),
        str(panel_plan.get("visual_notes") or ""),
    ]
    joined = " ".join(hints).lower()
    if "rain" in joined:
        return "Wet, overcast scene lighting with reflective ground shadows; keep it continuous across adjacent panels."
    if "night" in joined or "ghost" in joined:
        return "Low-key supernatural lighting with readable silhouettes and consistent rim highlights."
    if "day" in joined or "sun" in joined:
        return "Clear daylight with stable cast shadows and consistent value grouping."
    return "Use lighting consistent with the scene memory; preserve shadows, value grouping, and emotional continuity."


def clean_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def style_bible_to_prompt(style: StyleBible | None) -> dict[str, Any] | None:
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


def story_bible_to_prompt(story: StoryBible | None) -> dict[str, Any] | None:
    if story is None:
        return None
    return {
        "id": str(story.id),
        "logline": story.logline,
        "synopsis": story.synopsis,
        "genre": story.genre,
        "themes": story.themes,
        "tone": story.tone,
        "main_conflict": story.main_conflict,
        "world_rules": story.world_rules,
        "continuity_rules": story.continuity_rules,
    }


def page_plan_to_prompt(page_plan: PagePlan | None) -> dict[str, Any] | None:
    if page_plan is None:
        return None
    return {
        "id": str(page_plan.id),
        "page_number": page_plan.page_number,
        "summary": page_plan.summary,
        "pacing": page_plan.pacing,
        "panel_count": page_plan.panel_count,
    }


def panel_plan_to_prompt(panel_plan: PanelPlan | None) -> dict[str, Any] | None:
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


def character_card_to_prompt(card: CharacterCard) -> dict[str, Any]:
    return {
        "id": str(card.id),
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
    }


def location_to_prompt(location: Location) -> dict[str, Any]:
    return {
        "id": str(location.id),
        "name": location.name,
        "description": location.description,
        "visual_notes": location.visual_notes,
        "rules": location.rules,
    }


def key_object_to_prompt(key_object: KeyObject) -> dict[str, Any]:
    return {
        "id": str(key_object.id),
        "name": key_object.name,
        "description": key_object.description,
        "significance": key_object.significance,
        "visual_notes": key_object.visual_notes,
    }


def asset_to_reference(asset: CharacterReferenceAsset | StyleSampleAsset, kind: str) -> dict[str, Any]:
    return {
        "id": str(asset.id),
        "kind": kind,
        "filename": asset.filename,
        "content_type": asset.content_type,
        "storage_key": asset.storage_key,
        "metadata": asset.metadata_json,
    }


def parse_size(size: str) -> tuple[int, int]:
    width, height = size.lower().split("x", 1)
    return int(width), int(height)


def normalize_size(width: int, height: int) -> str:
    safe_width = max(64, min(2048, int(width)))
    safe_height = max(64, min(2048, int(height)))
    return f"{safe_width}x{safe_height}"


def stable_seed(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def color_from_seed(seed: int) -> tuple[int, int, int]:
    return (
        225 + seed % 24,
        225 + (seed // 7) % 24,
        220 + (seed // 13) % 24,
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
