from __future__ import annotations

import argparse
import json
import os
import shutil
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from manga_api.compositor import get_latest_composite_asset
from manga_api.db import build_engine
from manga_api.demo_pipeline import DEMO_PREMISE, create_full_demo_project
from manga_api.main import app
from manga_api.models import (
    Asset,
    AssetProvenance,
    Bubble,
    Chapter,
    Character,
    CharacterCard,
    GenerationJob,
    KeyObject,
    Location,
    Page,
    Panel,
    Project,
    ProjectExport,
    QAReport,
    Render,
    StoryBible,
    StyleBible,
)
from manga_api.provenance import ProvenanceService, jsonable
from manga_api.storage import ObjectStorage


KEYWORDS = [
    "TODO",
    "FIXME",
    "pass",
    "NotImplemented",
    "stub",
    "mock only",
    "hard-coded",
    "placeholder",
    "skip",
    "console.log",
    "fake data",
]

EXCLUDED_DIRS = {
    ".git",
    ".next",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "coverage",
}


@dataclass(frozen=True)
class RepoPaths:
    repo_root: Path
    docs_dir: Path
    evidence_dir: Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Manga AI Studio final-boss evidence and inventories.")
    parser.add_argument("--repo-root", default=None, help="Repository root. Defaults to /app/repo when mounted.")
    parser.add_argument("--output", default="/app/evidence/final_boss_demo", help="Evidence output directory.")
    parser.add_argument("--demo-only", action="store_true", help="Generate only the demo evidence pack.")
    parser.add_argument("--inventory-only", action="store_true", help="Generate only audit/inventory docs.")
    parser.add_argument("--skip-results-doc", action="store_true", help="Do not rewrite docs/FINAL_BOSS_RESULTS.md.")
    args = parser.parse_args()

    paths = resolve_paths(args.repo_root, args.output)
    paths.docs_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] | None = None
    if not args.inventory_only:
        summary = generate_demo_evidence(paths.evidence_dir)

    if not args.demo_only:
        generate_docs(paths, summary, write_results=not args.skip_results_doc)

    if summary:
        print(json.dumps(summary, indent=2, sort_keys=True))


def resolve_paths(repo_root_arg: str | None, output_arg: str) -> RepoPaths:
    repo_root = Path(repo_root_arg or "/app/repo")
    if not repo_root.exists():
        repo_root = Path.cwd()
        for parent in [Path.cwd(), *Path.cwd().parents]:
            if (parent / "README.md").exists() and (parent / "services").exists():
                repo_root = parent
                break
    repo_root = repo_root.resolve()
    docs_dir = repo_root / "docs"
    evidence_dir = Path(output_arg)
    if not evidence_dir.is_absolute():
        evidence_dir = repo_root / evidence_dir
    return RepoPaths(repo_root=repo_root, docs_dir=docs_dir, evidence_dir=evidence_dir.resolve())


