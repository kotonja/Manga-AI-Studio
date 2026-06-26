from __future__ import annotations

import uuid
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from PIL import Image, ImageDraw, ImageFont
from sqlmodel import Session, select

from manga_api.access import require_character_card_access, require_project_access, require_style_bible_access
from manga_api.auth import require_alpha_user
from manga_api.ai_tasks import AITaskRunner
from manga_api.db import get_session
from manga_api.llm import get_llm_provider
from manga_api.models import (
    Asset,
    Chapter,
    CharacterCard,
    CharacterReferenceAsset,
    CharacterState,
    ExpressionSheet,
    GenerationJob,
    Page,
    Project,
    Scene,
    StyleBible,
    StyleSampleAsset,
)
from manga_api.provenance import ProvenanceService, RightsDeclarationRequiredError
from manga_api.safety import get_safety_provider
from manga_api.schemas import (
    ActiveStyleUpdate,
    AssetRead,
    CharacterCardCreate,
    CharacterCardRead,
    CharacterCardUpdate,
    CharacterReferenceAssetRead,
    CharacterStateCreate,
    CharacterStateRead,
    CharacterStateUpdate,
    ExpressionSheetRead,
    GenerateCharacterSheetResult,
    GenerationJobRead,
    ReferenceAssetCreate,
    StyleDNAGenerateRequest,
    StyleDNAOptionsResult,
    StyleBibleLabCreate,
    StyleBibleLabRead,
    StyleBibleLabUpdate,
    StyleGuardResult,
    StylePreviewResult,
    StyleSampleAssetCreate,
    StyleSampleAssetRead,
)
from manga_api.storage import get_object_storage
from manga_api.style_guard import StyleRiskError, evaluate_style_safety, require_style_is_safe
from manga_api.uploads import UploadValidationError, validate_upload_metadata
from manga_api.versioning import VersioningService

router = APIRouter(tags=["labs"], dependencies=[Depends(require_alpha_user)])


def touch(row) -> None:
    row.updated_at = datetime.now(timezone.utc)


@router.post("/projects/{project_id}/characters", response_model=CharacterCardRead, status_code=status.HTTP_201_CREATED)
def create_character_card(
    project_id: uuid.UUID,
    payload: CharacterCardCreate,
    session: Session = Depends(get_session),
) -> CharacterCard:
    project = require_project(session, project_id)
    card = CharacterCard(project_id=project.id, **payload.model_dump())
    touch(project)
    session.add(card)
    session.add(project)
    session.commit()
    session.refresh(card)
    VersioningService(session).create_snapshot(card, label=f"{card.name} created", reason="character_card_create")
    session.commit()
    return card


@router.get("/projects/{project_id}/characters", response_model=list[CharacterCardRead])
def list_character_cards(project_id: uuid.UUID, session: Session = Depends(get_session)) -> list[CharacterCard]:
    require_project(session, project_id)
    return list(
        session.exec(
            select(CharacterCard)
            .where(CharacterCard.project_id == project_id)
            .order_by(CharacterCard.name.asc(), CharacterCard.created_at.asc())
        ).all()
    )


@router.get("/characters/{character_id}", response_model=CharacterCardRead)
def get_character_card(character_id: uuid.UUID, session: Session = Depends(get_session)) -> CharacterCard:
    return require_character_card(session, character_id)


@router.put("/characters/{character_id}", response_model=CharacterCardRead)
def update_character_card(
    character_id: uuid.UUID,
    payload: CharacterCardUpdate,
    session: Session = Depends(get_session),
) -> CharacterCard:
    card = require_character_card(session, character_id)
    VersioningService(session).create_snapshot(card, label=f"{card.name} before edit", reason="before_character_card_update")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(card, field, value)
    touch(card)
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


