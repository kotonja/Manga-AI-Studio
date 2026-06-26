from __future__ import annotations

from pathlib import PurePath

from manga_api.config import Settings, get_settings


class UploadValidationError(ValueError):
    """Raised when uploaded asset metadata violates production limits."""


def validate_upload_metadata(
    *,
    filename: str,
    content_type: str,
    size_bytes: int,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    normalized_content_type = content_type.lower().strip()
    if normalized_content_type not in settings.allowed_upload_content_types:
        allowed = ", ".join(sorted(settings.allowed_upload_content_types))
        raise UploadValidationError(f"Unsupported upload content type '{content_type}'. Allowed: {allowed}")
    if size_bytes <= 0:
        raise UploadValidationError("Uploaded asset size must be greater than zero")
    if size_bytes > settings.upload_max_bytes:
        raise UploadValidationError(f"Uploaded asset is too large. Max size is {settings.upload_max_bytes} bytes")
    validate_safe_filename(filename)


def validate_safe_filename(filename: str) -> None:
    path = PurePath(filename)
    if path.name != filename or filename in {".", ".."}:
        raise UploadValidationError("Uploaded filename must not contain path components")
    if any(char in filename for char in ["\x00", "/", "\\"]):
        raise UploadValidationError("Uploaded filename contains invalid characters")
