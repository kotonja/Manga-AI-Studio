from __future__ import annotations

import json
import logging
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Protocol

from PIL import Image
from sqlmodel import Session, select

from manga_api.compositor import get_latest_composite_asset
from manga_api.lettering import lettering_svg_for_page
from manga_api.models import Asset, Bubble, GenerationJob, Page, Panel, Project, ProjectExport, QAReport, Render, SFXElement
from manga_api.publishing import get_export_preset, get_project_publishing_metadata
from manga_api.provenance import ProvenanceService
from manga_api.qa import latest_qa_report
from manga_api.versioning import VersioningService

EXPORT_FORMATS = {"zip", "pdf", "epub", "layered", "png_sequence", "webtoon", "archive"}
logger = logging.getLogger("manga_api.export")


class ExportError(RuntimeError):
    """Raised for expected export validation failures."""


class ExportStorage(Protocol):
    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        """Persist bytes to object storage."""

    def get_bytes(self, key: str) -> bytes:
        """Read bytes from object storage."""

    def public_url(self, key: str) -> str:
        """Return a browser-accessible URL for a stored object."""


@dataclass(frozen=True)
class PageExportData:
    page: Page
    composite_asset: Asset
    composite_bytes: bytes
    panels: list[Panel]
    bubbles_by_panel: dict[uuid.UUID, list[Bubble]]
    sfx_elements: list[SFXElement]
    renders_by_panel: dict[uuid.UUID, Render]


