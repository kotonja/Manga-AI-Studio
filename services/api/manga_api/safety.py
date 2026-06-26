from __future__ import annotations

from typing import Any, Protocol

from manga_api.config import get_settings
from manga_api.schemas import SafetyCheckResult, SafetyIssueRead
from manga_api.style_guard import clean_risky_text, evaluate_style_safety


class SafetyProvider(Protocol):
    name: str

    def check_text_prompts(self, text: str, metadata: dict[str, Any] | None = None) -> SafetyCheckResult:
        """Check prompt text for rights, style, and IP risk."""

    def check_uploaded_image_metadata(self, metadata: dict[str, Any]) -> SafetyCheckResult:
        """Check uploaded image metadata before it enters the project."""

    def check_generated_output_metadata(self, metadata: dict[str, Any]) -> SafetyCheckResult:
        """Check generated output metadata before export or approval."""


class MockSafetyProvider:
    name = "mock"

    def check_text_prompts(self, text: str, metadata: dict[str, Any] | None = None) -> SafetyCheckResult:
        payload = {"text": text, **(metadata or {})}
        style_result = evaluate_style_safety(payload)
        issues = [
            SafetyIssueRead(
                severity=issue.severity,
                code=issue.code,
                message=issue.message,
                field=issue.field,
                matched_text=issue.matched_text,
            )
            for issue in style_result.issues
        ]
        suggested_text = clean_risky_text(text) if text else None
        return SafetyCheckResult(
            allowed=style_result.allowed,
            severity=style_result.severity,
            issues=issues,
            suggested_text=suggested_text,
            suggested_metadata=style_result.suggested_style,
        )

    def check_uploaded_image_metadata(self, metadata: dict[str, Any]) -> SafetyCheckResult:
        return self.check_text_prompts(metadata_text(metadata), metadata)

    def check_generated_output_metadata(self, metadata: dict[str, Any]) -> SafetyCheckResult:
        return self.check_text_prompts(metadata_text(metadata), metadata)


class OpenAISafetyProvider:
    name = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.fallback = MockSafetyProvider()

    def check_text_prompts(self, text: str, metadata: dict[str, Any] | None = None) -> SafetyCheckResult:
        if not self.api_key:
            return self.fallback.check_text_prompts(text, metadata)
        # Future hook: call OpenAI moderation/structured critique here.
        return self.fallback.check_text_prompts(text, metadata)

    def check_uploaded_image_metadata(self, metadata: dict[str, Any]) -> SafetyCheckResult:
        if not self.api_key:
            return self.fallback.check_uploaded_image_metadata(metadata)
        return self.fallback.check_uploaded_image_metadata(metadata)

    def check_generated_output_metadata(self, metadata: dict[str, Any]) -> SafetyCheckResult:
        if not self.api_key:
            return self.fallback.check_generated_output_metadata(metadata)
        return self.fallback.check_generated_output_metadata(metadata)


def get_safety_provider(provider_name: str = "mock") -> SafetyProvider:
    if provider_name.lower().strip() == "openai":
        return OpenAISafetyProvider()
    return MockSafetyProvider()


def metadata_text(metadata: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)):
            parts.append(f"{key}: {value}")
        elif isinstance(value, list):
            parts.append(f"{key}: {' '.join(str(item) for item in value)}")
        elif isinstance(value, dict):
            parts.append(f"{key}: {metadata_text(value)}")
    return "\n".join(parts)