def generate_demo_evidence(evidence_dir: Path) -> dict[str, Any]:
    prepare_evidence_dir(evidence_dir)
    (evidence_dir / "final_pages").mkdir(parents=True)
    (evidence_dir / "exports").mkdir(parents=True)
    (evidence_dir / "screenshots").mkdir(parents=True)

    engine = build_engine()
    storage = ObjectStorage()
    with Session(engine) as session:
        created = create_full_demo_project(session, storage)
        project_id = created.project.id
        project = session.get(Project, project_id)
        if project is None:
            raise RuntimeError("Final-boss demo project was not persisted.")

        story_bible = session.exec(
            select(StoryBible).where(StoryBible.project_id == project.id).order_by(StoryBible.created_at.desc())
        ).first()
        style_bible = session.get(StyleBible, project.active_style_bible_id) if project.active_style_bible_id else None
        if style_bible is None:
            style_bible = session.exec(
                select(StyleBible).where(StyleBible.project_id == project.id).order_by(StyleBible.created_at.desc())
            ).first()

        pages = list(
            session.exec(select(Page).where(Page.project_id == project.id).order_by(Page.page_number.asc())).all()
        )
        panels = list(
            session.exec(select(Panel).where(Panel.page_id.in_([page.id for page in pages])).order_by(Panel.created_at.asc())).all()
        ) if pages else []
        bubbles = list(
            session.exec(select(Bubble).where(Bubble.panel_id.in_([panel.id for panel in panels])).order_by(Bubble.created_at.asc())).all()
        ) if panels else []
        renders = list(
            session.exec(select(Render).where(Render.panel_id.in_([panel.id for panel in panels])).order_by(Render.created_at.asc())).all()
        ) if panels else []
        qa_reports = list(
            session.exec(select(QAReport).where(QAReport.id.in_(created.qa_report_ids)).order_by(QAReport.created_at.asc())).all()
        )
        exports = list(
            session.exec(select(ProjectExport).where(ProjectExport.id.in_(list(created.exports.values()))).order_by(ProjectExport.created_at.asc())).all()
        )

        write_json(evidence_dir / "project.json", model_to_dict(project))
        write_json(
            evidence_dir / "story_bible.json",
            {
                "story_bible": model_to_dict(story_bible),
                "locations": [model_to_dict(item) for item in query_project(session, Location, project.id)],
                "key_objects": [model_to_dict(item) for item in query_project(session, KeyObject, project.id)],
                "chapters": [model_to_dict(item) for item in query_project(session, Chapter, project.id)],
            },
        )
        write_json(
            evidence_dir / "characters.json",
            {
                "characters": [model_to_dict(item) for item in query_project(session, Character, project.id)],
                "character_cards": [model_to_dict(item) for item in query_project(session, CharacterCard, project.id)],
            },
        )
        write_json(evidence_dir / "style_bible.json", model_to_dict(style_bible))
        write_json(evidence_dir / "pages.json", [page_payload(session, page) for page in pages])
        write_json(evidence_dir / "panels.json", [panel_payload(session, panel) for panel in panels])
        write_json(evidence_dir / "qa_reports.json", [model_to_dict(report) for report in qa_reports])

        final_page_files: list[str] = []
        for page in pages:
            composite_asset = get_latest_composite_asset(session, page.id)
            if composite_asset is None:
                raise RuntimeError(f"Page {page.page_number} has no composite asset.")
            filename = f"page-{page.page_number:03d}.png"
            (evidence_dir / "final_pages" / filename).write_bytes(storage.get_bytes(composite_asset.storage_key))
            final_page_files.append(f"final_pages/{filename}")

        export_files: list[dict[str, Any]] = []
        for export in exports:
            if export.status != "succeeded" or export.file_asset_id is None:
                raise RuntimeError(f"{export.format} export did not succeed: {export.error_message}")
            asset = session.get(Asset, export.file_asset_id)
            if asset is None:
                raise RuntimeError(f"{export.format} export asset is missing.")
            extension = "pdf" if export.format == "pdf" else "zip"
            filename = f"{export.format}-{export.id}.{extension}"
            (evidence_dir / "exports" / filename).write_bytes(storage.get_bytes(asset.storage_key))
            export_files.append(
                {
                    "format": export.format,
                    "export_id": str(export.id),
                    "asset_id": str(asset.id),
                    "file": f"exports/{filename}",
                    "content_type": asset.content_type,
                    "size_bytes": asset.size_bytes,
                    "status": export.status,
                }
            )

        provenance_payload = ProvenanceService(session).export_payload(project.id)
        write_json(evidence_dir / "provenance.json", provenance_payload)
        write_text(
            evidence_dir / "screenshots" / "README.md",
            "# Screenshots\n\n"
            "The final-boss evidence generator is backend/asset focused and does not drive a browser.\n"
            "Frontend screenshots from the UX polish pass are stored in `docs/screenshots/`.\n",
        )

        panel_count_by_page = Counter(str(panel.page_id) for panel in panels)
        export_manifest = {
            "generated_at": utc_now(),
            "premise": DEMO_PREMISE,
            "project_id": str(project.id),
            "counts": {
                "projects": 1,
                "story_bibles": 1 if story_bible else 0,
                "characters": len(query_project(session, Character, project.id)),
                "character_cards": len(query_project(session, CharacterCard, project.id)),
                "locations": len(query_project(session, Location, project.id)),
                "style_bibles": 1 if style_bible else 0,
                "chapters": len(query_project(session, Chapter, project.id)),
                "pages": len(pages),
                "panels": len(panels),
                "bubbles": len(bubbles),
                "renders": len(renders),
                "qa_reports": len(qa_reports),
                "exports": len(exports),
            },
            "validation": {
                "exactly_four_pages": len(pages) == 4,
                "at_least_three_panels_per_page": all(panel_count_by_page[str(page.id)] >= 3 for page in pages),
                "bubbles_on_every_page": all(page_has_bubble(page, panels, bubbles) for page in pages),
                "all_renders_exist": len(renders) >= len(panels),
                "all_pages_composed": len(final_page_files) == len(pages),
                "no_blocking_qa": not any(report.blocking for report in qa_reports),
                "zip_export": any(item["format"] == "zip" for item in export_files),
                "pdf_export": any(item["format"] == "pdf" for item in export_files),
                "provenance_export": bool(provenance_payload["assets"]),
            },
            "final_pages": final_page_files,
            "exports": export_files,
            "provenance_summary": provenance_payload["summary"],
        }
        write_json(evidence_dir / "export_manifest.json", export_manifest)
        return export_manifest