class ProjectExporter:
    def __init__(self, session: Session, storage: ExportStorage) -> None:
        self.session = session
        self.storage = storage

    def export_project(
        self,
        project_id: uuid.UUID | str,
        export_format: str,
        *,
        force: bool = False,
        options: dict[str, Any] | None = None,
    ) -> ProjectExport:
        parsed_project_id = uuid.UUID(str(project_id))
        project = self.session.get(Project, parsed_project_id)
        if project is None:
            raise ExportError("Project not found")

        normalized_format = normalize_export_format(export_format)
        options = options or {}
        export = ProjectExport(
            project_id=project.id,
            format=normalized_format,
            status="running",
            options={**options, "force": force},
        )
        self.session.add(export)
        self.session.commit()
        self.session.refresh(export)
        logger.info(
            "export job started",
            extra={
                "job_id": str(export.id),
                "project_id": str(project.id),
            },
        )

        try:
            pages = self.session.exec(
                select(Page)
                .where(Page.project_id == project.id)
                .order_by(Page.page_number.asc(), Page.created_at.asc())
            ).all()
            if not pages:
                raise ExportError("Project has no pages to export")
            self._assert_qa_allows_export(pages, force)
            page_data = [self._load_page_export_data(page) for page in pages]
            metadata = self._project_metadata(project, page_data, normalized_format, options, force)

            if normalized_format in {"zip", "archive"}:
                data, content_type, extension = self._build_zip(project, page_data, metadata)
            elif normalized_format == "png_sequence":
                data, content_type, extension = self._build_png_sequence(project, page_data, metadata)
            elif normalized_format == "pdf":
                data, content_type, extension = self._build_pdf(project, page_data, metadata)
            elif normalized_format == "epub":
                data, content_type, extension = self._build_epub(project, page_data, metadata)
            elif normalized_format == "webtoon":
                data, content_type, extension = self._build_webtoon_package(project, page_data, metadata, options)
            else:
                data, content_type, extension = self._build_layered_package(project, page_data, metadata)

            storage_key = f"exports/{project.id}/{export.id}.{extension}"
            self.storage.put_bytes(key=storage_key, data=data, content_type=content_type)
            asset = Asset(
                project_id=project.id,
                filename=f"{slugify(project.name)}-{normalized_format}.{extension}",
                kind="project_export",
                content_type=content_type,
                size_bytes=len(data),
                storage_key=storage_key,
                metadata_json={
                    "export_id": str(export.id),
                    "format": normalized_format,
                    "preset_id": metadata["export"].get("preset", {}).get("id"),
                    "project_id": str(project.id),
                    "page_count": len(page_data),
                    "force": force,
                    "options": options,
                    "public_url": self.storage.public_url(storage_key),
                },
            )
            self.session.add(asset)
            self.session.flush()
            provenance_service = ProvenanceService(self.session)
            provenance_summary = provenance_service.project_provenance(project.id).summary
            provenance_service.record_asset(
                asset,
                source_type="internal_mock",
                provider_name="manga-ai-exporter",
                model_name=f"export-{normalized_format}",
                declared_rights="Packaged by Manga AI Studio from project assets and metadata.",
                license_type="project_export",
                allow_training=False,
                allow_commercial_use=True,
                ai_disclosure_required=provenance_summary.ai_disclosure_required,
            )
            export.file_asset_id = asset.id
            export.status = "succeeded"
            export.error_message = None
            export.updated_at = utc_now()
            self.session.add(export)
            self.session.commit()
            self.session.refresh(export)
            logger.info(
                "export job succeeded",
                extra={
                    "job_id": str(export.id),
                    "project_id": str(project.id),
                },
            )
            VersioningService(self.session).create_snapshot(
                export,
                label=f"{export.format.upper()} export succeeded",
                reason="export_created",
            )
            self.session.commit()
            return export
        except Exception as exc:
            export.status = "failed"
            export.error_message = str(exc)[:4000]
            export.updated_at = utc_now()
            self.session.add(export)
            self.session.commit()
            self.session.refresh(export)
            logger.warning(
                "export job failed",
                extra={
                    "job_id": str(export.id),
                    "project_id": str(project.id),
                },
            )
            VersioningService(self.session).create_snapshot(
                export,
                label=f"{export.format.upper()} export failed",
                reason="export_created",
            )
            self.session.commit()
            return export

    def _assert_qa_allows_export(self, pages: list[Page], force: bool) -> None:
        if force:
            return
        blocking_pages: list[int] = []
        for page in pages:
            report = latest_qa_report(self.session, "page", page.id)
            if report is not None and report.blocking:
                blocking_pages.append(page.page_number)
        if blocking_pages:
            page_list = ", ".join(str(page_number) for page_number in blocking_pages)
            raise ExportError(f"Blocking QA issues must be resolved before export. Pages: {page_list}")

    def _load_page_export_data(self, page: Page) -> PageExportData:
        composite = get_latest_composite_asset(self.session, page.id)
        if composite is None:
            raise ExportError(f"Page {page.page_number} does not have a final composite PNG")
        composite_bytes = self.storage.get_bytes(composite.storage_key)
        panels = self.session.exec(
            select(Panel)
            .where(Panel.page_id == page.id)
            .order_by(Panel.reading_order.asc(), Panel.created_at.asc())
        ).all()
        panel_ids = [panel.id for panel in panels]
        bubbles_by_panel = self._load_bubbles_by_panel(panel_ids)
        sfx_elements = self._load_sfx(page.id)
        renders_by_panel = self._latest_renders_by_panel(panel_ids)
        return PageExportData(
            page=page,
            composite_asset=composite,
            composite_bytes=composite_bytes,
            panels=panels,
            bubbles_by_panel=bubbles_by_panel,
            sfx_elements=sfx_elements,
            renders_by_panel=renders_by_panel,
        )

    def _build_zip(
        self,
        project: Project,
        page_data: list[PageExportData],
        metadata: dict[str, Any],
    ) -> tuple[bytes, str, str]:
        output = BytesIO()
        provenance = ProvenanceService(self.session)
        provenance_payload = provenance.export_payload(project.id)
        rights_summary = provenance.rights_summary(project.id)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("project.json", json_bytes(metadata))
            archive.writestr("provenance.json", json_bytes(provenance_payload))
            archive.writestr("asset-rights-summary.json", json_bytes(rights_summary))
            if provenance_payload["summary"]["ai_disclosure_required"]:
                archive.writestr("ai_disclosure.txt", provenance.ai_disclosure_text(project.id))
            for page_item in page_data:
                archive.writestr(page_png_path(page_item.page), page_item.composite_bytes)
        return output.getvalue(), "application/zip", "zip"

    def _build_png_sequence(
        self,
        project: Project,
        page_data: list[PageExportData],
        metadata: dict[str, Any],
    ) -> tuple[bytes, str, str]:
        output = BytesIO()
        provenance = ProvenanceService(self.session)
        provenance_payload = provenance.export_payload(project.id)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("metadata.json", json_bytes(metadata))
            archive.writestr("provenance.json", json_bytes(provenance_payload))
            archive.writestr("asset-rights-summary.json", json_bytes(provenance.rights_summary(project.id)))
            if provenance_payload["summary"]["ai_disclosure_required"]:
                archive.writestr("ai_disclosure.txt", provenance.ai_disclosure_text(project.id))
            for page_item in page_data:
                archive.writestr(f"png-sequence/page-{page_item.page.page_number:03d}.png", page_item.composite_bytes)
        return output.getvalue(), "application/zip", "zip"

    def _build_pdf(self, project: Project, page_data: list[PageExportData], metadata: dict[str, Any]) -> tuple[bytes, str, str]:
        images = [Image.open(BytesIO(page.composite_bytes)).convert("RGB") for page in page_data]
        if not images:
            raise ExportError("No page images available for PDF export")
        output = BytesIO()
        publishing = metadata.get("publishing", {})
        title = str(publishing.get("title") or project.name)
        author = str(publishing.get("author_name") or "")
        images[0].save(
            output,
            format="PDF",
            save_all=True,
            append_images=images[1:],
            title=title,
            author=author,
            subject=str(publishing.get("synopsis") or project.description or ""),
            creator="Manga AI Studio",
        )
        return output.getvalue(), "application/pdf", "pdf"

    def _build_webtoon_package(
        self,
        project: Project,
        page_data: list[PageExportData],
        metadata: dict[str, Any],
        options: dict[str, Any],
    ) -> tuple[bytes, str, str]:
        preset = metadata["export"].get("preset", {})
        preset_options = preset.get("options") if isinstance(preset.get("options"), dict) else {}
        target_width = int(options.get("page_width") or preset.get("page_width") or 1080)
        spacing = int(options.get("spacing", preset_options.get("spacing", 80)))
        max_height = int(options.get("max_image_height", preset_options.get("max_image_height", 16000)))
        background = str(options.get("background", "white"))
        strips = build_webtoon_strips(page_data, target_width=target_width, spacing=spacing, max_height=max_height, background=background)
        output = BytesIO()
        provenance = ProvenanceService(self.session)
        provenance_payload = provenance.export_payload(project.id)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("metadata.json", json_bytes(metadata))
            archive.writestr("provenance.json", json_bytes(provenance_payload))
            archive.writestr("asset-rights-summary.json", json_bytes(provenance.rights_summary(project.id)))
            if provenance_payload["summary"]["ai_disclosure_required"]:
                archive.writestr("ai_disclosure.txt", provenance.ai_disclosure_text(project.id))
            for index, strip in enumerate(strips, start=1):
                image_output = BytesIO()
                strip.save(image_output, format="PNG", optimize=True)
                archive.writestr(f"webtoon/strip-{index:03d}.png", image_output.getvalue())
            archive.writestr(
                "webtoon/manifest.json",
                json_bytes(
                    {
                        "strip_count": len(strips),
                        "target_width": target_width,
                        "spacing": spacing,
                        "max_image_height": max_height,
                        "panel_slicing": bool(options.get("panel_slicing", preset_options.get("panel_slicing", False))),
                    }
                ),
            )
        return output.getvalue(), "application/zip", "zip"

    def _build_epub(
        self,
        project: Project,
        page_data: list[PageExportData],
        metadata: dict[str, Any],
    ) -> tuple[bytes, str, str]:
        output = BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            provenance = ProvenanceService(self.session)
            provenance_payload = provenance.export_payload(project.id)
            archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
            archive.writestr("META-INF/container.xml", epub_container_xml())
            archive.writestr("OEBPS/package.opf", epub_package_opf(project, page_data, metadata))
            archive.writestr("OEBPS/nav.xhtml", epub_nav_xhtml(project, page_data))
            archive.writestr("OEBPS/metadata.json", json_bytes(metadata))
            archive.writestr("OEBPS/provenance.json", json_bytes(provenance_payload))
            archive.writestr("OEBPS/asset-rights-summary.json", json_bytes(provenance.rights_summary(project.id)))
            if provenance_payload["summary"]["ai_disclosure_required"]:
                archive.writestr("OEBPS/ai_disclosure.txt", provenance.ai_disclosure_text(project.id))
            for page_item in page_data:
                archive.writestr(f"OEBPS/images/page-{page_item.page.page_number:03d}.png", page_item.composite_bytes)
                archive.writestr(f"OEBPS/pages/page-{page_item.page.page_number:03d}.xhtml", epub_page_xhtml(page_item.page))
        return output.getvalue(), "application/epub+zip", "epub"

    def _build_layered_package(
        self,
        project: Project,
        page_data: list[PageExportData],
        metadata: dict[str, Any],
    ) -> tuple[bytes, str, str]:
        output = BytesIO()
        provenance = ProvenanceService(self.session)
        provenance_payload = provenance.export_payload(project.id)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("metadata.json", json_bytes(metadata))
            archive.writestr("provenance.json", json_bytes(provenance_payload))
            archive.writestr("asset-rights-summary.json", json_bytes(provenance.rights_summary(project.id)))
            if provenance_payload["summary"]["ai_disclosure_required"]:
                archive.writestr("ai_disclosure.txt", provenance.ai_disclosure_text(project.id))
            for page_item in page_data:
                page_dir = f"pages/page-{page_item.page.page_number:03d}"
                archive.writestr(f"{page_dir}/layout.json", json_bytes(page_layout_export(page_item)))
                archive.writestr(f"{page_dir}/final.png", page_item.composite_bytes)
                for panel in page_item.panels:
                    render = page_item.renders_by_panel.get(panel.id)
                    if render is not None:
                        archive.writestr(f"{page_dir}/panels/panel-{panel.reading_order:03d}.png", self.storage.get_bytes(render.storage_key))
                archive.writestr(f"{page_dir}/bubbles/bubbles.json", json_bytes(bubbles_export(page_item)))
                archive.writestr(f"{page_dir}/bubbles/bubbles.svg", bubbles_svg(page_item))
                archive.writestr(f"{page_dir}/sfx/sfx.json", json_bytes(sfx_export(page_item)))
                archive.writestr(f"{page_dir}/lettering/lettering.svg", lettering_svg_for_page(self.session, page_item.page.id))
        return output.getvalue(), "application/zip", "zip"

    def _project_metadata(
        self,
        project: Project,
        page_data: list[PageExportData],
        export_format: str,
        options: dict[str, Any],
        force: bool,
    ) -> dict[str, Any]:
        preset_id = str(options.get("preset_id") or options.get("preset") or export_format)
        try:
            preset = get_export_preset(preset_id)
        except ValueError:
            preset = get_export_preset(export_format)
        publishing = get_project_publishing_metadata(self.session, project.id)
        return {
            "project": {
                "id": str(project.id),
                "name": project.name,
                "description": project.description,
                "style_prompt": project.style_prompt,
                "status": project.status,
            },
            "publishing": publishing_metadata(project, publishing),
            "export": {
                "format": export_format,
                "preset": preset.to_read().model_dump(mode="json"),
                "created_at": utc_now().isoformat(),
                "force": force,
                "options": options,
                "provenance": ProvenanceService(self.session).rights_summary(project.id),
            },
            "pages": [
                {
                    "id": str(item.page.id),
                    "page_number": item.page.page_number,
                    "width": item.page.width,
                    "height": item.page.height,
                    "reading_direction": (item.page.layout_json or {}).get("reading_direction", "rtl"),
                    "layout": item.page.layout_json,
                    "final_asset": asset_metadata(item.composite_asset),
                    "panels": [
                        {
                            "id": str(panel.id),
                            "reading_order": panel.reading_order,
                            "x": panel.x,
                            "y": panel.y,
                            "width": panel.width,
                            "height": panel.height,
                            "polygon": panel.polygon,
                            "prompt": panel.prompt,
                            "render": render_metadata(item.renders_by_panel.get(panel.id), self.session),
                            "bubbles": [
                                bubble_metadata(bubble)
                                for bubble in item.bubbles_by_panel.get(panel.id, [])
                            ],
                            "sfx": [
                                sfx_metadata(element)
                                for element in item.sfx_elements
                                if element.panel_id == panel.id
                            ],
                        }
                        for panel in item.panels
                    ],
                    "page_sfx": [
                        sfx_metadata(element)
                        for element in item.sfx_elements
                        if element.panel_id is None
                    ],
                }
                for item in page_data
            ],
        }

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
        renders_by_panel: dict[uuid.UUID, Render] = {}
        if not panel_ids:
            return renders_by_panel
        renders = self.session.exec(
            select(Render, GenerationJob)
            .join(GenerationJob, GenerationJob.id == Render.job_id)
            .where(Render.panel_id.in_(panel_ids), GenerationJob.status == "succeeded")
            .order_by(Render.created_at.desc())
        ).all()
        for render, _job in renders:
            renders_by_panel.setdefault(render.panel_id, render)
        return renders_by_panel


