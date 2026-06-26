from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from manga_api.models import Asset, AssetProvenance, Project, RightsDeclaration
from manga_api.schemas import (
    AssetProvenanceRead,
    AssetProvenanceUpdate,
    ProvenanceAssetRead,
    ProvenanceSummaryRead,
    ProjectProvenanceRead,
    RightsDeclarationRead,
    RightsDeclarationUpsert,
)


UPLOAD_RIGHTS_ERROR = (
    "Upload rights declaration is required before adding uploaded or imported assets. "
    "Confirm upload rights, no unlicensed IP, and review-before-publish in Project Provenance."
)


class RightsDeclarationRequiredError(RuntimeError):
    """Raised when a user-uploaded asset is added before project rights are declared."""


class ProvenanceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record_asset(
        self,
        asset: Asset,
        *,
        source_type: str,
        creator_user_id: str | None = None,
        provider_name: str | None = None,
        model_name: str | None = None,
        prompt_id: str | uuid.UUID | None = None,
        generation_job_id: str | uuid.UUID | None = None,
        uploaded_filename: str | None = None,
        declared_rights: str = "",
        license_type: str = "project_generated",
        allow_training: bool = False,
        allow_commercial_use: bool = True,
        ai_disclosure_required: bool | None = None,
    ) -> AssetProvenance:
        if ai_disclosure_required is None:
            ai_disclosure_required = source_type in {"ai_generated", "internal_mock"}
        provenance = self.session.exec(
            select(AssetProvenance).where(AssetProvenance.asset_id == asset.id)
        ).first()
        if provenance is None:
            provenance = AssetProvenance(asset_id=asset.id, source_type=source_type)

        provenance.source_type = source_type
        provenance.creator_user_id = creator_user_id
        provenance.provider_name = provider_name
        provenance.model_name = model_name
        provenance.prompt_id = str(prompt_id) if prompt_id is not None else None
        provenance.generation_job_id = uuid.UUID(str(generation_job_id)) if generation_job_id is not None else None
        provenance.uploaded_filename = uploaded_filename
        provenance.declared_rights = declared_rights
        provenance.license_type = license_type
        provenance.allow_training = allow_training
        provenance.allow_commercial_use = allow_commercial_use
        provenance.ai_disclosure_required = ai_disclosure_required
        provenance.updated_at = utc_now()
        self.session.add(provenance)
        self.session.flush()
        return provenance

    def update_asset_provenance(self, asset: Asset, payload: AssetProvenanceUpdate) -> AssetProvenance:
        provenance = self.session.exec(
            select(AssetProvenance).where(AssetProvenance.asset_id == asset.id)
        ).first()
        if provenance is None:
            provenance = AssetProvenance(
                asset_id=asset.id,
                source_type=payload.source_type or "imported",
                declared_rights=payload.declared_rights or "",
                license_type=payload.license_type or "unspecified",
            )
        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            if field == "generation_job_id" and value is not None:
                value = uuid.UUID(str(value))
            setattr(provenance, field, value)
        provenance.updated_at = utc_now()
        self.session.add(provenance)
        self.session.flush()
        return provenance

    def get_asset_provenance(self, asset_id: uuid.UUID | str) -> AssetProvenance | None:
        return self.session.exec(
            select(AssetProvenance).where(AssetProvenance.asset_id == uuid.UUID(str(asset_id)))
        ).first()

    def get_rights_declaration(self, project_id: uuid.UUID | str) -> RightsDeclaration | None:
        return self.session.exec(
            select(RightsDeclaration).where(RightsDeclaration.project_id == uuid.UUID(str(project_id)))
        ).first()

    def upsert_rights_declaration(
        self,
        project_id: uuid.UUID | str,
        payload: RightsDeclarationUpsert,
    ) -> RightsDeclaration:
        parsed_project_id = uuid.UUID(str(project_id))
        declaration = self.get_rights_declaration(parsed_project_id)
        if declaration is None:
            declaration = RightsDeclaration(project_id=parsed_project_id)
        for field, value in payload.model_dump().items():
            setattr(declaration, field, value)
        declaration.updated_at = utc_now()
        self.session.add(declaration)
        self.session.flush()
        return declaration

    def assert_upload_rights_declared(self, project_id: uuid.UUID | str) -> RightsDeclaration:
        declaration = self.get_rights_declaration(project_id)
        if declaration is None or not rights_declaration_complete(declaration):
            raise RightsDeclarationRequiredError(UPLOAD_RIGHTS_ERROR)
        return declaration

    def project_provenance(self, project_id: uuid.UUID | str) -> ProjectProvenanceRead:
        parsed_project_id = uuid.UUID(str(project_id))
        assets = list(
            self.session.exec(
                select(Asset)
                .where(Asset.project_id == parsed_project_id)
                .order_by(Asset.created_at.desc(), Asset.id.desc())
            ).all()
        )
        provenance_by_asset = {
            provenance.asset_id: provenance
            for provenance in self.session.exec(
                select(AssetProvenance).where(AssetProvenance.asset_id.in_([asset.id for asset in assets]))
            ).all()
        } if assets else {}
        source_counts = Counter(
            provenance.source_type
            for provenance in provenance_by_asset.values()
        )
        missing = [asset.id for asset in assets if asset.id not in provenance_by_asset]
        summary = ProvenanceSummaryRead(
            total_assets=len(assets),
            assets_with_provenance=len(provenance_by_asset),
            ai_disclosure_required=any(
                provenance.ai_disclosure_required
                for provenance in provenance_by_asset.values()
            ),
            source_type_counts=dict(source_counts),
            missing_provenance_asset_ids=missing,
        )
        declaration = self.get_rights_declaration(parsed_project_id)
        return ProjectProvenanceRead(
            project_id=parsed_project_id,
            rights_declaration=RightsDeclarationRead.model_validate(declaration) if declaration else None,
            summary=summary,
            assets=[
                ProvenanceAssetRead(
                    asset=asset,
                    provenance=AssetProvenanceRead.model_validate(provenance_by_asset.get(asset.id))
                    if asset.id in provenance_by_asset
                    else None,
                )
                for asset in assets
            ],
        )

    def export_payload(self, project_id: uuid.UUID | str) -> dict[str, Any]:
        project = self.session.get(Project, uuid.UUID(str(project_id)))
        provenance = self.project_provenance(project_id)
        return {
            "generated_at": utc_now().isoformat(),
            "project": {
                "id": str(project.id) if project else str(project_id),
                "name": project.name if project else None,
            },
            "rights_declaration": jsonable(provenance.rights_declaration),
            "summary": jsonable(provenance.summary),
            "assets": [
                {
                    "asset": jsonable(item.asset),
                    "provenance": jsonable(item.provenance),
                }
                for item in provenance.assets
            ],
        }

    def rights_summary(self, project_id: uuid.UUID | str) -> dict[str, Any]:
        payload = self.export_payload(project_id)
        assets = payload["assets"]
        return {
            "generated_at": payload["generated_at"],
            "project": payload["project"],
            "rights_declaration": payload["rights_declaration"],
            "source_type_counts": payload["summary"]["source_type_counts"],
            "ai_disclosure_required": payload["summary"]["ai_disclosure_required"],
            "assets": [
                {
                    "asset_id": item["asset"]["id"],
                    "filename": item["asset"]["filename"],
                    "kind": item["asset"]["kind"],
                    "source_type": (item["provenance"] or {}).get("source_type"),
                    "license_type": (item["provenance"] or {}).get("license_type"),
                    "declared_rights": (item["provenance"] or {}).get("declared_rights"),
                    "allow_commercial_use": (item["provenance"] or {}).get("allow_commercial_use"),
                    "ai_disclosure_required": (item["provenance"] or {}).get("ai_disclosure_required"),
                }
                for item in assets
            ],
        }

    def ai_disclosure_text(self, project_id: uuid.UUID | str) -> str:
        payload = self.export_payload(project_id)
        generated_assets = [
            item
            for item in payload["assets"]
            if item["provenance"] and item["provenance"].get("ai_disclosure_required")
        ]
        if not generated_assets:
            return "No AI disclosure is required by the current asset provenance records.\n"
        lines = [
            "AI and synthetic asset disclosure",
            "",
            "This package includes generated or synthetic production assets tracked by Manga AI Studio.",
            "",
        ]
        for item in generated_assets:
            provenance = item["provenance"] or {}
            asset = item["asset"]
            lines.append(
                f"- {asset['filename']} ({asset['kind']}): "
                f"{provenance.get('source_type')} via {provenance.get('provider_name') or 'Manga AI Studio'}, "
                f"model {provenance.get('model_name') or 'not specified'}."
            )
        lines.append("")
        return "\n".join(lines)


def rights_declaration_complete(declaration: RightsDeclaration) -> bool:
    return (
        declaration.user_confirms_upload_rights
        and declaration.user_confirms_no_unlicensed_ip
        and declaration.user_confirms_review_required_before_publish
    )


def jsonable(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return jsonable(value.model_dump())
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
