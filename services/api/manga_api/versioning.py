from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlmodel import SQLModel, Session, select

from manga_api.models import (
    Asset,
    Bubble,
    CharacterCard,
    CharacterCardVersion,
    ExportVersion,
    GenerationJob,
    LetteringVersion,
    LayoutVersion,
    Page,
    PageVersion,
    Panel,
    PanelRenderPrompt,
    PanelVersion,
    Project,
    ProjectExport,
    ProjectVersion,
    Render,
    RenderVersion,
    SFXElement,
    StoryBible,
    StoryBibleVersion,
    StyleBible,
    StyleBibleVersion,
    VersionRecordBase,
)


VERSION_MODELS = [
    ProjectVersion,
    PageVersion,
    PanelVersion,
    LayoutVersion,
    RenderVersion,
    LetteringVersion,
    StoryBibleVersion,
    StyleBibleVersion,
    CharacterCardVersion,
    ExportVersion,
]

VERSION_MODEL_BY_ENTITY = {
    "project": ProjectVersion,
    "page": PageVersion,
    "panel": PanelVersion,
    "layout": LayoutVersion,
    "render": RenderVersion,
    "lettering": LetteringVersion,
    "story_bible": StoryBibleVersion,
    "style_bible": StyleBibleVersion,
    "character_card": CharacterCardVersion,
    "export": ExportVersion,
}

ROW_MODEL_BY_ENTITY = {
    "project": Project,
    "page": Page,
    "panel": Panel,
    "story_bible": StoryBible,
    "style_bible": StyleBible,
    "character_card": CharacterCard,
    "export": ProjectExport,
}


