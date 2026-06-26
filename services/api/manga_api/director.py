from __future__ import annotations

import uuid
from typing import Any, Protocol

from sqlmodel import Session, select

from manga_api.compositor import PageCompositor, get_latest_composite_asset
from manga_api.exporting import ProjectExporter
from manga_api.models import (
    Bubble,
    Chapter,
    Character,
    CharacterCard,
    GenerationJob,
    JobEvent,
    KeyObject,
    Location,
    Page,
    PagePlan,
    Panel,
    PanelPlan,
    Project,
    ProjectExport,
    Render,
    Scene,
    StoryBible,
    StyleBible,
)
from manga_api.qa import MockQAProvider, PageQAService, QAOptions, latest_qa_report
from manga_api.rendering import RenderOrchestrator
from manga_api.schemas import DirectorGenerateDraftRequest


class DirectorStorage(Protocol):
    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        """Persist bytes to object storage."""

    def get_bytes(self, key: str) -> bytes:
        """Read bytes from object storage."""

    def public_url(self, key: str) -> str:
        """Return a browser-accessible URL for a stored object."""


class MangaDirectorOrchestrator:
    def __init__(self, session: Session, storage: DirectorStorage) -> None:
        self.session = session
        self.storage = storage

    def generate_draft(self, job_id: uuid.UUID | str) -> GenerationJob:
        job = self._require_job(job_id)
        request = DirectorGenerateDraftRequest.model_validate(job.input_payload.get("request", {}))
        job.status = "running"
        job.error_message = None
        self._save_job(job)

        try:
            self._emit(job, "generating_story_bible", "Creating story bible from premise.")
            self._ensure_story_bible(job, request)

            self._emit(job, "generating_characters", "Creating characters, locations, and key objects.")
            self._ensure_characters_locations_objects(job, request)

            self._emit(job, "generating_style", "Creating active style bible.")
            self._ensure_style_bible(job, request)

            self._emit(job, "planning_pages", "Planning chapters, pages, and panels.")
            self._ensure_plans(job, request)

            self._emit(job, "creating_layouts", "Creating page layouts, panels, and bubbles.")
            self._ensure_layouts(job, request)

            self._emit(job, "rendering_panels", "Rendering panel drafts.")
            self._ensure_renders(job, request)

            self._emit(job, "composing_pages", "Composing final draft pages.")
            self._ensure_composites(job)

            self._emit(job, "running_qa", "Running page QA.")
            self._ensure_qa(job)

            self._emit(job, "exporting", "Creating draft ZIP export.")
            self._ensure_export(job)

            job.status = "succeeded"
            self._save_job(job)
            self._emit(job, "complete", "Director draft manga generation complete.", self._state(job))
            return job
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)[:4000]
            self._save_job(job)
            self._emit(job, "failed", str(exc)[:1000], self._state(job))
            return job

    def _ensure_story_bible(self, job: GenerationJob, request: DirectorGenerateDraftRequest) -> None:
        state = self._state(job)
        existing_id = state.get("story_bible_id")
        if existing_id and self.session.get(StoryBible, uuid.UUID(existing_id)):
            return

        project = self._require_project(job.project_id)
        genre = ", ".join(request.genre)
        story = StoryBible(
            project_id=project.id,
            logline=f"{project.name}: {request.premise}",
            synopsis=(
                f"{request.premise} The draft follows a compact manga structure with clear emotional turns, "
                f"visual continuity, and a {request.tone.lower()} tone for {request.target_audience}."
            ),
            genre=genre[:120] or "drama",
            themes=["protection", "identity", "choice", "survival"],
            target_audience=request.target_audience,
            tone=request.tone,
            main_conflict="The lead must protect a vulnerable companion while confronting the cost of isolation.",
            world_rules=[
                "Every major location reflects the protagonist's unresolved emotional state.",
                "Powerful moments require a visible consequence in the next scene.",
                "Character continuity must be preserved across all pages.",
            ],
            chapter_outline=[
                {
                    "chapter_number": index,
                    "title": f"Draft Chapter {index}",
                    "summary": f"Chapter {index} advances the premise through a focused manga sequence.",
                }
                for index in range(1, request.chapter_count + 1)
            ],
            continuity_rules=[
                "Keep silhouettes readable across panels.",
                "Do not change core outfits after page one without a story reason.",
                "Each page must include one clear emotional beat.",
            ],
        )
        self.session.add(story)
        self.session.commit()
        self.session.refresh(story)
        self._update_state(job, story_bible_id=str(story.id))

    def _ensure_characters_locations_objects(self, job: GenerationJob, request: DirectorGenerateDraftRequest) -> None:
        state = self._state(job)
        if state.get("character_card_ids") and state.get("location_ids") and state.get("key_object_ids"):
            return

        project = self._require_project(job.project_id)
        story_bible_id = uuid.UUID(state["story_bible_id"])
        archetypes = self._character_archetypes(request)
        story_character_ids: list[str] = []
        card_ids: list[str] = []
        for item in archetypes:
            character = Character(
                project_id=project.id,
                story_bible_id=story_bible_id,
                name=item["name"],
                role=item["role"],
                description=item["description"],
                traits=item["traits"],
                visual_notes=item["visual_notes"],
            )
            card = CharacterCard(
                project_id=project.id,
                name=item["name"],
                aliases=item["aliases"],
                age_range=item["age_range"],
                role=item["role"],
                personality=item["personality"],
                face_description=item["face_description"],
                hair_description=item["hair_description"],
                eye_description=item["eye_description"],
                body_type=item["body_type"],
                outfit_default=item["outfit_default"],
                accessories=item["accessories"],
                scars_marks=item["scars_marks"],
                voice_style=item["voice_style"],
                forbidden_changes=item["forbidden_changes"],
                continuity_rules=item["continuity_rules"],
            )
            self.session.add(character)
            self.session.add(card)
            self.session.flush()
            story_character_ids.append(str(character.id))
            card_ids.append(str(card.id))

        location = Location(
            project_id=project.id,
            story_bible_id=story_bible_id,
            name="Primary Story Location",
            description=f"The central setting shaped by the premise: {request.premise}",
            visual_notes="Strong establishing silhouettes, reusable landmarks, and readable depth layers.",
            rules=["The location must be recognizable across all generated pages."],
        )
        key_object = KeyObject(
            project_id=project.id,
            story_bible_id=story_bible_id,
            name="Continuity Anchor",
            description="A recurring object used to keep story and visual continuity connected.",
            significance="It gives the draft a repeatable visual motif for rendering and QA.",
            visual_notes="Simple, iconic, high-contrast shape visible in close-ups.",
        )
        self.session.add(location)
        self.session.add(key_object)
        self.session.commit()
        self.session.refresh(location)
        self.session.refresh(key_object)
        self._update_state(
            job,
            story_character_ids=story_character_ids,
            character_card_ids=card_ids,
            location_ids=[str(location.id)],
            key_object_ids=[str(key_object.id)],
        )

    def _ensure_style_bible(self, job: GenerationJob, request: DirectorGenerateDraftRequest) -> None:
        state = self._state(job)
        existing_id = state.get("style_bible_id")
        if existing_id and self.session.get(StyleBible, uuid.UUID(existing_id)):
            return

        project = self._require_project(job.project_id)
        story_bible_id = uuid.UUID(state["story_bible_id"])
        style = StyleBible(
            project_id=project.id,
            story_bible_id=story_bible_id,
            name="Director Draft Style",
            linework="Clean black manga linework with readable silhouettes.",
            screentone="Moderate screentone for mood and depth.",
            hatching="Directional hatching reserved for tension and texture.",
            black_white_balance="High contrast foregrounds with white gutters.",
            face_language="Expressive eyes and restrained mouth shapes.",
            anatomy_style="Grounded action manga proportions.",
            background_detail="Clear setting landmarks with selective detail.",
            panel_rhythm="Balanced page rhythm with one strong hero beat per page.",
            sfx_style="Hand-drawn effects integrated into panel action.",
            typography_notes="Clean dialogue, rectangular narration boxes, no unreadable generated text.",
            forbidden_references=["photorealism", "muddy grayscale", "illegible lettering"],
            prompt_style_positive=f"{', '.join(request.genre)} manga, {request.tone}, clean draft pages.",
            prompt_style_negative="muddy anatomy, cluttered panels, unreadable text.",
            visual_style=f"{request.tone} manga draft with strong continuity and readable page design.",
            line_art="Crisp lines with bold silhouettes.",
            palette="Black-and-white manga values.",
            paneling="Clear gutters and readable reading order.",
            lettering="Simple dialogue balloons and narration boxes.",
            negative_prompts=["muddy anatomy", "blank backgrounds", "unreadable text"],
        )
        self.session.add(style)
        self.session.flush()
        project.active_style_bible_id = style.id
        self.session.add(project)
        self.session.commit()
        self.session.refresh(style)
        self._update_state(job, style_bible_id=str(style.id))

    def _ensure_plans(self, job: GenerationJob, request: DirectorGenerateDraftRequest) -> None:
        state = self._state(job)
        if state.get("chapter_ids") and state.get("page_plan_ids") and state.get("panel_plan_ids"):
            return

        project = self._require_project(job.project_id)
        story_bible_id = uuid.UUID(state["story_bible_id"])
        chapter_ids: list[str] = []
        page_plan_ids: list[str] = []
        panel_plan_ids: list[str] = []

        chapters: list[Chapter] = []
        for index in range(1, request.chapter_count + 1):
            chapter = Chapter(
                project_id=project.id,
                story_bible_id=story_bible_id,
                chapter_number=index,
                title=f"Director Draft Chapter {index}",
                summary=f"Chapter {index} adapts the premise into sequential manga beats.",
                goal="Advance the emotional bond and visual conflict.",
            )
            self.session.add(chapter)
            self.session.flush()
            self.session.add(
                Scene(
                    chapter_id=chapter.id,
                    scene_order=1,
                    title=f"Chapter {index} Core Scene",
                    summary=f"A focused scene generated from: {request.premise}",
                    location_name="Primary Story Location",
                    emotional_turn="Distance becomes commitment.",
                    characters=["Lead Protector", "Vulnerable Companion"],
                )
            )
            chapters.append(chapter)
            chapter_ids.append(str(chapter.id))

        for page_number in range(1, request.page_count + 1):
            chapter = chapters[min(len(chapters) - 1, (page_number - 1) * len(chapters) // request.page_count)]
            page_plan = PagePlan(
                project_id=project.id,
                chapter_id=chapter.id,
                page_number=page_number,
                summary=f"Page {page_number} develops the draft premise with a clear setup and response beat.",
                pacing="fast" if request.quality_mode == "fast" else "balanced",
                panel_count=2,
            )
            self.session.add(page_plan)
            self.session.flush()
            page_plan_ids.append(str(page_plan.id))

            for order in [1, 2]:
                panel_plan = PanelPlan(
                    page_plan_id=page_plan.id,
                    panel_order=order,
                    story_beat=self._panel_story_beat(page_number, order, request),
                    shot_type="wide shot" if order == 1 else "medium close-up",
                    camera_angle="high angle" if order == 1 else "eye level",
                    characters=["Lead Protector", "Vulnerable Companion"] if order == 2 else ["Lead Protector"],
                    location="Primary Story Location",
                    dialogue=self._panel_dialogue(page_number, order),
                    narration=self._panel_narration(page_number, order),
                    visual_notes=f"Director draft page {page_number}, panel {order}, {request.tone.lower()} mood.",
                    emotional_intent="momentum" if order == 1 else "connection",
                )
                self.session.add(panel_plan)
                self.session.flush()
                panel_plan_ids.append(str(panel_plan.id))

        self.session.commit()
        self._update_state(job, chapter_ids=chapter_ids, page_plan_ids=page_plan_ids, panel_plan_ids=panel_plan_ids)

    def _ensure_layouts(self, job: GenerationJob, request: DirectorGenerateDraftRequest) -> None:
        state = self._state(job)
        if state.get("page_ids") and state.get("panel_ids") and state.get("bubble_ids"):
            return

        project = self._require_project(job.project_id)
        width, height = page_size_for_quality(request.quality_mode)
        page_ids: list[str] = []
        panel_ids: list[str] = []
        bubble_ids: list[str] = []

        page_plans = self.session.exec(
            select(PagePlan)
            .where(PagePlan.project_id == project.id)
            .order_by(PagePlan.page_number.asc())
        ).all()
        for page_plan in page_plans:
            page = Page(
                project_id=project.id,
                page_number=page_plan.page_number,
                width=width,
                height=height,
                layout_json={
                    "bleed": max(24, width // 32),
                    "safe_margin": max(48, width // 16),
                    "reading_direction": request.reading_direction,
                    "qa_overlay_enabled": False,
                    "director_job_id": str(job.id),
                },
            )
            self.session.add(page)
            self.session.flush()
            page_ids.append(str(page.id))

            panel_specs = panel_layout_specs(width, height)
            panel_plans = self.session.exec(
                select(PanelPlan)
                .where(PanelPlan.page_plan_id == page_plan.id)
                .order_by(PanelPlan.panel_order.asc())
            ).all()
            for panel_plan, panel_spec in zip(panel_plans, panel_specs, strict=False):
                panel = Panel(
                    page_id=page.id,
                    x=panel_spec["x"],
                    y=panel_spec["y"],
                    width=panel_spec["width"],
                    height=panel_spec["height"],
                    polygon=rect_polygon(panel_spec["x"], panel_spec["y"], panel_spec["width"], panel_spec["height"]),
                    reading_order=panel_plan.panel_order,
                    prompt=panel_plan.visual_notes,
                )
                self.session.add(panel)
                self.session.flush()
                panel_ids.append(str(panel.id))

                bubble_text = panel_plan.dialogue or panel_plan.narration or "..."
                bubble = Bubble(
                    panel_id=panel.id,
                    kind="speech" if panel_plan.dialogue else "narration",
                    x=panel.x + panel_spec["bubble_dx"],
                    y=panel.y + panel_spec["bubble_dy"],
                    width=panel_spec["bubble_width"],
                    height=panel_spec["bubble_height"],
                    text=bubble_text,
                )
                self.session.add(bubble)
                self.session.flush()
                bubble_ids.append(str(bubble.id))

        self.session.commit()
        self._update_state(job, page_ids=page_ids, panel_ids=panel_ids, bubble_ids=bubble_ids)

    def _ensure_renders(self, job: GenerationJob, request: DirectorGenerateDraftRequest) -> None:
        state = self._state(job)
        panel_ids = [uuid.UUID(value) for value in state.get("panel_ids", [])]
        if state.get("render_job_ids") and len(state["render_job_ids"]) >= len(panel_ids):
            return

        render_job_ids: list[str] = list(state.get("render_job_ids", []))
        orchestrator = RenderOrchestrator(self.session, self.storage)
        for index, panel_id in enumerate(panel_ids, start=1):
            existing = self._latest_successful_render(panel_id)
            if existing is not None:
                if str(existing.job_id) not in render_job_ids:
                    render_job_ids.append(str(existing.job_id))
                    self._update_state(job, render_job_ids=render_job_ids)
                continue

            render_job = orchestrator.render_panel(panel_id, request.render_provider, options={"seed": 41000 + index})
            if render_job.status == "failed" and request.allow_mock_assets and request.render_provider != "mock":
                render_job = orchestrator.render_panel(panel_id, "mock", options={"seed": 51000 + index, "fallback_from": request.render_provider})
            render_job_ids.append(str(render_job.id))
            self._update_state(job, render_job_ids=render_job_ids)
            if render_job.status == "failed":
                raise RuntimeError(render_job.error_message or f"Render failed for panel {panel_id}")

    def _ensure_composites(self, job: GenerationJob) -> None:
        state = self._state(job)
        page_ids = [uuid.UUID(value) for value in state.get("page_ids", [])]
        if state.get("composite_asset_ids") and len(state["composite_asset_ids"]) >= len(page_ids):
            return

        composite_asset_ids: list[str] = list(state.get("composite_asset_ids", []))
        compositor = PageCompositor(self.session, self.storage)
        for page_id in page_ids:
            existing = get_latest_composite_asset(self.session, page_id)
            if existing is not None:
                if str(existing.id) not in composite_asset_ids:
                    composite_asset_ids.append(str(existing.id))
                    self._update_state(job, composite_asset_ids=composite_asset_ids)
                continue
            composite = compositor.compose_page(page_id)
            composite_asset_ids.append(str(composite.asset.id))
            self._update_state(job, composite_asset_ids=composite_asset_ids)

    def _ensure_qa(self, job: GenerationJob) -> None:
        state = self._state(job)
        page_ids = [uuid.UUID(value) for value in state.get("page_ids", [])]
        if state.get("qa_report_ids") and len(state["qa_report_ids"]) >= len(page_ids):
            return

        qa_report_ids: list[str] = list(state.get("qa_report_ids", []))
        service = PageQAService(self.session, MockQAProvider())
        for page_id in page_ids:
            existing = latest_qa_report(self.session, "page", page_id)
            if existing is not None and str(existing.id) not in qa_report_ids:
                qa_report_ids.append(str(existing.id))
                self._update_state(job, qa_report_ids=qa_report_ids)
                continue
            report = service.run_page_qa(page_id, QAOptions(export_preset="draft"))
            qa_report_ids.append(str(report.id))
            self._update_state(job, qa_report_ids=qa_report_ids)

    def _ensure_export(self, job: GenerationJob) -> None:
        state = self._state(job)
        existing_id = state.get("draft_export_id")
        if existing_id:
            existing = self.session.get(ProjectExport, uuid.UUID(existing_id))
            if existing is not None and existing.status == "succeeded":
                return

        export = ProjectExporter(self.session, self.storage).export_project(
            self._require_project(job.project_id).id,
            "zip",
            force=False,
            options={"source": "director_mode", "job_id": str(job.id)},
        )
        self._update_state(job, draft_export_id=str(export.id))
        if export.status != "succeeded":
            raise RuntimeError(export.error_message or "Director draft export failed")

    def _latest_successful_render(self, panel_id: uuid.UUID) -> Render | None:
        row = self.session.exec(
            select(Render, GenerationJob)
            .join(GenerationJob, GenerationJob.id == Render.job_id)
            .where(Render.panel_id == panel_id, GenerationJob.status == "succeeded")
            .order_by(Render.created_at.desc())
        ).first()
        return row[0] if row is not None else None

    def _character_archetypes(self, request: DirectorGenerateDraftRequest) -> list[dict[str, Any]]:
        return [
            {
                "name": "Lead Protector",
                "aliases": ["Director Lead"],
                "age_range": "young adult",
                "role": "Protagonist and protector",
                "description": f"The central lead shaped by the premise: {request.premise}",
                "traits": ["guarded", "capable", "protective"],
                "personality": "Reserved, competent, emotionally cautious, and increasingly protective.",
                "face_description": "Sharp, focused face with tired eyes.",
                "hair_description": "Practical, slightly messy hair suited for action scenes.",
                "eye_description": "Watchful eyes that soften around the companion.",
                "body_type": "Lean action-manga build.",
                "outfit_default": "Layered travel outfit with one iconic silhouette element.",
                "accessories": ["signature weapon", "worn travel item"],
                "scars_marks": "Small mark that suggests a difficult past.",
                "voice_style": "Short, direct, emotionally restrained.",
                "visual_notes": "Readable silhouette, strong protective poses.",
                "forbidden_changes": ["Do not remove the protector silhouette."],
                "continuity_rules": ["Always frame the lead as aware of threats."],
            },
            {
                "name": "Vulnerable Companion",
                "aliases": ["Director Companion"],
                "age_range": "child or teen",
                "role": "Emotional anchor and protected companion",
                "description": "The vulnerable character who gives the lead a reason to choose connection.",
                "traits": ["quiet", "brave", "observant"],
                "personality": "Gentle, watchful, and stronger than first impressions suggest.",
                "face_description": "Soft face with large expressive eyes.",
                "hair_description": "Simple, recognizable hair shape.",
                "eye_description": "Reflective eyes with a recurring highlight motif.",
                "body_type": "Small, readable companion silhouette.",
                "outfit_default": "Simple outfit with one recurring prop or motif.",
                "accessories": ["continuity anchor object"],
                "scars_marks": "Subtle visual hint of vulnerability.",
                "voice_style": "Soft, sparse, emotionally clear.",
                "visual_notes": "Keep poses simple and emotionally readable.",
                "forbidden_changes": ["Do not make the companion visually generic."],
                "continuity_rules": ["The companion should remain near the continuity anchor object."],
            },
        ]

    def _panel_story_beat(self, page_number: int, order: int, request: DirectorGenerateDraftRequest) -> str:
        if order == 1:
            return f"Page {page_number} establishes a new visual pressure from the premise."
        return f"Page {page_number} turns that pressure into a character choice."

    def _panel_dialogue(self, page_number: int, order: int) -> str | None:
        if order == 2:
            return "We keep going."
        if page_number == 1:
            return "Something is watching."
        return None

    def _panel_narration(self, page_number: int, order: int) -> str | None:
        if order == 1:
            return f"Page {page_number}: the road narrows."
        return None

    def _require_job(self, job_id: uuid.UUID | str) -> GenerationJob:
        job = self.session.get(GenerationJob, uuid.UUID(str(job_id)))
        if job is None:
            raise ValueError("Director job not found")
        return job

    def _require_project(self, project_id: uuid.UUID | None) -> Project:
        if project_id is None:
            raise ValueError("Director job is missing project id")
        project = self.session.get(Project, project_id)
        if project is None:
            raise ValueError("Director project not found")
        return project

    def _state(self, job: GenerationJob) -> dict[str, Any]:
        output = job.output_payload if isinstance(job.output_payload, dict) else {}
        state = output.get("director_state", {})
        return dict(state) if isinstance(state, dict) else {}

    def _update_state(self, job: GenerationJob, **updates: Any) -> None:
        output = dict(job.output_payload or {})
        state = self._state(job)
        state.update(updates)
        output["director_state"] = state
        job.output_payload = output
        self._save_job(job)

    def _save_job(self, job: GenerationJob) -> None:
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)

    def _emit(self, job: GenerationJob, event_type: str, message: str, payload: dict[str, Any] | None = None) -> None:
        event = JobEvent(
            job_id=job.id,
            event_type=event_type,
            message=message,
            payload=payload or {},
        )
        self.session.add(event)
        self.session.commit()


def page_size_for_quality(quality_mode: str) -> tuple[int, int]:
    if quality_mode == "high":
        return 1600, 2400
    if quality_mode == "fast":
        return 800, 1200
    return 1000, 1500


def panel_layout_specs(width: int, height: int) -> list[dict[str, int]]:
    margin_x = max(60, width // 12)
    top = max(80, height // 15)
    panel_width = width - margin_x * 2
    first_height = int(height * 0.37)
    second_y = top + first_height + max(70, height // 16)
    second_height = height - second_y - top
    return [
        {
            "x": margin_x,
            "y": top,
            "width": panel_width,
            "height": first_height,
            "bubble_dx": max(30, width // 25),
            "bubble_dy": max(24, height // 50),
            "bubble_width": max(220, width // 3),
            "bubble_height": max(84, height // 14),
        },
        {
            "x": margin_x,
            "y": second_y,
            "width": panel_width,
            "height": second_height,
            "bubble_dx": int(panel_width * 0.55),
            "bubble_dy": max(36, height // 42),
            "bubble_width": max(220, width // 3),
            "bubble_height": max(96, height // 12),
        },
    ]


def rect_polygon(x: int, y: int, width: int, height: int) -> list[dict[str, int]]:
    return [
        {"x": x, "y": y},
        {"x": x + width, "y": y},
        {"x": x + width, "y": y + height},
        {"x": x, "y": y + height},
    ]