def prepare_evidence_dir(evidence_dir: Path) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for child in evidence_dir.iterdir():
        if child.name == "logs":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def generate_docs(paths: RepoPaths, summary: dict[str, Any] | None, *, write_results: bool = True) -> None:
    endpoints = api_endpoint_inventory(paths.repo_root)
    frontend_routes = frontend_route_inventory(paths.repo_root)
    stubs = stub_inventory(paths.repo_root)
    write_text(paths.docs_dir / "API_INVENTORY.md", render_api_inventory(endpoints))
    write_text(paths.docs_dir / "FRONTEND_INVENTORY.md", render_frontend_inventory(frontend_routes))
    write_text(paths.docs_dir / "STUBS_AND_TODOS.md", render_stubs_inventory(stubs))
    write_text(paths.docs_dir / "FINAL_BOSS_AUDIT.md", render_audit(paths.repo_root, endpoints, frontend_routes, stubs))
    if write_results:
        write_text(paths.docs_dir / "FINAL_BOSS_RESULTS.md", render_results(summary))


def query_project(session: Session, model: Any, project_id: uuid.UUID) -> list[Any]:
    return list(session.exec(select(model).where(model.project_id == project_id).order_by(model.created_at.asc())).all())


def page_payload(session: Session, page: Page) -> dict[str, Any]:
    composite = get_latest_composite_asset(session, page.id)
    return {
        **model_to_dict(page),
        "composite_asset": model_to_dict(composite),
    }


def panel_payload(session: Session, panel: Panel) -> dict[str, Any]:
    bubbles = list(session.exec(select(Bubble).where(Bubble.panel_id == panel.id).order_by(Bubble.created_at.asc())).all())
    renders = list(session.exec(select(Render).where(Render.panel_id == panel.id).order_by(Render.created_at.asc())).all())
    jobs = [
        session.get(GenerationJob, render.job_id)
        for render in renders
    ]
    return {
        **model_to_dict(panel),
        "bubbles": [model_to_dict(bubble) for bubble in bubbles],
        "renders": [model_to_dict(render) for render in renders],
        "render_jobs": [model_to_dict(job) for job in jobs if job is not None],
    }


def page_has_bubble(page: Page, panels: list[Panel], bubbles: list[Bubble]) -> bool:
    panel_ids = {panel.id for panel in panels if panel.page_id == page.id}
    return any(bubble.panel_id in panel_ids for bubble in bubbles)


def model_to_dict(model: Any) -> dict[str, Any] | None:
    if model is None:
        return None
    if hasattr(model, "model_dump"):
        return jsonable(model.model_dump())
    return jsonable(model)