class VersioningService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_snapshot(
        self,
        entity: Any,
        *,
        entity_type: str | None = None,
        label: str = "",
        created_by: str = "system",
        reason: str = "",
        is_checkpoint: bool = False,
        asset_ids: list[str] | None = None,
    ) -> VersionRecordBase:
        resolved_type = entity_type or entity_type_for(entity)
        version_model = VERSION_MODEL_BY_ENTITY[resolved_type]
        snapshot, entity_id, project_id, inferred_assets = self._snapshot_payload(entity, resolved_type)
        resolved_assets = [*inferred_assets, *(asset_ids or [])]
        parent = self._latest_version(version_model, resolved_type, entity_id)
        version = version_model(
            project_id=project_id,
            parent_id=parent.id if parent is not None else None,
            entity_type=resolved_type,
            entity_id=entity_id,
            snapshot_json=snapshot,
            asset_ids=dedupe_strings(resolved_assets),
            label=label,
            created_by=created_by,
            reason=reason,
            is_checkpoint=is_checkpoint,
        )
        self.session.add(version)
        self.session.flush()
        return version

    def create_checkpoint(
        self,
        project_id: uuid.UUID | str,
        *,
        label: str,
        created_by: str = "system",
        reason: str = "manual_checkpoint",
    ) -> list[VersionRecordBase]:
        project = self._require(Project, project_id, "Project not found")
        versions: list[VersionRecordBase] = [
            self.create_snapshot(project, label=label, created_by=created_by, reason=reason, is_checkpoint=True)
        ]
        story_bibles = self.session.exec(
            select(StoryBible)
            .where(StoryBible.project_id == project.id)
            .order_by(StoryBible.created_at.desc())
        ).all()
        versions.extend(
            self.create_snapshot(story, label=label, created_by=created_by, reason=reason, is_checkpoint=True)
            for story in story_bibles
        )
        style_bibles = self.session.exec(
            select(StyleBible)
            .where(StyleBible.project_id == project.id)
            .order_by(StyleBible.created_at.desc())
        ).all()
        versions.extend(
            self.create_snapshot(style, label=label, created_by=created_by, reason=reason, is_checkpoint=True)
            for style in style_bibles
        )
        characters = self.session.exec(
            select(CharacterCard)
            .where(CharacterCard.project_id == project.id)
            .order_by(CharacterCard.name.asc(), CharacterCard.created_at.asc())
        ).all()
        versions.extend(
            self.create_snapshot(character, label=label, created_by=created_by, reason=reason, is_checkpoint=True)
            for character in characters
        )
        pages = self.session.exec(
            select(Page)
            .where(Page.project_id == project.id)
            .order_by(Page.page_number.asc(), Page.created_at.asc())
        ).all()
        for page in pages:
            versions.append(self.create_snapshot(page, label=label, created_by=created_by, reason=reason, is_checkpoint=True))
            versions.append(self.create_snapshot(page, entity_type="layout", label=label, created_by=created_by, reason=reason, is_checkpoint=True))
            panels = self.session.exec(
                select(Panel)
                .where(Panel.page_id == page.id)
                .order_by(Panel.reading_order.asc(), Panel.created_at.asc())
            ).all()
            versions.extend(
                self.create_snapshot(panel, label=label, created_by=created_by, reason=reason, is_checkpoint=True)
                for panel in panels
            )
            versions.append(self.create_snapshot(page, entity_type="lettering", label=label, created_by=created_by, reason=reason, is_checkpoint=True))

        self.session.commit()
        return versions

    def list_project_versions(self, project_id: uuid.UUID | str) -> list[VersionRecordBase]:
        parsed_project_id = uuid.UUID(str(project_id))
        versions: list[VersionRecordBase] = []
        for model in VERSION_MODELS:
            versions.extend(
                self.session.exec(
                    select(model)
                    .where(model.project_id == parsed_project_id)
                    .order_by(model.created_at.desc(), model.id.desc())
                ).all()
            )
        return sorted(versions, key=lambda version: version.created_at, reverse=True)

    def restore_snapshot(self, version_id: uuid.UUID | str) -> VersionRecordBase:
        version = self.get_version(version_id)
        if version.entity_type == "layout":
            self._restore_layout(version)
        elif version.entity_type == "lettering":
            self._restore_lettering(version)
        elif version.entity_type == "render":
            self._restore_render(version)
        else:
            self._restore_simple_entity(version)
        self.session.commit()
        return version

    def diff_versions(self, version_a: uuid.UUID | str, version_b: uuid.UUID | str) -> dict[str, Any]:
        first = self.get_version(version_a)
        second = self.get_version(version_b)
        first_flat = flatten_json(first.snapshot_json)
        second_flat = flatten_json(second.snapshot_json)
        first_keys = set(first_flat)
        second_keys = set(second_flat)
        changed = {
            key: {"from": first_flat[key], "to": second_flat[key]}
            for key in sorted(first_keys & second_keys)
            if first_flat[key] != second_flat[key]
        }
        return {
            "version_a": version_to_dict(first),
            "version_b": version_to_dict(second),
            "added": {key: second_flat[key] for key in sorted(second_keys - first_keys)},
            "removed": {key: first_flat[key] for key in sorted(first_keys - second_keys)},
            "changed": changed,
        }

    def get_version(self, version_id: uuid.UUID | str) -> VersionRecordBase:
        parsed_id = uuid.UUID(str(version_id))
        for model in VERSION_MODELS:
            version = self.session.get(model, parsed_id)
            if version is not None:
                return version
        raise ValueError("Version not found")

    def _snapshot_payload(self, entity: Any, entity_type: str) -> tuple[dict[str, Any], uuid.UUID, uuid.UUID | None, list[str]]:
        if entity_type == "layout":
            page = self._page_from_entity(entity)
            return self._layout_snapshot(page), page.id, page.project_id, []
        if entity_type == "lettering":
            page = self._page_from_entity(entity)
            return self._lettering_snapshot(page), page.id, page.project_id, []
        if entity_type == "render":
            render = self._render_from_entity(entity)
            return self._render_snapshot(render)
        if entity_type == "export":
            export = self._export_from_entity(entity)
            return {"export": row_snapshot(export)}, export.id, export.project_id, [str(export.file_asset_id)] if export.file_asset_id else []
        row = entity
        snapshot = {entity_type: row_snapshot(row)}
        return snapshot, row.id, project_id_for(self.session, row), asset_ids_for(row)

    def _layout_snapshot(self, page: Page) -> dict[str, Any]:
        panels = self.session.exec(
            select(Panel)
            .where(Panel.page_id == page.id)
            .order_by(Panel.reading_order.asc(), Panel.created_at.asc())
        ).all()
        return {
            "page": row_snapshot(page),
            "panels": [row_snapshot(panel) for panel in panels],
        }

    def _lettering_snapshot(self, page: Page) -> dict[str, Any]:
        panels = self.session.exec(
            select(Panel)
            .where(Panel.page_id == page.id)
            .order_by(Panel.reading_order.asc(), Panel.created_at.asc())
        ).all()
        panel_ids = [panel.id for panel in panels]
        bubbles = []
        if panel_ids:
            bubbles = self.session.exec(
                select(Bubble)
                .where(Bubble.panel_id.in_(panel_ids))
                .order_by(Bubble.created_at.asc())
            ).all()
        sfx = self.session.exec(
            select(SFXElement)
            .where(SFXElement.page_id == page.id)
            .order_by(SFXElement.created_at.asc())
        ).all()
        return {
            "page": row_snapshot(page),
            "bubbles": [row_snapshot(bubble) for bubble in bubbles],
            "sfx": [row_snapshot(element) for element in sfx],
        }

    def _render_snapshot(self, render: Render) -> tuple[dict[str, Any], uuid.UUID, uuid.UUID | None, list[str]]:
        job = self.session.get(GenerationJob, render.job_id)
        asset = self.session.get(Asset, render.asset_id) if render.asset_id is not None else None
        prompt = self._prompt_for_job(job) if job is not None else None
        project_id = job.project_id if job is not None else project_id_for(self.session, render)
        snapshot = {
            "render": row_snapshot(render),
            "job": row_snapshot(job) if job is not None else None,
            "prompt": row_snapshot(prompt) if prompt is not None else None,
            "asset": row_snapshot(asset) if asset is not None else None,
        }
        return snapshot, render.id, project_id, [str(render.asset_id)] if render.asset_id else []

    def _prompt_for_job(self, job: GenerationJob) -> PanelRenderPrompt | None:
        prompt_id = None
        if isinstance(job.output_payload, dict):
            prompt_id = job.output_payload.get("panel_render_prompt_id")
        if prompt_id is None and isinstance(job.input_payload, dict):
            prompt_id = job.input_payload.get("panel_render_prompt_id")
            options = job.input_payload.get("options")
            if prompt_id is None and isinstance(options, dict):
                prompt_id = options.get("panel_render_prompt_id")
        if prompt_id is None:
            return None
        return self.session.get(PanelRenderPrompt, uuid.UUID(str(prompt_id)))

    def _restore_layout(self, version: VersionRecordBase) -> None:
        page_data = version.snapshot_json.get("page") or {}
        page = self._require(Page, version.entity_id, "Page not found")
        apply_fields(page, page_data, {"id", "project_id", "created_at", "updated_at"})
        touch(page)
        self.session.add(page)
        for panel_data in version.snapshot_json.get("panels", []):
            panel_id = uuid.UUID(str(panel_data["id"]))
            panel = self.session.get(Panel, panel_id)
            if panel is None:
                panel = Panel(page_id=page.id)
            apply_fields(panel, panel_data, {"created_at", "updated_at"})
            panel.page_id = page.id
            touch(panel)
            self.session.add(panel)

    def _restore_lettering(self, version: VersionRecordBase) -> None:
        page = self._require(Page, version.entity_id, "Page not found")
        for bubble_data in version.snapshot_json.get("bubbles", []):
            bubble_id = uuid.UUID(str(bubble_data["id"]))
            bubble = self.session.get(Bubble, bubble_id)
            if bubble is None:
                bubble = Bubble(panel_id=uuid.UUID(str(bubble_data["panel_id"])), text=str(bubble_data.get("text", "")) or " ")
            apply_fields(bubble, bubble_data, {"created_at", "updated_at"})
            touch(bubble)
            self.session.add(bubble)
        for sfx_data in version.snapshot_json.get("sfx", []):
            sfx_id = uuid.UUID(str(sfx_data["id"]))
            sfx = self.session.get(SFXElement, sfx_id)
            if sfx is None:
                sfx = SFXElement(page_id=page.id, text=str(sfx_data.get("text", "SFX")) or "SFX")
            apply_fields(sfx, sfx_data, {"created_at", "updated_at"})
            sfx.page_id = page.id
            touch(sfx)
            self.session.add(sfx)

    def _restore_render(self, version: VersionRecordBase) -> None:
        render_data = version.snapshot_json.get("render") or {}
        render = self.session.get(Render, version.entity_id)
        if render is None:
            return
        apply_fields(render, render_data, {"id", "job_id", "panel_id", "created_at", "updated_at"})
        touch(render)
        self.session.add(render)
        asset_data = version.snapshot_json.get("asset") or {}
        if asset_data.get("id"):
            asset = self.session.get(Asset, uuid.UUID(str(asset_data["id"])))
            if asset is not None:
                apply_fields(asset, asset_data, {"id", "project_id", "created_at", "updated_at"})
                touch(asset)
                self.session.add(asset)

    def _restore_simple_entity(self, version: VersionRecordBase) -> None:
        model = ROW_MODEL_BY_ENTITY.get(version.entity_type)
        if model is None:
            return
        row = self.session.get(model, version.entity_id)
        if row is None:
            raise ValueError(f"{version.entity_type} not found")
        snapshot = version.snapshot_json.get(version.entity_type) or {}
        apply_fields(row, snapshot, {"id", "project_id", "created_at", "updated_at"})
        touch(row)
        self.session.add(row)

    def _latest_version(self, model: type[VersionRecordBase], entity_type: str, entity_id: uuid.UUID) -> VersionRecordBase | None:
        return self.session.exec(
            select(model)
            .where(model.entity_type == entity_type, model.entity_id == entity_id)
            .order_by(model.created_at.desc(), model.id.desc())
        ).first()

    def _page_from_entity(self, entity: Any) -> Page:
        if isinstance(entity, Page):
            return entity
        return self._require(Page, entity, "Page not found")

    def _render_from_entity(self, entity: Any) -> Render:
        if isinstance(entity, Render):
            return entity
        return self._require(Render, entity, "Render not found")

    def _export_from_entity(self, entity: Any) -> ProjectExport:
        if isinstance(entity, ProjectExport):
            return entity
        return self._require(ProjectExport, entity, "Export not found")

    def _require(self, model: type[SQLModel], entity_id: uuid.UUID | str, message: str) -> Any:
        row = self.session.get(model, uuid.UUID(str(entity_id)))
        if row is None:
            raise ValueError(message)
        return row