def normalize_export_format(format_value: str) -> str:
    normalized = format_value.lower().strip()
    if normalized in {"layered_project", "project_package", "package"}:
        normalized = "layered"
    if normalized in {"kindle", "kindle_fixed_layout"}:
        normalized = "epub"
    if normalized in {"web_preview_png", "high_res_png_sequence"}:
        normalized = "png_sequence" if "high_res" in normalized else "zip"
    if normalized in {"archive_package"}:
        normalized = "archive"
    if normalized in {"layered_production_package"}:
        normalized = "layered"
    if normalized in {"webtoon_vertical_strip"}:
        normalized = "webtoon"
    if normalized in {"print_pdf"}:
        normalized = "pdf"
    if normalized in {"epub_fixed_layout"}:
        normalized = "epub"
    if normalized not in EXPORT_FORMATS:
        raise ExportError(f"Unsupported export format: {format_value}")
    return normalized


def page_png_path(page: Page) -> str:
    return f"pages/page-{page.page_number:03d}.png"


def page_layout_export(page_item: PageExportData) -> dict[str, Any]:
    return {
        "page": {
            "id": str(page_item.page.id),
            "page_number": page_item.page.page_number,
            "width": page_item.page.width,
            "height": page_item.page.height,
            "layout": page_item.page.layout_json,
            "reading_direction": (page_item.page.layout_json or {}).get("reading_direction", "rtl"),
        },
        "panels": [
            {
                "id": str(panel.id),
                "reading_order": panel.reading_order,
                "x": panel.x,
                "y": panel.y,
                "width": panel.width,
                "height": panel.height,
                "polygon": panel.polygon,
                "prompt": panel.prompt,
                "render_storage_key": page_item.renders_by_panel.get(panel.id).storage_key
                if page_item.renders_by_panel.get(panel.id)
                else None,
            }
            for panel in page_item.panels
        ],
    }