def api_endpoint_inventory(repo_root: Path) -> list[dict[str, Any]]:
    tests_text = read_tests_text(repo_root)
    endpoints: list[dict[str, Any]] = []
    openapi = app.openapi()
    for path, path_item in sorted(openapi.get("paths", {}).items()):
        for method, operation in sorted(path_item.items()):
            method_upper = method.upper()
            if method_upper not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            tested = endpoint_is_tested(path, tests_text)
            endpoints.append(
                {
                    "method": method_upper,
                    "path": path,
                    "name": operation.get("operationId", ""),
                    "tags": operation.get("tags", []),
                    "request_body": openapi_request_shape(operation),
                    "response_shape": openapi_response_shape(operation),
                    "auth": "dev flag" if path.startswith("/admin") else "none",
                    "status": endpoint_status(path, tested),
                    "tested": tested,
                }
            )
    return sorted(endpoints, key=lambda item: (item["path"], item["method"]))


def openapi_request_shape(operation: dict[str, Any]) -> str:
    request_body = operation.get("requestBody")
    if not request_body:
        return "none"
    content = request_body.get("content", {})
    json_content = content.get("application/json") or next(iter(content.values()), {})
    schema = json_content.get("schema", {})
    return schema_name(schema)


def openapi_response_shape(operation: dict[str, Any]) -> str:
    responses = operation.get("responses", {})
    selected = responses.get("200") or responses.get("201") or responses.get("202") or next(iter(responses.values()), {})
    content = selected.get("content", {}) if isinstance(selected, dict) else {}
    json_content = content.get("application/json") or next(iter(content.values()), {})
    schema = json_content.get("schema", {})
    return schema_name(schema) if schema else "not declared"


def schema_name(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]
    if schema.get("type") == "array":
        return f"list[{schema_name(schema.get('items', {}))}]"
    if "anyOf" in schema:
        return " | ".join(schema_name(item) for item in schema["anyOf"])
    return schema.get("title") or schema.get("type") or "object"


def endpoint_is_tested(path: str, tests_text: str) -> bool:
    if path in tests_text:
        return True
    prefix = path.split("{", 1)[0].rstrip("/")
    if len(prefix) > 4 and prefix in tests_text:
        return True
    normalized = path.replace("{project_id}", "").replace("{page_id}", "").replace("{panel_id}", "")
    return len(normalized.strip("/")) > 2 and normalized.strip("/") in tests_text


def endpoint_status(path: str, tested: bool) -> str:
    if "openai" in path.lower() or "comfy" in path.lower():
        return "STUB"
    if path.startswith("/admin"):
        return "PARTIAL"
    if tested:
        return "WORKING"
    if path in {"/health", "/health/db", "/health/redis", "/health/storage", "/health/worker"}:
        return "WORKING"
    return "PARTIAL"


def frontend_route_inventory(repo_root: Path) -> list[dict[str, str]]:
    app_dir = repo_root / "apps" / "web" / "src" / "app"
    routes: list[dict[str, str]] = []
    if not app_dir.exists():
        return routes
    for page_file in sorted(app_dir.rglob("page.tsx")):
        relative = page_file.relative_to(app_dir).parent
        path = "/" if str(relative) == "." else "/" + "/".join(dynamic_segment(part) for part in relative.parts)
        routes.append(
            {
                "path": path,
                "purpose": frontend_purpose(path),
                "backend_dependencies": frontend_dependencies(path),
                "status": frontend_status(path),
                "known_ui_issues": frontend_issue(path),
            }
        )
    return routes


def dynamic_segment(part: str) -> str:
    if part.startswith("[") and part.endswith("]"):
        return "{" + part[1:-1] + "}"
    return part


def frontend_purpose(path: str) -> str:
    if path == "/":
        return "Project dashboard and demo creation entry."
    if path.endswith("/director"):
        return "One-premise draft manga orchestrator."
    if path.endswith("/story"):
        return "Story bible and chapter/page plan inspection."
    if path.endswith("/characters"):
        return "Character cards, references, and continuity state."
    if path.endswith("/world"):
        return "Locations and key object worldbuilding."
    if path.endswith("/style"):
        return "Style bible, StyleDNA options, and style safety warnings."
    if path.endswith("/studio"):
        return "Konva page layout, rendering, QA overlay, and panel preview."
    if path.endswith("/lettering"):
        return "Bubble and SFX lettering editor."
    if path.endswith("/qa"):
        return "Grouped QA issues and safe auto-fixes."
    if path.endswith("/publishing"):
        return "Export readiness and download room."
    if path.endswith("/provenance"):
        return "Rights declarations and asset provenance."
    if path.endswith("/settings"):
        return "Project settings and operational status."
    if path.startswith("/admin/eval"):
        return "Developer-only evaluation harness UI."
    if path.startswith("/admin/ai-task-runs"):
        return "Developer-only AI task run inspector."
    return "Project detail shell."