@router.delete("/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character_card(character_id: uuid.UUID, session: Session = Depends(get_session)) -> Response:
    card = require_character_card(session, character_id)
    session.delete(card)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/characters/{character_id}/reference-assets",
    response_model=CharacterReferenceAssetRead,
    status_code=status.HTTP_201_CREATED,
)
def create_character_reference_asset(
    character_id: uuid.UUID,
    payload: ReferenceAssetCreate,
    session: Session = Depends(get_session),
) -> CharacterReferenceAsset:
    card = require_character_card(session, character_id)
    try:
        validate_upload_metadata(
            filename=payload.filename,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    provenance_service = ProvenanceService(session)
    try:
        declaration = provenance_service.assert_upload_rights_declared(card.project_id)
    except RightsDeclarationRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    safety = get_safety_provider("mock").check_uploaded_image_metadata(
        {"filename": payload.filename, "kind": payload.kind, **payload.metadata_json}
    )
    if not safety.allowed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=safety.model_dump())
    VersioningService(session).create_snapshot(card, label=f"{card.name} before reference update", reason="before_character_reference_asset")
    storage_key = payload.storage_key or generated_storage_key("characters", card.id, payload.filename)
    catalog_asset = Asset(
        project_id=card.project_id,
        filename=payload.filename,
        kind="character_reference",
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        storage_key=storage_key,
        metadata_json={
            **payload.metadata_json,
            "character_card_id": str(card.id),
            "metadata_record_type": "character_reference_asset",
        },
    )
    session.add(catalog_asset)
    session.flush()
    source_type = normalize_uploaded_source_type(payload.metadata_json.get("source_type"))
    provenance_service.record_asset(
        catalog_asset,
        source_type=source_type,
        creator_user_id=string_or_none(payload.metadata_json.get("creator_user_id")),
        uploaded_filename=payload.filename,
        declared_rights=declaration.notes or "User declared they have rights to upload and use this reference asset.",
        license_type=string_or_none(payload.metadata_json.get("license_type")) or "user_declared_upload",
        allow_training=bool(payload.metadata_json.get("allow_training", False)),
        allow_commercial_use=bool(payload.metadata_json.get("allow_commercial_use", True)),
        ai_disclosure_required=False,
    )
    asset = CharacterReferenceAsset(
        project_id=card.project_id,
        character_card_id=card.id,
        filename=payload.filename,
        kind=payload.kind,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        storage_key=storage_key,
        metadata_json={
            **payload.metadata_json,
            "asset_id": str(catalog_asset.id),
            "rights_declaration_id": str(declaration.id),
        },
    )
    card.reference_asset_ids = merge_id(card.reference_asset_ids, asset.id)
    touch(card)
    session.add(asset)
    session.add(card)
    session.commit()
    session.refresh(asset)
    return asset