def bubbles_export(page_item: PageExportData) -> dict[str, Any]:
    return {
        "page_id": str(page_item.page.id),
        "bubbles": [
            bubble_metadata(bubble)
            for bubbles in page_item.bubbles_by_panel.values()
            for bubble in bubbles
        ],
    }


def sfx_export(page_item: PageExportData) -> dict[str, Any]:
    return {
        "page_id": str(page_item.page.id),
        "sfx": [sfx_metadata(element) for element in page_item.sfx_elements],
    }


def bubbles_svg(page_item: PageExportData) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_item.page.width}" height="{page_item.page.height}" viewBox="0 0 {page_item.page.width} {page_item.page.height}">'
    ]
    for bubbles in page_item.bubbles_by_panel.values():
        for bubble in bubbles:
            if bubble.kind == "narration":
                parts.append(
                    f'<rect x="{bubble.x}" y="{bubble.y}" width="{bubble.width}" height="{bubble.height}" fill="white" stroke="black" />'
                )
            else:
                parts.append(
                    f'<ellipse cx="{bubble.x + bubble.width / 2}" cy="{bubble.y + bubble.height / 2}" rx="{bubble.width / 2}" ry="{bubble.height / 2}" fill="white" stroke="black" />'
                )
            parts.append(
                f'<text x="{bubble.x + bubble.width / 2}" y="{bubble.y + bubble.height / 2}" text-anchor="middle" dominant-baseline="middle" font-size="24">{escape_xml(bubble.text)}</text>'
            )
    parts.append("</svg>")
    return "\n".join(parts)


