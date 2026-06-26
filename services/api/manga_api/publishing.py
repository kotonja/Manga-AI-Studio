from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from manga_api.compositor import get_latest_composite_asset
from manga_api.models import Page, Project, ProjectPublishingMetadata, QAReport, RightsDeclaration
from manga_api.provenance import ProvenanceService
from manga_api.qa import latest_qa_report
from manga_api.schemas import (
    ExportPreviewResult,
    ExportPresetRead,
    ExportReadinessItem,
    ExportReadinessResult,
    ProjectPublishingMetadataRead,
    ProjectPublishingMetadataUpsert,
)


@dataclass(frozen=True)
class ExportPreset:
    id: str
    name: str
    description: str
    page_width: int
    page_height: int
    dpi: int
    bleed: int
    safe_margin: int
    color_mode: str
    reading_direction: str
    file_format: str
    compression_quality: int
    required_qa_gates: list[str] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)

    def to_read(self) -> ExportPresetRead:
        return ExportPresetRead(**asdict(self))


EXPORT_PRESETS: dict[str, ExportPreset] = {
    "web_preview_png": ExportPreset(
        id="web_preview_png",
        name="Web preview PNG",
        description="Lightweight PNG package for browser review.",
        page_width=1200,
        page_height=1800,
        dpi=96,
        bleed=0,
        safe_margin=60,
        color_mode="RGB",
        reading_direction="rtl",
        file_format="zip",
        compression_quality=82,
        required_qa_gates=["all_pages_composed", "reading_direction_set", "provenance_included"],
        options={"variant": "web_preview", "image_format": "png"},
    ),
    "high_res_png_sequence": ExportPreset(
        id="high_res_png_sequence",
        name="High-resolution PNG sequence",
        description="Full-resolution numbered page PNGs for review or print handoff.",
        page_width=2480,
        page_height=3508,
        dpi=300,
        bleed=90,
        safe_margin=180,
        color_mode="RGB",
        reading_direction="rtl",
        file_format="png_sequence",
        compression_quality=96,
        required_qa_gates=["all_pages_composed", "resolution_valid", "reading_direction_set", "provenance_included"],
        options={"variant": "high_res_sequence"},
    ),
    "print_pdf": ExportPreset(
        id="print_pdf",
        name="Print PDF",
        description="Print-oriented multi-page PDF with metadata and QA gates.",
        page_width=2480,
        page_height=3508,
        dpi=300,
        bleed=90,
        safe_margin=180,
        color_mode="grayscale_metadata",
        reading_direction="rtl",
        file_format="pdf",
        compression_quality=95,
        required_qa_gates=["all_pages_composed", "no_blocking_qa", "resolution_valid", "metadata_completed", "rights_completed"],
        options={"variant": "print_pdf"},
    ),
    "kindle_fixed_layout": ExportPreset(
        id="kindle_fixed_layout",
        name="Kindle fixed-layout package",
        description="Kindle-oriented fixed-layout EPUB package skeleton.",
        page_width=1600,
        page_height=2560,
        dpi=300,
        bleed=0,
        safe_margin=96,
        color_mode="RGB",
        reading_direction="rtl",
        file_format="epub",
        compression_quality=90,
        required_qa_gates=["all_pages_composed", "no_blocking_qa", "metadata_completed", "rights_completed", "provenance_included"],
        options={"variant": "kindle_fixed_layout", "rendition": "pre-paginated"},
    ),
    "epub_fixed_layout": ExportPreset(
        id="epub_fixed_layout",
        name="EPUB fixed-layout package",
        description="Standards-oriented fixed-layout EPUB skeleton with page images.",
        page_width=1600,
        page_height=2400,
        dpi=300,
        bleed=0,
        safe_margin=90,
        color_mode="RGB",
        reading_direction="rtl",
        file_format="epub",
        compression_quality=90,
        required_qa_gates=["all_pages_composed", "no_blocking_qa", "metadata_completed", "provenance_included"],
        options={"variant": "epub_fixed_layout", "rendition": "pre-paginated"},
    ),
    "webtoon_vertical_strip": ExportPreset(
        id="webtoon_vertical_strip",
        name="Webtoon vertical strip",
        description="Stacks final pages vertically with configurable spacing and splitting.",
        page_width=1080,
        page_height=0,
        dpi=96,
        bleed=0,
        safe_margin=48,
        color_mode="RGB",
        reading_direction="vertical-rl",
        file_format="webtoon",
        compression_quality=88,
        required_qa_gates=["all_pages_composed", "reading_direction_set", "provenance_included"],
        options={"spacing": 80, "max_image_height": 16000, "panel_slicing": False},
    ),
    "layered_production_package": ExportPreset(
        id="layered_production_package",
        name="Layered production package",
        description="Production handoff with layouts, panels, lettering SVG/JSON, composites, and provenance.",
        page_width=2480,
        page_height=3508,
        dpi=300,
        bleed=90,
        safe_margin=180,
        color_mode="grayscale_metadata",
        reading_direction="rtl",
        file_format="layered",
        compression_quality=96,
        required_qa_gates=["all_pages_composed", "provenance_included", "metadata_completed"],
        options={"variant": "layered_production"},
    ),
    "archive_package": ExportPreset(
        id="archive_package",
        name="Archive package",
        description="Complete project archive with final pages, metadata, provenance, and rights summary.",
        page_width=1600,
        page_height=2400,
        dpi=300,
        bleed=0,
        safe_margin=90,
        color_mode="RGB",
        reading_direction="rtl",
        file_format="archive",
        compression_quality=90,
        required_qa_gates=["all_pages_composed", "provenance_included", "metadata_completed", "rights_completed"],
        options={"variant": "archive"},
    ),
}