@router.get("/characters/{character_id}/reference-assets", response_model=list[CharacterReferenceAssetRead])
def list_character_reference_assets(
    character_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[CharacterReferenceAsset]:
    card = require_character_card(session, character_id)
    return list(
        session.exec(
            select(CharacterReferenceAsset)
            .where(CharacterReferenceAsset.character_card_id == card.id)
            .order_by(CharacterReferenceAsset.created_at.desc())
        ).all()
    )


@router.get("/characters/{character_id}/states", response_model=list[CharacterStateRead])
def list_character_states(
    character_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[CharacterState]:
    card = require_character_card(session, character_id)
    return list(
        session.exec(
            select(CharacterState)
            .where(CharacterState.character_id == card.id)
            .order_by(CharacterState.created_at.desc())
        ).all()
    )


@router.post("/characters/{character_id}/states", response_model=CharacterStateRead, status_code=status.HTTP_201_CREATED)
def create_character_state(
    character_id: uuid.UUID,
    payload: CharacterStateCreate,
    session: Session = Depends(get_session),
) -> CharacterState:
    card = require_character_card(session, character_id)
    validate_character_state_links(session, card, payload.chapter_id, payload.scene_id, payload.page_id)
    state_row = CharacterState(character_id=card.id, **payload.model_dump())
    touch(card)
    session.add(state_row)
    session.add(card)
    session.commit()
    session.refresh(state_row)
    return state_row


@router.put("/character-states/{state_id}", response_model=CharacterStateRead)
def update_character_state(
    state_id: uuid.UUID,
    payload: CharacterStateUpdate,
    session: Session = Depends(get_session),
) -> CharacterState:
    state_row = session.get(CharacterState, state_id)
    if state_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character state not found")
    card = require_character_card(session, state_row.character_id)
    updates = payload.model_dump(exclude_unset=True)
    chapter_id = updates.get("chapter_id", state_row.chapter_id)
    scene_id = updates.get("scene_id", state_row.scene_id)
    page_id = updates.get("page_id", state_row.page_id)
    validate_character_state_links(session, card, chapter_id, scene_id, page_id)
    for field, value in updates.items():
        setattr(state_row, field, value)
    touch(state_row)
    touch(card)
    session.add(state_row)
    session.add(card)
    session.commit()
    session.refresh(state_row)
    return state_row


@router.post(
    "/characters/{character_id}/generate-character-sheet",
    response_model=GenerateCharacterSheetResult,
    status_code=status.HTTP_201_CREATED,
)
def generate_character_sheet(
    character_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> GenerateCharacterSheetResult:
    card = require_character_card(session, character_id)
    VersioningService(session).create_snapshot(card, label=f"{card.name} before sheet generation", reason="before_character_sheet_generation")
    job = GenerationJob(
        project_id=card.project_id,
        provider="mock",
        job_type="character_sheet",
        status="succeeded",
        input_payload={"character_card_id": str(card.id), "provider": "mock"},
        output_payload={},
    )
    session.add(job)
    session.flush()

    expressions = ["neutral", "joy", "anger", "surprise"]
    assets: list[CharacterReferenceAsset] = []
    for expression in expressions:
        asset = CharacterReferenceAsset(
            project_id=card.project_id,
            character_card_id=card.id,
            filename=f"{slug(card.name)}-{expression}.png",
            kind="mock_character_sheet",
            content_type="image/png",
            size_bytes=0,
            storage_key=f"mock/characters/{card.id}/{expression}.png",
            metadata_json={
                "job_id": str(job.id),
                "expression": expression,
                "placeholder": True,
            },
        )
        session.add(asset)
        session.flush()
        assets.append(asset)

    card.reference_asset_ids = merge_ids(card.reference_asset_ids, [asset.id for asset in assets])
    touch(card)
    expression_sheet = ExpressionSheet(
        project_id=card.project_id,
        character_card_id=card.id,
        name=f"{card.name} Expression Sheet",
        expressions=expressions,
        asset_ids=[str(asset.id) for asset in assets],
    )
    job.output_payload = {
        "asset_ids": [str(asset.id) for asset in assets],
        "expression_sheet_id": str(expression_sheet.id),
    }
    touch(job)
    session.add(expression_sheet)
    session.add(card)
    session.add(job)
    session.commit()

    for asset in assets:
        session.refresh(asset)
    session.refresh(expression_sheet)
    session.refresh(job)
    return GenerateCharacterSheetResult(
        job=GenerationJobRead.model_validate(job),
        assets=[CharacterReferenceAssetRead.model_validate(asset) for asset in assets],
        expression_sheet=ExpressionSheetRead.model_validate(expression_sheet),
    )


@router.post("/projects/{project_id}/style-bibles", response_model=StyleBibleLabRead, status_code=status.HTTP_201_CREATED)
def create_style_bible(
    project_id: uuid.UUID,
    payload: StyleBibleLabCreate,
    session: Session = Depends(get_session),
) -> StyleBible:
    project = require_project(session, project_id)
    payload_dict = payload.model_dump()
    try:
        require_style_is_safe(payload_dict)
    except StyleRiskError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.result.model_dump()) from exc
    style_bible = StyleBible(
        project_id=project.id,
        **payload_dict,
    )
    touch(project)
    session.add(style_bible)
    session.add(project)
    session.commit()
    session.refresh(style_bible)
    VersioningService(session).create_snapshot(style_bible, label=f"{style_bible.name} created", reason="style_bible_create")
    session.commit()
    return style_bible


@router.post("/projects/{project_id}/style/generate-dna", response_model=StyleDNAOptionsResult, status_code=status.HTTP_201_CREATED)
def generate_style_dna(
    project_id: uuid.UUID,
    payload: StyleDNAGenerateRequest,
    session: Session = Depends(get_session),
) -> StyleDNAOptionsResult:
    project = require_project(session, project_id)
    result = AITaskRunner(session).run(
        "generate_style_dna",
        {
            "project_name": project.name,
            **payload.model_dump(),
        },
        StyleDNAOptionsResult,
        get_llm_provider(),
    )
    blocked_options = [
        option.style_name
        for option in result.options
        if not evaluate_style_safety(option.model_dump()).allowed
    ]
    if blocked_options:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Generated style DNA options failed safety guard: {', '.join(blocked_options)}",
        )
    return result


@router.post("/style/guard", response_model=StyleGuardResult)
def check_style_guard(payload: StyleBibleLabCreate) -> StyleGuardResult:
    return evaluate_style_safety(payload.model_dump())


@router.get("/projects/{project_id}/style-bibles", response_model=list[StyleBibleLabRead])
def list_style_bibles(project_id: uuid.UUID, session: Session = Depends(get_session)) -> list[StyleBible]:
    require_project(session, project_id)
    return list(
        session.exec(
            select(StyleBible)
            .where(StyleBible.project_id == project_id)
            .order_by(StyleBible.created_at.desc())
        ).all()
    )


@router.get("/style-bibles/{style_bible_id}", response_model=StyleBibleLabRead)
def get_style_bible(style_bible_id: uuid.UUID, session: Session = Depends(get_session)) -> StyleBible:
    return require_style_bible(session, style_bible_id)


@router.put("/style-bibles/{style_bible_id}", response_model=StyleBibleLabRead)
def update_style_bible(
    style_bible_id: uuid.UUID,
    payload: StyleBibleLabUpdate,
    session: Session = Depends(get_session),
) -> StyleBible:
    style_bible = require_style_bible(session, style_bible_id)
    updates = payload.model_dump(exclude_unset=True)
    guard_payload = StyleBibleLabRead.model_validate(style_bible).model_dump()
    guard_payload.update(updates)
    try:
        require_style_is_safe(guard_payload)
    except StyleRiskError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.result.model_dump()) from exc
    VersioningService(session).create_snapshot(style_bible, label=f"{style_bible.name} before edit", reason="before_style_bible_update")
    for field, value in updates.items():
        setattr(style_bible, field, value)
    touch(style_bible)
    session.add(style_bible)
    session.commit()
    session.refresh(style_bible)
    return style_bible