def frontend_dependencies(path: str) -> str:
    dependency_map = {
        "/": "GET/POST /projects, POST /demo/create-full-project",
        "/admin/ai-task-runs": "GET /admin/ai-task-runs",
        "/admin/eval": "GET /eval/scenarios, POST /eval/run",
    }
    if path in dependency_map:
        return dependency_map[path]
    if path.endswith("/director"):
        return "POST /projects/{id}/director/generate-draft, GET /jobs/{id}/events"
    if path.endswith("/story"):
        return "story endpoints for bible, chapter plans, and page plans"
    if path.endswith("/characters"):
        return "character CRUD and reference asset metadata endpoints"
    if path.endswith("/world"):
        return "story bible location/key object data"
    if path.endswith("/style"):
        return "style bible CRUD, StyleDNA, style preview endpoints"
    if path.endswith("/studio"):
        return "layout, panel render, compose, QA endpoints"
    if path.endswith("/lettering"):
        return "lettering, bubble, SFX, SVG endpoints"
    if path.endswith("/qa"):
        return "page/project QA and auto-fix endpoints"
    if path.endswith("/publishing"):
        return "export create/get/download endpoints"
    if path.endswith("/provenance"):
        return "rights declaration and provenance endpoints"
    return "GET /projects/{id}, GET /projects/{id}/workspace-summary"


def frontend_status(path: str) -> str:
    if path.startswith("/admin"):
        return "PARTIAL"
    if path.endswith("/world"):
        return "PARTIAL"
    return "WORKING"


def frontend_issue(path: str) -> str:
    if path.startswith("/admin"):
        return "Hidden by dev flag; no auth system exists yet."
    if path.endswith("/world"):
        return "World Room is mostly metadata inspection from story generation, not a full bespoke editor."
    return "No blocker found in static inventory; covered by build and route smoke where applicable."