def list_export_presets() -> list[ExportPresetRead]:
    return [preset.to_read() for preset in EXPORT_PRESETS.values()]


def get_export_preset(preset_id: str) -> ExportPreset:
    key = preset_id.strip().lower()
    preset = EXPORT_PRESETS.get(key)
    if preset is None:
        # Backward-compatible mapping from raw formats to professional presets.
        fallback = {
            "zip": "archive_package",
            "pdf": "print_pdf",
            "epub": "epub_fixed_layout",
            "layered": "layered_production_package",
            "webtoon": "webtoon_vertical_strip",
            "png_sequence": "high_res_png_sequence",
            "archive": "archive_package",
        }.get(key)
        preset = EXPORT_PRESETS.get(fallback or "")
    if preset is None:
        raise ValueError(f"Unsupported export preset: {preset_id}")
    return preset


class ExportReadinessService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def readiness(self, project_id: uuid.UUID | str, preset_id: str = "archive_package") -> ExportReadinessResult:
        project = self._require_project(project_id)
        preset = get_export_preset(preset_id)
        pages = self._pages(project.id)
        metadata = get_project_publishing_metadata(self.session, project.id)
        rights = self.session.exec(select(RightsDeclaration).where(RightsDeclaration.project_id == project.id)).first()
        provenance = ProvenanceService(self.session).project_provenance(project.id)
        checklist = [
            self._all_pages_composed(pages),
            self._no_blocking_qa(pages),
            self._page_count_valid(pages),
            self._resolution_valid(pages, preset),
            self._reading_direction_set(pages),
            ExportReadinessItem(
                key="provenance_included",
                label="Provenance included",
                passed=provenance.summary.missing_provenance_asset_ids == [],
                severity="blocking",
                message=(
                    "All assets have provenance records."
                    if provenance.summary.missing_provenance_asset_ids == []
                    else f"{len(provenance.summary.missing_provenance_asset_ids)} assets are missing provenance."
                ),
                details={"missing_asset_ids": provenance.summary.missing_provenance_asset_ids},
            ),
            ExportReadinessItem(
                key="rights_completed",
                label="Rights declaration completed",
                passed=bool(
                    rights
                    and rights.user_confirms_upload_rights
                    and rights.user_confirms_no_unlicensed_ip
                    and rights.user_confirms_review_required_before_publish
                ),
                severity="blocking",
                message="Rights declaration is complete." if rights else "Rights declaration is missing.",
            ),
            self._metadata_completed(project, metadata),
        ]
        required = set(preset.required_qa_gates)
        relevant = [item for item in checklist if item.key in required or item.severity == "blocking"]
        blocking_issue_count = sum(1 for item in relevant if not item.passed and (item.key in required or item.severity == "blocking"))
        return ExportReadinessResult(
            project_id=project.id,
            preset=preset.to_read(),
            ready=blocking_issue_count == 0,
            force_required=blocking_issue_count > 0,
            checklist=checklist,
            page_count=len(pages),
            blocking_issue_count=blocking_issue_count,
            metadata=ProjectPublishingMetadataRead.model_validate(metadata) if metadata else None,
        )

    def preview(self, project_id: uuid.UUID | str, preset_id: str = "archive_package", options: dict[str, Any] | None = None) -> ExportPreviewResult:
        project = self._require_project(project_id)
        readiness = self.readiness(project.id, preset_id)
        preset = get_export_preset(preset_id)
        pages = self._pages(project.id)
        estimated_files = ["metadata.json", "provenance.json", "asset-rights-summary.json"]
        if preset.file_format == "pdf":
            estimated_files.append(f"{slug(project.name)}.pdf")
        elif preset.file_format == "epub":
            estimated_files.extend(["mimetype", "OEBPS/package.opf", *[f"OEBPS/images/page-{page.page_number:03d}.png" for page in pages]])
        elif preset.file_format == "webtoon":
            estimated_files.extend(["webtoon/strip-001.png", "metadata.json"])
        elif preset.file_format in {"layered", "archive", "zip", "png_sequence"}:
            estimated_files.extend([f"pages/page-{page.page_number:03d}.png" for page in pages])
        estimated_size = sum((get_latest_composite_asset(self.session, page.id).size_bytes if get_latest_composite_asset(self.session, page.id) else 0) for page in pages)
        return ExportPreviewResult(
            project_id=project.id,
            preset=preset.to_read(),
            readiness=readiness,
            estimated_files=estimated_files,
            estimated_size_bytes=estimated_size,
            warnings=[item.message for item in readiness.checklist if not item.passed],
            metadata_preview={
                "preset": preset.id,
                "format": preset.file_format,
                "page_count": len(pages),
                "options": {**preset.options, **(options or {})},
            },
        )

    def _all_pages_composed(self, pages: list[Page]) -> ExportReadinessItem:
        missing = [page.page_number for page in pages if get_latest_composite_asset(self.session, page.id) is None]
        return ExportReadinessItem(
            key="all_pages_composed",
            label="All pages composed",
            passed=not missing and bool(pages),
            message="All pages have final composite PNGs." if not missing and pages else f"Missing composites for pages: {missing or 'all'}.",
            details={"missing_page_numbers": missing},
        )

    def _no_blocking_qa(self, pages: list[Page]) -> ExportReadinessItem:
        blocking: list[int] = []
        for page in pages:
            report = latest_qa_report(self.session, "page", page.id)
            if report is not None and report.blocking:
                blocking.append(page.page_number)
        return ExportReadinessItem(
            key="no_blocking_qa",
            label="No blocking QA",
            passed=not blocking,
            message="No blocking QA reports found." if not blocking else f"Blocking QA issues on pages: {blocking}.",
            details={"blocking_page_numbers": blocking},
        )

    def _page_count_valid(self, pages: list[Page]) -> ExportReadinessItem:
        return ExportReadinessItem(
            key="page_count_valid",
            label="Page count valid",
            passed=len(pages) > 0,
            message=f"{len(pages)} pages ready." if pages else "Project has no pages.",
            details={"page_count": len(pages)},
        )

    def _resolution_valid(self, pages: list[Page], preset: ExportPreset) -> ExportReadinessItem:
        invalid = [
            page.page_number
            for page in pages
            if preset.page_height > 0 and (page.width < preset.page_width or page.height < preset.page_height)
        ]
        return ExportReadinessItem(
            key="resolution_valid",
            label="Resolution valid",
            passed=not invalid,
            severity="blocking" if "resolution_valid" in preset.required_qa_gates else "warning",
            message="Page dimensions meet preset target." if not invalid else f"Pages below preset target: {invalid}.",
            details={"invalid_page_numbers": invalid, "target": {"width": preset.page_width, "height": preset.page_height, "dpi": preset.dpi}},
        )

    def _reading_direction_set(self, pages: list[Page]) -> ExportReadinessItem:
        missing = [page.page_number for page in pages if not (page.layout_json or {}).get("reading_direction")]
        return ExportReadinessItem(
            key="reading_direction_set",
            label="Reading direction set",
            passed=not missing,
            message="Reading direction metadata is set." if not missing else f"Missing reading direction on pages: {missing}.",
            details={"missing_page_numbers": missing},
        )

    def _metadata_completed(self, project: Project, metadata: ProjectPublishingMetadata | None) -> ExportReadinessItem:
        missing: list[str] = []
        if metadata is None:
            missing = ["title", "author_name", "language", "synopsis", "copyright_notice", "ai_disclosure_text"]
        else:
            for field_name in ["title", "author_name", "language", "synopsis", "copyright_notice", "ai_disclosure_text"]:
                if not str(getattr(metadata, field_name, "") or "").strip():
                    missing.append(field_name)
        return ExportReadinessItem(
            key="metadata_completed",
            label="Export metadata completed",
            passed=not missing,
            message="Publishing metadata is complete." if not missing else f"Missing metadata fields: {', '.join(missing)}.",
            details={"missing_fields": missing},
        )

    def _pages(self, project_id: uuid.UUID) -> list[Page]:
        return list(
            self.session.exec(
                select(Page)
                .where(Page.project_id == project_id)
                .order_by(Page.page_number.asc(), Page.created_at.asc())
            ).all()
        )

    def _require_project(self, project_id: uuid.UUID | str) -> Project:
        project = self.session.get(Project, uuid.UUID(str(project_id)))
        if project is None:
            raise ValueError("Project not found")
        return project