@router.delete("/style-bibles/{style_bible_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_style_bible(style_bible_id: uuid.UUID, session: Session = Depends(get_session)) -> Response:
    style_bible = require_style_bible(session, style_bible_id)
    projects = session.exec(
        select(Project).where(Project.active_style_bible_id == style_bible_id)
    ).all()
    for project in projects:
        project.active_style_bible_id = None
        touch(project)
        session.add(project)
    session.delete(style_bible)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/style-bibles/{style_bible_id}/mock-preview-panel", response_model=StylePreviewResult, status_code=status.HTTP_201_CREATED)
def generate_mock_style_preview_panel(
    style_bible_id: uuid.UUID,
    session: Session = Depends(get_session),
    storage=Depends(get_object_storage),
) -> StylePreviewResult:
    style_bible = require_style_bible(session, style_bible_id)
    safety = evaluate_style_safety(StyleBibleLabRead.model_validate(style_bible).model_dump())
    if not safety.allowed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=safety.model_dump())

    preview_prompt = style_preview_prompt(style_bible)
    data = render_style_preview_png(style_bible, preview_prompt)
    storage_key = f"style-previews/{style_bible.project_id}/{uuid.uuid4()}.png"
    storage.put_bytes(key=storage_key, data=data, content_type="image/png")
    public_url = storage.public_url(storage_key)
    asset = Asset(
        project_id=style_bible.project_id,
        filename=f"{slug(style_bible.style_name or style_bible.name)}-style-preview.png",
        kind="style_preview",
        content_type="image/png",
        size_bytes=len(data),
        storage_key=storage_key,
        metadata_json={
            "style_bible_id": str(style_bible.id),
            "preview_prompt": preview_prompt,
            "public_url": public_url,
            "mock": True,
            "style_name": style_bible.style_name or style_bible.name,
        },
    )
    session.add(asset)
    session.flush()
    ProvenanceService(session).record_asset(
        asset,
        source_type="internal_mock",
        provider_name="manga-ai-style-preview",
        model_name="mock-style-preview-v1",
        declared_rights="Mock preview generated inside Manga AI Studio for style evaluation.",
        license_type="project_generated",
        allow_training=False,
        allow_commercial_use=True,
        ai_disclosure_required=True,
    )
    session.commit()
    session.refresh(asset)
    return StylePreviewResult(
        asset=AssetRead.model_validate(asset),
        public_url=public_url,
        preview_prompt=preview_prompt,
        safety=safety,
    )


