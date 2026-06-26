from __future__ import annotations

from manga_api.uploads import UploadValidationError, validate_upload_metadata


def test_upload_metadata_validation_accepts_safe_image() -> None:
    validate_upload_metadata(filename="reference.png", content_type="image/png", size_bytes=1024)


def test_upload_metadata_validation_rejects_bad_type() -> None:
    try:
        validate_upload_metadata(filename="reference.exe", content_type="application/x-msdownload", size_bytes=1024)
    except UploadValidationError as exc:
        assert "Unsupported upload content type" in str(exc)
    else:
        raise AssertionError("Expected upload validation to reject executable content type")


def test_upload_metadata_validation_rejects_path_filename() -> None:
    try:
        validate_upload_metadata(filename="../reference.png", content_type="image/png", size_bytes=1024)
    except UploadValidationError as exc:
        assert "path components" in str(exc) or "invalid characters" in str(exc)
    else:
        raise AssertionError("Expected upload validation to reject path-like filename")


def test_request_size_limit_returns_413(client) -> None:
    response = client.post(
        "/projects",
        data="{}",
        headers={"content-type": "application/json", "content-length": str(30 * 1024 * 1024)},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "Request body is too large"