def epub_container_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/package.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def epub_package_opf(project: Project, page_data: list[PageExportData], metadata: dict[str, Any]) -> str:
    manifest_items = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="metadata" href="metadata.json" media-type="application/json"/>',
    ]
    spine_items = []
    for item in page_data:
        page_id = f"page-{item.page.page_number:03d}"
        manifest_items.append(f'<item id="{page_id}" href="pages/{page_id}.xhtml" media-type="application/xhtml+xml"/>')
        manifest_items.append(f'<item id="{page_id}-image" href="images/{page_id}.png" media-type="image/png"/>')
        spine_items.append(f'<itemref idref="{page_id}"/>')
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="book-id" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">{project.id}</dc:identifier>
    <dc:title>{escape_xml(project.name)}</dc:title>
    <dc:language>en</dc:language>
    <meta property="rendition:layout">pre-paginated</meta>
    <meta property="manga-ai:reading-direction">{metadata["pages"][0]["reading_direction"] if metadata["pages"] else "rtl"}</meta>
  </metadata>
  <manifest>
    {"".join(manifest_items)}
  </manifest>
  <spine>
    {"".join(spine_items)}
  </spine>
</package>
"""


def epub_nav_xhtml(project: Project, page_data: list[PageExportData]) -> str:
    links = "".join(
        f'<li><a href="pages/page-{item.page.page_number:03d}.xhtml">Page {item.page.page_number}</a></li>'
        for item in page_data
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>{escape_xml(project.name)}</title></head>
  <body>
    <nav epub:type="toc" xmlns:epub="http://www.idpf.org/2007/ops">
      <ol>{links}</ol>
    </nav>
  </body>
</html>
"""


