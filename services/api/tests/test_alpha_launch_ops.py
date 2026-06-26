import os
import subprocess
import sys
import uuid
from pathlib import Path

from manga_api.config import get_settings
from manga_api.routes import alpha as alpha_routes


REPO_ROOT = Path(__file__).resolve().parents[3]
ADMIN = {"X-Alpha-Token": "admin-token"}
USER_A = {"X-Alpha-Token": "token-a"}


def enable_alpha(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "alpha")
    monkeypatch.setenv("ALPHA_AUTH_ENABLED", "true")
    monkeypatch.setenv("ALPHA_SESSION_SECRET", "a" * 40)
    monkeypatch.setenv("ALPHA_USER_TOKENS", "user-a:token-a,user-b:token-b")
    monkeypatch.setenv("ALPHA_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("ENABLE_DEV_ADMIN", "false")
    monkeypatch.setenv("NEXT_PUBLIC_ENABLE_DEV_ADMIN", "false")
    monkeypatch.setenv("S3_PUBLIC_READ_ENABLED", "false")
    monkeypatch.setenv("ASSET_DOWNLOAD_MODE", "proxy")
    get_settings.cache_clear()


def test_alpha_readiness_endpoint_requires_admin_and_reports_checks(client, monkeypatch) -> None:
    enable_alpha(monkeypatch)

    class FakeRedis:
        def ping(self) -> bool:
            return True

    class FakeInspect:
        def ping(self):
            return {"worker@test": {"ok": "pong"}}

    class FakeControl:
        def inspect(self, timeout=1):
            return FakeInspect()

    class FakeCelery:
        control = FakeControl()

    monkeypatch.setattr(alpha_routes.Redis, "from_url", lambda *args, **kwargs: FakeRedis())
    monkeypatch.setattr(alpha_routes, "make_celery_client", lambda: FakeCelery())

    assert client.get("/alpha/readiness", headers=USER_A).status_code == 401
    response = client.get("/alpha/readiness", headers=ADMIN)
    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["auth enabled"]["status"] == "pass"
    assert checks["tester identity"]["status"] == "pass"
    assert checks["mock provider"]["status"] == "pass"
    assert checks["real providers"]["status"] == "warn"


def test_feedback_admin_triage_is_protected(client, monkeypatch) -> None:
    enable_alpha(monkeypatch)
    project = client.post("/projects", headers=USER_A, json={"name": "Feedback Triage", "description": "Alpha"}).json()
    feedback = client.post(
        "/feedback",
        headers=USER_A,
        json={
            "project_id": project["id"],
            "category": "bug",
            "severity": "high",
            "title": "Panel looked confusing",
            "description": "The page layout was hard to follow.",
            "context": {"page_id": "page-1"},
        },
    )
    assert feedback.status_code == 201
    feedback_id = feedback.json()["id"]

    assert client.get("/admin/feedback", headers=USER_A).status_code == 401
    listed = client.get("/admin/feedback", headers=ADMIN)
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == feedback_id

    updated = client.patch(
        f"/admin/feedback/{feedback_id}",
        headers=ADMIN,
        json={"status": "triaged", "severity": "blocker", "internal_notes": "Reproduce on page studio."},
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["status"] == "triaged"
    assert payload["severity"] == "blocker"
    assert payload["internal_notes"] == "Reproduce on page studio."

    assert client.patch(f"/admin/feedback/{uuid.uuid4()}", headers=ADMIN, json={"status": "fixed"}).status_code == 404


def test_create_alpha_token_format_and_write(tmp_path) -> None:
    script = REPO_ROOT / "scripts" / "create-alpha-token.py"
    result = subprocess.run(
        [sys.executable, str(script), "--user", "tester-a"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )
    first_line = result.stdout.splitlines()[0]
    user_id, token = first_line.split(":", 1)
    assert user_id == "tester-a"
    assert len(token) >= 32
    assert "ALPHA_USER_TOKENS=tester-a:" in result.stdout

    subprocess.run(
        [sys.executable, str(script), "--user", "tester-b", "--write"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )
    generated = (tmp_path / ".alpha-tokens.generated").read_text(encoding="utf-8")
    assert generated.startswith("tester-b:")


def test_check_alpha_env_passes_and_fails(tmp_path) -> None:
    script = REPO_ROOT / "scripts" / "check-alpha-env.py"
    valid_env = tmp_path / "valid.env"
    valid_env.write_text(
        "\n".join(
            [
                "APP_ENV=alpha",
                "ALPHA_AUTH_ENABLED=true",
                f"ALPHA_SESSION_SECRET={'a' * 40}",
                f"ALPHA_USER_TOKENS=tester-a:{'b' * 40}",
                f"ALPHA_ADMIN_TOKEN={'c' * 40}",
                "ENABLE_DEV_ADMIN=false",
                "NEXT_PUBLIC_ENABLE_DEV_ADMIN=false",
                "TRUST_EXTERNAL_AUTH_HEADERS=false",
                "S3_PUBLIC_READ_ENABLED=false",
                "ASSET_DOWNLOAD_MODE=proxy",
                "DATABASE_URL=postgresql+psycopg://manga:manga@db:5432/manga_ai",
                "REDIS_URL=redis://redis:6379/0",
                "S3_ENDPOINT_URL=http://minio:9000",
                "S3_ACCESS_KEY_ID=alphaaccesskey",
                "S3_SECRET_ACCESS_KEY=alphastoragevalue1234567890",
                "S3_BUCKET_NAME=manga-ai-alpha",
            ]
        ),
        encoding="utf-8",
    )
    env = {
        "PATH": os.environ.get("PATH", ""),
        "SystemRoot": os.environ.get("SystemRoot", ""),
        "PYTHONIOENCODING": "utf-8",
    }
    passing = subprocess.run(
        [sys.executable, str(script), "--env-file", str(valid_env)],
        text=True,
        capture_output=True,
        env=env,
    )
    assert passing.returncode == 0
    assert "Alpha environment check passed." in passing.stdout

    invalid_env = tmp_path / "invalid.env"
    invalid_env.write_text(
        "\n".join(
            [
                "APP_ENV=alpha",
                "ALPHA_AUTH_ENABLED=true",
                "ALPHA_SESSION_SECRET=replace-with-long-random-secret",
                f"ALPHA_USER_TOKENS=tester-a:{'b' * 40}",
                f"ALPHA_ADMIN_TOKEN={'c' * 40}",
                "ENABLE_DEV_ADMIN=true",
                "S3_PUBLIC_READ_ENABLED=true",
                "ASSET_DOWNLOAD_MODE=public_url",
            ]
        ),
        encoding="utf-8",
    )
    failing = subprocess.run(
        [sys.executable, str(script), "--env-file", str(invalid_env)],
        text=True,
        capture_output=True,
        env=env,
    )
    assert failing.returncode != 0
    assert "ENABLE_DEV_ADMIN must be false" in failing.stdout
    assert "S3_PUBLIC_READ_ENABLED must be false" in failing.stdout