@router.post(
    "/style-bibles/{style_bible_id}/sample-assets",
    response_model=StyleSampleAssetRead,
    status_code=status.HTTP_201_CREATED,
)
def create_style_sample_asset(
    style_bible_id: uuid.UUID,
    payload: StyleSampleAssetCreate,
    session: Session = Depends(get_session),
) -> StyleSampleAsset:
    style_bible = require_style_bible(session, style_bible_id)
    try:
        validate_upload_metadata(
            filename=payload.filename,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    provenance_service = ProvenanceService(session)
    try:
        declaration = provenance_service.assert_upload_rights_declared(style_bible.project_id)
    except RightsDeclarationRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    safety = get_safety_provider("mock").check_uploaded_image_metadata(
        {"filename": payload.filename, "kind": payload.kind, **payload.metadata_json}
    )
    if not safety.allowed:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=safety.model_dump())
    storage_key = payload.storage_key or generated_storage_key("styles", style_bible.id, payload.filename)
    catalog_asset = Asset(
        project_id=style_bible.project_id,
        filename=payload.filename,
        kind="style_sample",
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        storage_key=storage_key,
        metadata_json={
            **payload.metadata_json,
            "style_bible_id": str(style_bible.id),
            "metadata_record_type": "style_sample_asset",
        },
    )
    session.add(catalog_asset)
    session.flush()
    source_type = normalize_uploaded_source_type(payload.metadata_json.get("source_type"))
    provenance_service.record_asset(
        catalog_asset,
        source_type=source_type,
        creator_user_id=string_or_none(payload.metadata_json.get("creator_user_id")),
        uploaded_filename=payload.filename,
        declared_rights=declaration.notes or "User declared they have rights to upload and use this style sample asset.",
        license_type=string_or_none(payload.metadata_json.get("license_type")) or "user_declared_upload",
        allow_training=bool(payload.metadata_json.get("allow_training", False)),
        allow_commercial_use=bool(payload.metadata_json.get("allow_commercial_use", True)),
        ai_disclosure_required=False,
    )
    asset = StyleSampleAsset(
        project_id=style_bible.project_id,
        style_bible_id=style_bible.id,
        filename=payload.filename,
        kind=payload.kind,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        storage_key=storage_key,
        metadata_json={
            **payload.metadata_json,
            "asset_id": str(catalog_asset.id),
            "rights_declaration_id": str(declaration.id),
        },
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


@router.put("/projects/{project_id}/active-style", response_model=StyleBibleLabRead)
def set_active_project_style(
    project_id: uuid.UUID,
    payload: ActiveStyleUpdate,
    session: Session = Depends(get_session),
) -> StyleBible:
    project = require_project(session, project_id)
    style_bible = require_style_bible(session, payload.style_bible_id)
    if style_bible.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Style bible does not belong to project")

    project.active_style_bible_id = style_bible.id
    touch(project)
    session.add(project)
    session.commit()
    session.refresh(style_bible)
    return style_bible


def require_project(session: Session, project_id: uuid.UUID) -> Project:
    return require_project_access(session, project_id)


def require_character_card(session: Session, character_id: uuid.UUID) -> CharacterCard:
    return require_character_card_access(session, character_id)


def require_style_bible(session: Session, style_bible_id: uuid.UUID) -> StyleBible:
    return require_style_bible_access(session, style_bible_id)


def validate_character_state_links(
    session: Session,
    card: CharacterCard,
    chapter_id: uuid.UUID,
    scene_id: uuid.UUID,
    page_id: uuid.UUID | None,
) -> None:
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")
    if chapter.project_id != card.project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chapter does not belong to character project")

    scene = session.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")
    if scene.chapter_id != chapter.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Scene does not belong to chapter")

    if page_id is not None:
        page = session.get(Page, page_id)
        if page is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
        if page.project_id != card.project_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Page does not belong to character project")


def merge_id(values: list[str], value: uuid.UUID) -> list[str]:
    return merge_ids(values, [value])


def merge_ids(values: list[str], ids: list[uuid.UUID]) -> list[str]:
    next_values = list(values)
    seen = set(next_values)
    for item in ids:
        item_id = str(item)
        if item_id not in seen:
            next_values.append(item_id)
            seen.add(item_id)
    return next_values


def normalize_uploaded_source_type(value: Any) -> str:
    if isinstance(value, str) and value in {"user_upload", "stock_licensed", "imported"}:
        return value
    return "user_upload"


def string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def style_preview_prompt(style_bible: StyleBible) -> str:
    fragments = [
        style_bible.style_name or style_bible.name,
        style_bible.style_intent,
        style_bible.line_weight or style_bible.linework,
        style_bible.face_shape_language or style_bible.face_language,
        style_bible.eye_design_language,
        style_bible.shadow_strategy or style_bible.black_white_balance,
        style_bible.panel_border_style or style_bible.panel_rhythm,
        ", ".join(style_bible.positive_prompt_fragments or []),
    ]
    return "Original manga style preview panel: " + "; ".join(item for item in fragments if item)


def render_style_preview_png(style_bible: StyleBible, preview_prompt: str) -> bytes:
    width, height = 768, 512
    image = Image.new("RGB", (width, height), color=(248, 248, 242))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    title = style_bible.style_name or style_bible.name

    draw.rectangle((0, 0, width - 1, height - 1), outline=(18, 18, 18), width=6)
    draw.rectangle((28, 30, 460, 470), outline=(18, 18, 18), width=4)
    draw.rectangle((488, 30, 738, 220), outline=(18, 18, 18), width=4)
    draw.rectangle((488, 250, 738, 470), outline=(18, 18, 18), width=4)

    for offset in range(-120, 520, 28):
        draw.line((488 + offset, 220, 738 + offset, 30), fill=(210, 210, 200), width=1)
    for offset in range(0, 300, 20):
        draw.line((500 + offset, 470, 738, 250 + offset), fill=(220, 220, 212), width=1)

    draw.ellipse((150, 112, 330, 292), outline=(18, 18, 18), width=5)
    draw.polygon([(230, 292), (190, 426), (330, 426)], outline=(18, 18, 18), fill=(30, 30, 30))
    draw.line((235, 85, 190, 115), fill=(18, 18, 18), width=5)
    draw.line((245, 85, 300, 112), fill=(18, 18, 18), width=5)
    draw.ellipse((200, 180, 226, 205), fill=(18, 18, 18))
    draw.ellipse((270, 180, 296, 205), fill=(18, 18, 18))
    draw.arc((215, 205, 285, 250), start=15, end=165, fill=(18, 18, 18), width=3)

    draw.rectangle((52, 52, 430, 104), fill=(255, 255, 255), outline=(18, 18, 18), width=3)
    draw.text((66, 68), title[:48], fill=(18, 18, 18), font=font)
    draw.text((504, 52), "Line", fill=(18, 18, 18), font=font)
    draw.text((504, 272), "Tone", fill=(18, 18, 18), font=font)
    for index, line in enumerate(wrap_text(preview_prompt, 58)[:5]):
        draw.text((52, 452 + index * 12), line, fill=(60, 60, 58), font=font)

    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def wrap_text(value: str, width: int) -> list[str]:
    words = value.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def generated_storage_key(prefix: str, owner_id: uuid.UUID, filename: str) -> str:
    return f"{prefix}/{owner_id}/{uuid.uuid4()}-{filename}"


def slug(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in cleaned.split("-") if part) or "character"
