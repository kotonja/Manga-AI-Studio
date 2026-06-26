from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from manga_api.config import get_settings


@dataclass(frozen=True)
class ProviderCapabilities:
    supports_image_generation: bool
    supports_image_editing: bool
    supports_references: bool
    supports_seeds: bool
    supports_async_jobs: bool
    max_resolution: tuple[int, int]


@dataclass(frozen=True)
class ProviderRegistryEntry:
    name: str
    display_name: str
    model_name: str
    capabilities: ProviderCapabilities
    requires_env_vars: tuple[str, ...]
    cost_warning: str
    notes: str


PROVIDER_REGISTRY: dict[str, ProviderRegistryEntry] = {
    "mock": ProviderRegistryEntry(
        name="mock",
        display_name="Mock Image Provider",
        model_name="mock-image-v1",
        capabilities=ProviderCapabilities(
            supports_image_generation=True,
            supports_image_editing=True,
            supports_references=False,
            supports_seeds=True,
            supports_async_jobs=False,
            max_resolution=(4096, 4096),
        ),
        requires_env_vars=(),
        cost_warning="No external calls or paid usage.",
        notes="Deterministic local placeholder provider for tests, demos, and offline development.",
    ),
    "openai": ProviderRegistryEntry(
        name="openai",
        display_name="OpenAI Image Provider",
        model_name="",
        capabilities=ProviderCapabilities(
            supports_image_generation=True,
            supports_image_editing=False,
            supports_references=False,
            supports_seeds=False,
            supports_async_jobs=False,
            max_resolution=(2048, 2048),
        ),
        requires_env_vars=("OPENAI_API_KEY", "OPENAI_IMAGE_MODEL"),
        cost_warning="Real OpenAI image generation may incur API costs.",
        notes="Dry-run validates configuration and prompt assembly without calling the OpenAI API.",
    ),
    "comfyui": ProviderRegistryEntry(
        name="comfyui",
        display_name="ComfyUI Provider",
        model_name="comfyui-workflow",
        capabilities=ProviderCapabilities(
            supports_image_generation=True,
            supports_image_editing=False,
            supports_references=True,
            supports_seeds=True,
            supports_async_jobs=True,
            max_resolution=(4096, 4096),
        ),
        requires_env_vars=("COMFYUI_BASE_URL",),
        cost_warning="Local or remote ComfyUI cost depends on your ComfyUI deployment.",
        notes="Requires a workflow template; output retrieval remains provider-specific.",
    ),
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_provider_name(name: str) -> str:
    return name.lower().strip()


def get_provider_entry(name: str) -> ProviderRegistryEntry | None:
    return PROVIDER_REGISTRY.get(normalize_provider_name(name))


def provider_config(name: str) -> dict[str, Any]:
    settings = get_settings()
    normalized = normalize_provider_name(name)
    entry = get_provider_entry(normalized)
    if entry is None:
        return {
            "name": normalized,
            "configured": False,
            "missing_env_vars": [],
            "model_name": None,
        }
    values = {
        "OPENAI_API_KEY": settings.openai_api_key,
        "OPENAI_IMAGE_MODEL": settings.openai_image_model,
        "COMFYUI_BASE_URL": settings.comfyui_base_url,
    }
    missing = [key for key in entry.requires_env_vars if not values.get(key)]
    model_name = entry.model_name
    if normalized == "openai":
        model_name = settings.openai_image_model
    return {
        "name": normalized,
        "configured": not missing,
        "missing_env_vars": missing,
        "model_name": model_name,
    }


def provider_summary(name: str) -> dict[str, Any]:
    normalized = normalize_provider_name(name)
    entry = get_provider_entry(normalized)
    if entry is None:
        raise KeyError(f"Unsupported image provider: {name}")
    config = provider_config(normalized)
    capabilities = entry.capabilities
    return {
        "name": entry.name,
        "display_name": entry.display_name,
        "model_name": config["model_name"],
        "capabilities": {
            "supports_image_generation": capabilities.supports_image_generation,
            "supports_image_editing": capabilities.supports_image_editing,
            "supports_references": capabilities.supports_references,
            "supports_seeds": capabilities.supports_seeds,
            "supports_async_jobs": capabilities.supports_async_jobs,
        },
        "max_resolution": {
            "width": capabilities.max_resolution[0],
            "height": capabilities.max_resolution[1],
        },
        "requires_env_vars": list(entry.requires_env_vars),
        "configured": bool(config["configured"]),
        "missing_env_vars": list(config["missing_env_vars"]),
        "cost_warning": entry.cost_warning,
        "notes": entry.notes,
    }


def list_provider_summaries() -> list[dict[str, Any]]:
    return [provider_summary(name) for name in PROVIDER_REGISTRY]


def provider_health(name: str) -> dict[str, Any]:
    normalized = normalize_provider_name(name)
    entry = get_provider_entry(normalized)
    if entry is None:
        raise KeyError(f"Unsupported image provider: {name}")
    summary = provider_summary(normalized)
    checked_at = utc_now_iso()
    if not summary["configured"]:
        return {
            "name": normalized,
            "status": "not_configured",
            "configured": False,
            "message": f"{entry.display_name} is missing required environment variables.",
            "checked_at": checked_at,
            "details": {"missing_env_vars": summary["missing_env_vars"]},
        }
    if normalized == "mock":
        return {
            "name": normalized,
            "status": "healthy",
            "configured": True,
            "message": "Mock provider is available locally.",
            "checked_at": checked_at,
            "details": {},
        }
    if normalized == "openai":
        return {
            "name": normalized,
            "status": "configured",
            "configured": True,
            "message": "OpenAI provider is configured. Health checks do not call paid generation APIs.",
            "checked_at": checked_at,
            "details": {"model_name": summary["model_name"]},
        }
    if normalized == "comfyui":
        base_url = str(get_settings().comfyui_base_url or "").rstrip("/")
        try:
            response = httpx.get(f"{base_url}/system_stats", timeout=3)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return {
                "name": normalized,
                "status": "unreachable",
                "configured": True,
                "message": "ComfyUI is configured but not reachable.",
                "checked_at": checked_at,
                "details": {"error_type": type(exc).__name__, "safe_error": str(exc)[:500]},
            }
        return {
            "name": normalized,
            "status": "healthy",
            "configured": True,
            "message": "ComfyUI responded to a non-generation health check.",
            "checked_at": checked_at,
            "details": {"status_code": response.status_code},
        }
    return {
        "name": normalized,
        "status": "unknown",
        "configured": bool(summary["configured"]),
        "message": "Provider health is unknown.",
        "checked_at": checked_at,
        "details": {},
    }


def validate_provider_request(name: str, size: str) -> list[str]:
    entry = get_provider_entry(name)
    if entry is None:
        return [f"Unsupported image provider: {name}"]
    try:
        width_text, height_text = size.lower().split("x", 1)
        width = int(width_text)
        height = int(height_text)
    except (ValueError, AttributeError):
        return [f"Invalid render size: {size}"]
    max_width, max_height = entry.capabilities.max_resolution
    warnings: list[str] = []
    if width > max_width or height > max_height:
        warnings.append(f"Requested size {size} exceeds {entry.name} max resolution {max_width}x{max_height}.")
    config = provider_config(name)
    if not config["configured"]:
        warnings.append(f"{entry.display_name} is not configured.")
    return warnings


def estimate_image_cost(name: str, size: str, quality_mode: str) -> dict[str, Any]:
    normalized = normalize_provider_name(name)
    if normalized == "mock":
        return {"estimated_cost_usd": 0.0, "currency": "USD", "source": "mock_provider"}
    return {
        "estimated_cost_usd": None,
        "currency": "USD",
        "source": "not_available",
        "note": "Cost estimation is provider/model dependent and unavailable for this configuration.",
        "requested_size": size,
        "quality_mode": quality_mode,
    }