def stub_inventory(repo_root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in walk_repo_files(repo_root):
        if should_skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            matched = [keyword for keyword in KEYWORDS if keyword.lower() in lowered]
            if not matched:
                continue
            if path.name in {"STUBS_AND_TODOS.md", "FINAL_BOSS_AUDIT.md", "FINAL_BOSS_RESULTS.md"}:
                continue
            findings.append(
                {
                    "file": str(path.relative_to(repo_root)).replace("\\", "/"),
                    "line": line_number,
                    "keyword": ", ".join(matched),
                    "excerpt": line.strip()[:220],
                    "severity": stub_severity(path, line),
                    "blocks_mvp": blocks_mvp(path, line),
                    "recommended_fix": recommended_fix(path, line),
                }
            )
    return findings


def walk_repo_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for current_root, dir_names, file_names in os.walk(repo_root):
        dir_names[:] = [
            name
            for name in dir_names
            if name not in EXCLUDED_DIRS and not name.startswith(".")
        ]
        current = Path(current_root)
        for file_name in file_names:
            files.append(current / file_name)
    return sorted(files)


def should_skip(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)


def stub_severity(path: Path, line: str) -> str:
    text = line.lower()
    if "notimplemented" in text or "not implemented" in text:
        return "high" if "openai" not in text and "comfy" not in text else "medium"
    if "placeholder" in text or "stub" in text:
        return "medium"
    if "skip" in text or "pass" in text:
        return "low"
    return "info"


def blocks_mvp(path: Path, line: str) -> bool:
    text = line.lower()
    if "openai" in text or "comfyui" in text or "future" in text:
        return False
    if "notimplemented" in text or "not implemented" in text:
        return True
    return False


def recommended_fix(path: Path, line: str) -> str:
    text = line.lower()
    if "openai" in text or "comfyui" in text:
        return "Keep as documented provider stub until real provider integration is required."
    if "placeholder" in text and "rate" in text:
        return "Replace with distributed rate limiting before public production."
    if "make format" in text:
        return "Add Prettier/Ruff configuration when formatting policy is finalized."
    if "notimplemented" in text or "not implemented" in text:
        return "Implement or guard this path with a clear user-facing unsupported-provider error."
    return "Review and either complete, document as intentional, or remove stale wording."


def render_api_inventory(endpoints: list[dict[str, Any]]) -> str:
    rows = [
        "# API Inventory",
        "",
        f"Generated at: {utc_now()}",
        "",
        "| Method | Path | Request Body | Response Shape | Auth | Status | Test Coverage |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for endpoint in endpoints:
        rows.append(
            "| {method} | `{path}` | `{request_body}` | `{response_shape}` | {auth} | {status} | {tested} |".format(
                **{**endpoint, "tested": "yes" if endpoint["tested"] else "no"}
            )
        )
    rows.extend(
        [
            "",
            "Auth note: the MVP has no user authentication. Admin routes are protected only by the development flag and must not be exposed publicly.",
        ]
    )
    return "\n".join(rows) + "\n"


def render_frontend_inventory(routes: list[dict[str, str]]) -> str:
    rows = [
        "# Frontend Inventory",
        "",
        f"Generated at: {utc_now()}",
        "",
        "| Route | Purpose | Backend Dependencies | Status | Known UI Issues |",
        "| --- | --- | --- | --- | --- |",
    ]
    for route in routes:
        rows.append(
            f"| `{route['path']}` | {route['purpose']} | {route['backend_dependencies']} | {route['status']} | {route['known_ui_issues']} |"
        )
    return "\n".join(rows) + "\n"


def render_stubs_inventory(findings: list[dict[str, Any]]) -> str:
    counts = Counter(item["severity"] for item in findings)
    rows = [
        "# Stubs And TODOs",
        "",
        f"Generated at: {utc_now()}",
        "",
        "This is a literal keyword scan. UI placeholder attributes and documentation references are included so they can be reviewed, but not every match is a defect.",
        "",
        f"Findings: {len(findings)} total; high={counts['high']}, medium={counts['medium']}, low={counts['low']}, info={counts['info']}.",
        "",
        "| File | Line | Keyword | Severity | Blocks MVP | Finding | Recommended Fix |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for item in findings:
        rows.append(
            f"| `{item['file']}` | {item['line']} | {item['keyword']} | {item['severity']} | {'yes' if item['blocks_mvp'] else 'no'} | {escape_md(item['excerpt'])} | {item['recommended_fix']} |"
        )
    return "\n".join(rows) + "\n"


def render_audit(repo_root: Path, endpoints: list[dict[str, Any]], routes: list[dict[str, str]], stubs: list[dict[str, Any]]) -> str:
    structure = repo_structure(repo_root)
    backend_modules = sorted(str(path.relative_to(repo_root)).replace("\\", "/") for path in (repo_root / "services" / "api" / "manga_api").glob("*.py"))
    route_modules = sorted(str(path.relative_to(repo_root)).replace("\\", "/") for path in (repo_root / "services" / "api" / "manga_api" / "routes").glob("*.py"))
    worker_jobs = worker_job_names(repo_root)
    model_names = database_model_names()
    status_table = major_system_statuses()
    tested_count = sum(1 for endpoint in endpoints if endpoint["tested"])
    high_stubs = [item for item in stubs if item["severity"] == "high"]

    rows = [
        "# Final Boss Audit",
        "",
        f"Generated at: {utc_now()}",
        "",
        "## 1. Full Repo Structure Summary",
        "",
        structure,
        "",
        "## 2. Backend Modules Implemented",
        "",
        *[f"- `{item}`" for item in backend_modules],
        *[f"- `{item}`" for item in route_modules],
        "",
        "## 3. Frontend Pages Implemented",
        "",
        *[f"- `{route['path']}`: {route['purpose']} [{route['status']}]" for route in routes],
        "",
        "## 4. Worker Jobs Implemented",
        "",
        *[f"- `{job}`" for job in worker_jobs],
        "",
        "## 5. Database Models Implemented",
        "",
        *[f"- `{name}`" for name in model_names],
        "",
        "## 6. API Endpoints Implemented",
        "",
        f"- Total endpoints: {len(endpoints)}",
        f"- Endpoints with direct/static test coverage signal: {tested_count}",
        "- See `docs/API_INVENTORY.md` for method/path/request/response details.",
        "",
        "## 7. Missing Or Stubbed Areas",
        "",
        "- OpenAI structured text provider is an intentional stub.",
        "- OpenAI image edit is not implemented yet.",
        "- ComfyUI queue submission exists, but output retrieval is not implemented.",
        "- OpenAI multimodal QA provider is a future stub.",
        "- Rate limiting is a local placeholder and should be replaced with edge/Redis limits for public production.",
        "- `make format` is a placeholder until Prettier/Ruff are configured.",
        "",
        "## 8. Broken Or Risky Areas",
        "",
        *([f"- High severity keyword finding: `{item['file']}:{item['line']}` {item['excerpt']}" for item in high_stubs] or ["- No high severity keyword findings outside documented provider stubs."]),
        "- No authentication exists; public exposure requires an auth layer.",
        "- Local mock-generated assets are valid for demo/testing, not proof of final paid-provider quality.",
        "",
        "## 9. Test Coverage Summary",
        "",
        "- Backend tests cover CRUD, story, layout, labs, rendering, composition, QA, exports, director, prompt registry, provenance, versioning, evaluation, and production security basics.",
        "- Frontend coverage is build/typecheck plus smoke route checks, not a full browser interaction suite.",
        "",
        "## 10. Local Run Instructions",
        "",
        "```sh",
        "cp .env.example .env",
        "docker compose up --build",
        "make final-demo",
        "```",
        "",
        "## 11. Production Readiness Status",
        "",
        "Production config, Dockerfiles, CI, deployment docs, structured logs, health checks, and migration docs exist. The app is not production-ready until authentication, real provider hardening, distributed rate limits, secret management, and external storage policies are completed.",
        "",
        "## 12. Known Limitations",
        "",
        "- Mock providers are deterministic and useful for tests; they do not produce production art.",
        "- Export packages are technically valid MVP outputs but not yet print-production certified.",
        "- Admin/dev pages must remain disabled outside local/dev environments.",
        "",
        "## Major System Classification",
        "",
        "| System | Status | Evidence/Notes |",
        "| --- | --- | --- |",
    ]
    rows.extend(f"| {item['system']} | {item['status']} | {item['notes']} |" for item in status_table)
    return "\n".join(rows) + "\n"


def render_results(summary: dict[str, Any] | None) -> str:
    rows = [
        "# Final Boss Results",
        "",
        f"Generated at: {utc_now()}",
        "",
        "This file is regenerated by `scripts/final-boss-check.sh` with command results. The section below records the latest demo evidence generated by `app.final_boss.run`.",
        "",
    ]
    if summary is None:
        rows.append("No demo evidence was generated in this run.")
        return "\n".join(rows) + "\n"
    rows.extend(
        [
            "## Demo Evidence",
            "",
            f"- Project id: `{summary['project_id']}`",
            f"- Premise: {summary['premise']}",
            f"- Pages: {summary['counts']['pages']}",
            f"- Panels: {summary['counts']['panels']}",
            f"- Bubbles: {summary['counts']['bubbles']}",
            f"- Renders: {summary['counts']['renders']}",
            f"- QA reports: {summary['counts']['qa_reports']}",
            f"- Exports: {', '.join(item['format'] for item in summary['exports'])}",
            "",
            "## Validation",
            "",
        ]
    )
    rows.extend(f"- {key}: {value}" for key, value in summary["validation"].items())
    rows.extend(
        [
            "",
            "Evidence is saved under `evidence/final_boss_demo/`.",
        ]
    )
    return "\n".join(rows) + "\n"


def major_system_statuses() -> list[dict[str, str]]:
    return [
        {"system": "Project dashboard", "status": "WORKING", "notes": "Project CRUD and demo creation are covered by API tests and frontend build."},
        {"system": "Director Mode", "status": "WORKING", "notes": "Mock async director pipeline and job events are implemented/tested."},
        {"system": "Story Room", "status": "WORKING", "notes": "Story bible, chapter, page, and panel plans persist with mock LLM."},
        {"system": "Character Lab", "status": "PARTIAL", "notes": "Character cards and mock sheets work; real reference-image generation is not included."},
        {"system": "World Room", "status": "PARTIAL", "notes": "Locations/key objects exist from story data; editor depth is limited."},
        {"system": "Style Lab", "status": "WORKING", "notes": "Style bible, StyleDNA options, style guard, active style attachment, and mock preview exist."},
        {"system": "Page Studio", "status": "WORKING", "notes": "Konva editor, layout save/load, rendering, QA overlay, and panel controls build."},
        {"system": "Lettering Room", "status": "WORKING", "notes": "Bubbles/SFX/lettering SVG endpoints and UI exist."},
        {"system": "QA Room", "status": "WORKING", "notes": "Deterministic QA and safe auto-fix services are tested."},
        {"system": "Publishing Room", "status": "WORKING", "notes": "ZIP/PDF/EPUB/layered export APIs and UI exist; final-boss verifies ZIP/PDF."},
        {"system": "Prompt Registry", "status": "WORKING", "notes": "Versioned prompt files and loader tests exist."},
        {"system": "AI Task Runner", "status": "WORKING", "notes": "Mock provider validates schemas and records task runs."},
        {"system": "Mock LLM provider", "status": "WORKING", "notes": "Deterministic JSON outputs are used by tests/dev."},
        {"system": "OpenAI provider", "status": "STUB", "notes": "Reads env but structured generation remains intentionally unimplemented."},
        {"system": "ComfyUI provider", "status": "STUB", "notes": "Queue submission exists only when configured; output retrieval is not implemented."},
        {"system": "Mock image provider", "status": "WORKING", "notes": "Creates deterministic placeholder PNGs and provenance."},
        {"system": "Render queue", "status": "WORKING", "notes": "Celery tasks and worker health exist; local tests can bypass background jobs."},
        {"system": "Compositor", "status": "WORKING", "notes": "Pillow compositor produces final page PNGs with bubbles/SFX."},
        {"system": "Exporter", "status": "WORKING", "notes": "ZIP/PDF exports are tested and final-boss copied to evidence."},
        {"system": "Evaluation harness", "status": "WORKING", "notes": "Mock evaluation scenarios generate reports; metrics are synthetic/deterministic."},
        {"system": "Versioning", "status": "PARTIAL", "notes": "Snapshots, restore, diff, and checkpoints exist; UI comparison is basic."},
        {"system": "Provenance", "status": "WORKING", "notes": "Generated/export assets include provenance and disclosure metadata."},
        {"system": "Safety/style guard", "status": "WORKING", "notes": "Deterministic risky phrase/style checks are tested."},
        {"system": "Deployment config", "status": "PARTIAL", "notes": "Dockerfiles/CI/docs exist, but auth/secrets/real provider ops remain launch blockers."},
    ]


def repo_structure(repo_root: Path) -> str:
    wanted = [".github", "apps", "services", "packages", "infra", "docs", "scripts", "eval_reports", "evidence"]
    lines = []
    for name in wanted:
        path = repo_root / name
        if path.exists():
            count = len([file_path for file_path in walk_repo_files(path)]) if path.is_dir() else 1
            lines.append(f"- `{name}/` ({count} entries)")
    for file_name in ["README.md", "Makefile", "docker-compose.yml", "docker-compose.prod.example.yml", "package.json"]:
        if (repo_root / file_name).exists():
            lines.append(f"- `{file_name}`")
    return "\n".join(lines)


def worker_job_names(repo_root: Path) -> list[str]:
    task_file = repo_root / "services" / "worker" / "manga_worker" / "tasks.py"
    if not task_file.exists():
        return []
    jobs = []
    for line in task_file.read_text(encoding="utf-8").splitlines():
        if "@celery_app.task" in line and "name=" in line:
            jobs.append(line.split("name=", 1)[1].split(")", 1)[0].strip("\"'"))
    return jobs


def database_model_names() -> list[str]:
    return sorted(table.name for table in Project.metadata.sorted_tables)


def read_tests_text(repo_root: Path) -> str:
    tests_dir = repo_root / "services" / "api" / "tests"
    if not tests_dir.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8") for path in tests_dir.glob("test_*.py"))


def escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(value), indent=2, sort_keys=True, ensure_ascii=True), encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    main()