def entity_type_for(entity: Any) -> str:
    if isinstance(entity, Project):
        return "project"
    if isinstance(entity, Page):
        return "page"
    if isinstance(entity, Panel):
        return "panel"
    if isinstance(entity, Render):
        return "render"
    if isinstance(entity, StoryBible):
        return "story_bible"
    if isinstance(entity, StyleBible):
        return "style_bible"
    if isinstance(entity, CharacterCard):
        return "character_card"
    if isinstance(entity, ProjectExport):
        return "export"
    raise ValueError(f"Unsupported versioned entity: {type(entity).__name__}")


def project_id_for(session: Session, row: Any) -> uuid.UUID | None:
    if isinstance(row, Project):
        return row.id
    if hasattr(row, "project_id"):
        return row.project_id
    if isinstance(row, Panel):
        page = session.get(Page, row.page_id)
        return page.project_id if page is not None else None
    if isinstance(row, Render):
        panel = session.get(Panel, row.panel_id)
        if panel is None:
            return None
        page = session.get(Page, panel.page_id)
        return page.project_id if page is not None else None
    return None


def asset_ids_for(row: Any) -> list[str]:
    if isinstance(row, Render) and row.asset_id is not None:
        return [str(row.asset_id)]
    if isinstance(row, ProjectExport) and row.file_asset_id is not None:
        return [str(row.file_asset_id)]
    return []