def get_project_publishing_metadata(session: Session, project_id: uuid.UUID | str) -> ProjectPublishingMetadata | None:
    return session.exec(
        select(ProjectPublishingMetadata).where(ProjectPublishingMetadata.project_id == uuid.UUID(str(project_id)))
    ).first()


def upsert_project_publishing_metadata(
    session: Session,
    project: Project,
    payload: ProjectPublishingMetadataUpsert,
) -> ProjectPublishingMetadata:
    metadata = get_project_publishing_metadata(session, project.id)
    if metadata is None:
        metadata = ProjectPublishingMetadata(project_id=project.id)
    updates = payload.model_dump()
    for field_name, value in updates.items():
        setattr(metadata, field_name, value)
    metadata.updated_at = datetime.now(timezone.utc)
    session.add(metadata)
    session.flush()
    return metadata


def default_metadata_from_project(project: Project) -> ProjectPublishingMetadataUpsert:
    return ProjectPublishingMetadataUpsert(
        title=project.name,
        subtitle="",
        author_name="",
        publisher="",
        language="en",
        synopsis=project.description or "",
        age_rating="unrated",
        genres=[],
        tags=[],
        copyright_notice="",
        ai_disclosure_text="Created with AI-assisted tools in Manga AI Studio; review required before publication.",
    )


def slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-") or "manga-export"
