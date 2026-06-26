from __future__ import annotations

from typing import Protocol

from manga_api.rendering import GeneratedImage as RenderedImage
from manga_api.rendering import ImageProvider, get_image_provider


class RenderProvider(Protocol):
    name: str
    model_name: str

    def render_panel(self, *, panel_id: str, width: int, height: int, prompt: str | None) -> RenderedImage:
        """Compatibility wrapper for older worker smoke checks."""


class RenderProviderAdapter:
    def __init__(self, image_provider: ImageProvider) -> None:
        self.image_provider = image_provider
        self.name = image_provider.name
        self.model_name = image_provider.model_name

    def render_panel(self, *, panel_id: str, width: int, height: int, prompt: str | None) -> RenderedImage:
        return self.image_provider.generate_image(
            prompt or "Render manga panel",
            f"{width}x{height}",
            [],
            {"panel_id": panel_id},
        )


def get_render_provider(provider_name: str) -> RenderProvider:
    return RenderProviderAdapter(get_image_provider(provider_name))