def row_snapshot(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if hasattr(row, "__table__"):
        data = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    elif hasattr(row, "model_dump"):
        data = row.model_dump()
    else:
        data = dict(row)
    return normalize_json(data)


def apply_fields(row: Any, snapshot: dict[str, Any], excluded: set[str]) -> None:
    for field, value in snapshot.items():
        if field in excluded or not hasattr(row, field):
            continue
        setattr(row, field, parse_value_for_field(row, field, value))


def parse_value_for_field(row: Any, field: str, value: Any) -> Any:
    if value is None:
        return None
    current = getattr(row, field, None)
    if isinstance(current, uuid.UUID):
        return uuid.UUID(str(value))
    if field == "id" or field.endswith("_id"):
        try:
            return uuid.UUID(str(value))
        except (TypeError, ValueError):
            return value
    return value


def normalize_json(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): normalize_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_json(item) for item in value]
    return value


def touch(row: Any) -> None:
    if hasattr(row, "updated_at"):
        row.updated_at = datetime.now(timezone.utc)


def flatten_json(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        flattened: dict[str, Any] = {}
        for key, item in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(flatten_json(item, child_prefix))
        return flattened
    if isinstance(value, list):
        flattened: dict[str, Any] = {}
        for index, item in enumerate(value):
            child_prefix = f"{prefix}[{index}]"
            flattened.update(flatten_json(item, child_prefix))
        return flattened
    return {prefix: value}


def version_to_dict(version: VersionRecordBase) -> dict[str, Any]:
    return {
        "id": str(version.id),
        "project_id": str(version.project_id) if version.project_id else None,
        "parent_id": str(version.parent_id) if version.parent_id else None,
        "entity_type": version.entity_type,
        "entity_id": str(version.entity_id),
        "asset_ids": version.asset_ids,
        "label": version.label,
        "created_by": version.created_by,
        "created_at": version.created_at.isoformat(),
        "reason": version.reason,
        "is_checkpoint": version.is_checkpoint,
    }


def dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result