def epub_page_xhtml(page: Page) -> str:
    page_name = f"page-{page.page_number:03d}"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Page {page.page_number}</title></head>
  <body style="margin:0">
    <img src="../images/{page_name}.png" alt="Page {page.page_number}" style="width:100%;height:auto"/>
  </body>
</html>
"""


def asset_metadata(asset: Asset | None) -> dict[str, Any] | None:
    if asset is None:
        return None
    return {
        "id": str(asset.id),
        "filename": asset.filename,
        "kind": asset.kind,
        "content_type": asset.content_type,
        "size_bytes": asset.size_bytes,
        "storage_key": asset.storage_key,
        "metadata": asset.metadata_json,
    }


def render_metadata(render: Render | None, session: Session) -> dict[str, Any] | None:
    if render is None:
        return None
    job = session.get(GenerationJob, render.job_id)
    return {
        "id": str(render.id),
        "job_id": str(render.job_id),
        "asset_id": str(render.asset_id) if render.asset_id else None,
        "storage_key": render.storage_key,
        "width": render.width,
        "height": render.height,
        "mime_type": render.mime_type,
        "provenance": {
            "provider": job.provider if job else None,
            "model_name": job.input_payload.get("model_name") if job and isinstance(job.input_payload, dict) else None,
            "prompt": job.input_payload.get("prompt") if job and isinstance(job.input_payload, dict) else None,
            "prompt_json": job.input_payload.get("prompt_json") if job and isinstance(job.input_payload, dict) else None,
            "options": job.input_payload.get("options") if job and isinstance(job.input_payload, dict) else None,
            "output": job.output_payload if job else {},
        },
    }


def bubble_metadata(bubble: Bubble) -> dict[str, Any]:
    return {
        "id": str(bubble.id),
        "panel_id": str(bubble.panel_id),
        "kind": bubble.kind,
        "bubble_type": bubble.bubble_type,
        "speaker_character_id": str(bubble.speaker_character_id) if bubble.speaker_character_id else None,
        "x": bubble.x,
        "y": bubble.y,
        "width": bubble.width,
        "height": bubble.height,
        "text": bubble.text,
        "language": bubble.language,
        "reading_direction": bubble.reading_direction,
        "shape": bubble.shape,
        "position": bubble.position,
        "size": bubble.size,
        "tail_target": bubble.tail_target,
        "font_family": bubble.font_family,
        "font_size": bubble.font_size,
        "font_weight": bubble.font_weight,
        "text_align": bubble.text_align,
        "vertical_text": bubble.vertical_text,
        "z_index": bubble.z_index,
        "locked": bubble.locked,
    }


def sfx_metadata(element: SFXElement) -> dict[str, Any]:
    return {
        "id": str(element.id),
        "page_id": str(element.page_id),
        "panel_id": str(element.panel_id) if element.panel_id else None,
        "text": element.text,
        "meaning": element.meaning,
        "style": element.style,
        "position": element.position,
        "size": element.size,
        "rotation": element.rotation,
        "warp_style": element.warp_style,
        "stroke_width": element.stroke_width,
        "fill": element.fill,
        "outline": element.outline,
        "z_index": element.z_index,
        "locked": element.locked,
    }


def build_webtoon_strips(
    page_data: list[PageExportData],
    *,
    target_width: int,
    spacing: int,
    max_height: int,
    background: str,
) -> list[Image.Image]:
    if not page_data:
        raise ExportError("No page images available for webtoon export")
    target_width = max(1, target_width)
    spacing = max(0, spacing)
    max_height = max(target_width, max_height)
    resized: list[Image.Image] = []
    for item in page_data:
        image = Image.open(BytesIO(item.composite_bytes)).convert("RGB")
        scale = target_width / image.width
        target_height = max(1, int(image.height * scale))
        resized.append(image.resize((target_width, target_height), Image.Resampling.LANCZOS))

    strips: list[Image.Image] = []
    current_images: list[Image.Image] = []
    current_height = 0
    for image in resized:
        additional = image.height + (spacing if current_images else 0)
        if current_images and current_height + additional > max_height:
            strips.append(stack_images(current_images, target_width, spacing, background))
            current_images = [image]
            current_height = image.height
        else:
            current_images.append(image)
            current_height += additional
    if current_images:
        strips.append(stack_images(current_images, target_width, spacing, background))
    return strips


def stack_images(images: list[Image.Image], width: int, spacing: int, background: str) -> Image.Image:
    height = sum(image.height for image in images) + spacing * max(0, len(images) - 1)
    strip = Image.new("RGB", (width, height), background)
    y = 0
    for image in images:
        strip.paste(image, (0, y))
        y += image.height + spacing
    return strip


def publishing_metadata(project: Project, publishing: Any | None) -> dict[str, Any]:
    if publishing is None:
        return {
            "title": project.name,
            "subtitle": "",
            "author_name": "",
            "publisher": "",
            "language": "en",
            "synopsis": project.description or "",
            "age_rating": "unrated",
            "genres": [],
            "tags": [],
            "copyright_notice": "",
            "ai_disclosure_text": "Created with AI-assisted tools in Manga AI Studio; review required before publication.",
        }
    return {
        "title": publishing.title,
        "subtitle": publishing.subtitle,
        "author_name": publishing.author_name,
        "publisher": publishing.publisher,
        "language": publishing.language,
        "synopsis": publishing.synopsis,
        "age_rating": publishing.age_rating,
        "genres": publishing.genres,
        "tags": publishing.tags,
        "copyright_notice": publishing.copyright_notice,
        "ai_disclosure_text": publishing.ai_disclosure_text,
        "metadata_json": publishing.metadata_json,
    }


def json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("utf-8")


def slugify(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "manga-ai-export"


def escape_xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
