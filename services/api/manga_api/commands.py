from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from manga_api.compositor import PageCompositor, StorageClient
from manga_api.exporting import ProjectExporter
from manga_api.models import (
    Bubble,
    Chapter,
    CharacterCard,
    CommandHistory,
    GenerationJob,
    Page,
    Panel,
    Project,
    StoryBible,
    StyleBible,
)
from manga_api.panel_render_director import PanelRenderDirector
from manga_api.qa import MockQAProvider, PageQAService, QAOptions
from manga_api.qa_autofix import AutoFixService
from manga_api.rendering import RenderOrchestrator
from manga_api.schemas import (
    CommandAction,
    CommandExecuteRequest,
    CommandExecuteResult,
    CommandInterpretRequest,
    CommandInterpretResult,
)
from manga_api.versioning import VersioningService


DESTRUCTIVE_WORDS = {
    "delete",
    "discard",
    "erase",
    "remove",
    "reset",
    "replace all",
    "replace entire",
    "start over",
    "wipe",
}


class CommandInterpreter:
    def __init__(self, session: Session, storage: StorageClient | None = None) -> None:
        self.session = session
        self.storage = storage

    def interpret(self, request: CommandInterpretRequest, *, persist: bool = False) -> CommandInterpretResult:
        project = self._require_project(request.project_id)
        self._validate_scope(project.id, request.scope.type, request.scope.id)
        command = request.command.strip()
        normalized = normalize_command(command)
        target_type, target_id = self._resolve_primary_target(project.id, request.scope.type, request.scope.id, normalized)
        intent, actions, risk_level, summary = self._classify(project.id, target_type, target_id, command, normalized)
        requires_confirmation = risk_level == "high" or any(action.destructive for action in actions)

        result = CommandInterpretResult(
            command_id=None,
            project_id=project.id,
            intent=intent,
            target_type=target_type,
            target_id=str(target_id),
            proposed_actions=actions,
            requires_confirmation=requires_confirmation,
            risk_level=risk_level,
            summary=summary,
        )
        if persist:
            history = self._store_history(
                request,
                result,
                status="interpreted",
                confirmed=False,
                executed_actions=[],
                version_ids=[],
                error_message=None,
            )
            result.command_id = history.id
        return result

    def execute(self, request: CommandExecuteRequest) -> CommandExecuteResult:
        interpretation = self.interpret(
            CommandInterpretRequest(project_id=request.project_id, scope=request.scope, command=request.command),
            persist=False,
        )
        history = self._store_history(
            request,
            interpretation,
            status="blocked" if interpretation.requires_confirmation and not request.confirmed else "interpreted",
            confirmed=request.confirmed,
            executed_actions=[],
            version_ids=[],
            error_message=None,
        )
        interpretation.command_id = history.id

        if interpretation.requires_confirmation and not request.confirmed:
            return self._execution_result(
                interpretation,
                history,
                status="blocked",
                executed_actions=[],
                version_ids=[],
                error_message="This command is high risk and requires confirmation before execution.",
            )

        executed_actions: list[dict[str, Any]] = []
        version_ids: list[str] = []
        try:
            for action in interpretation.proposed_actions:
                result = self._execute_action(action, request.command)
                executed_actions.append(result)
                version_ids.extend(result.get("version_ids", []))
            if not executed_actions:
                executed_actions.append(
                    {
                        "action_type": "none",
                        "status": "skipped",
                        "message": "No executable action was identified for this command.",
                    }
                )
            return self._execution_result(
                interpretation,
                history,
                status="executed",
                executed_actions=executed_actions,
                version_ids=version_ids,
                error_message=None,
            )
        except Exception as exc:
            return self._execution_result(
                interpretation,
                history,
                status="failed",
                executed_actions=executed_actions,
                version_ids=version_ids,
                error_message=str(exc),
            )

    def _classify(
        self,
        project_id: uuid.UUID,
        target_type: str,
        target_id: uuid.UUID,
        command: str,
        normalized: str,
    ) -> tuple[str, list[CommandAction], str, str]:
        if any(word in normalized for word in DESTRUCTIVE_WORDS):
            return (
                "destructive_edit_request",
                [
                    CommandAction(
                        action_type="update_layout" if target_type in {"page", "panel", "bubble"} else "update_story_bible",
                        target_type=target_type,
                        target_id=str(target_id),
                        summary="Potentially destructive edit; a version snapshot is required before any change.",
                        payload={"command": command},
                        destructive=True,
                    )
                ],
                "high",
                "This command may remove or overwrite user work, so Manga AI Studio will only preview it until confirmed.",
            )

        if "qa" in normalized and any(word in normalized for word in ["fix", "repair", "resolve", "all"]):
            page_id = self._target_page_id(project_id, target_type, target_id)
            return (
                "fix_qa_issues",
                [
                    CommandAction(
                        action_type="run_qa",
                        target_type="page",
                        target_id=str(page_id),
                        summary="Run deterministic QA on the target page.",
                        payload={"provider_name": "mock"},
                    ),
                    CommandAction(
                        action_type="apply_qa_fixes",
                        target_type="page",
                        target_id=str(page_id),
                        summary="Apply safe QA fixes for layout, lettering, prompts, and missing composition.",
                        payload={"safe_only": True},
                    ),
                ],
                "medium",
                "I will run QA, create snapshots, and apply only safe automatic fixes on the current page.",
            )

        if "qa" in normalized or "quality" in normalized or "review" in normalized:
            page_id = self._target_page_id(project_id, target_type, target_id)
            return (
                "run_quality_check",
                [
                    CommandAction(
                        action_type="run_qa",
                        target_type="page",
                        target_id=str(page_id),
                        summary="Run deterministic QA on the target page.",
                        payload={"provider_name": "mock"},
                    )
                ],
                "low",
                "I will run a deterministic QA pass and store the report.",
            )

        if "bubble" in normalized and any(word in normalized for word in ["move", "shift", "away", "face"]):
            bubble_id = self._target_bubble_id(project_id, target_type, target_id)
            return (
                "move_lettering",
                [
                    CommandAction(
                        action_type="move_bubble",
                        target_type="bubble",
                        target_id=str(bubble_id),
                        summary="Move the selected bubble while keeping it inside the page.",
                        payload={"strategy": "away_from_center"},
                    )
                ],
                "low",
                "I will move the bubble to a safer readable position and snapshot the lettering first.",
            )

        if "dialogue" in normalized and any(word in normalized for word in ["short", "shorter", "tighten", "trim"]):
            bubble_target_type, bubble_target_id = self._target_bubble_or_page(project_id, target_type, target_id)
            return (
                "tighten_dialogue",
                [
                    CommandAction(
                        action_type="update_bubble_text",
                        target_type=bubble_target_type,
                        target_id=str(bubble_target_id),
                        summary="Shorten dialogue text while preserving the meaning.",
                        payload={"operation": "shorten"},
                    )
                ],
                "low",
                "I will shorten the target lettering and snapshot the previous lettering layer.",
            )

        if any(word in normalized for word in ["regenerate", "rerender", "render"]) and "panel" in normalized:
            panel_id = self._target_panel_id(project_id, target_type, target_id, normalized)
            camera_instruction = "low-angle shot" if "low angle" in normalized or "low-angle" in normalized else None
            return (
                "rerender_panel",
                [
                    CommandAction(
                        action_type="update_panel_prompt",
                        target_type="panel",
                        target_id=str(panel_id),
                        summary="Add the command instruction to the panel prompt.",
                        payload={"instruction": command, "camera_instruction": camera_instruction},
                    ),
                    CommandAction(
                        action_type="rerender_panel",
                        target_type="panel",
                        target_id=str(panel_id),
                        summary="Render a new mock draft for the target panel.",
                        payload={"provider_name": "mock", "render_mode": "draft", "camera_instruction": camera_instruction},
                    ),
                ],
                "medium",
                "I will preserve the layout, update the panel prompt, and create a new render attempt.",
            )

        if "compose" in normalized:
            page_id = self._target_page_id(project_id, target_type, target_id)
            return (
                "compose_page",
                [
                    CommandAction(
                        action_type="compose_page",
                        target_type="page",
                        target_id=str(page_id),
                        summary="Compose the page from panel renders and lettering.",
                        payload={},
                    )
                ],
                "low",
                "I will compose the target page into a final PNG asset.",
            )

        if "export" in normalized:
            return (
                "create_export",
                [
                    CommandAction(
                        action_type="create_export",
                        target_type="project",
                        target_id=str(project_id),
                        summary="Create a ZIP export with current project metadata and assets.",
                        payload={"format": "zip", "force": True},
                    )
                ],
                "low",
                "I will create a ZIP export package for the project.",
            )

        if any(word in normalized for word in ["layout", "webtoon", "horror reveal", "dramatic", "splash", "silence"]):
            page_id = self._target_page_id(project_id, target_type, target_id)
            page_type = "horror_build" if "horror" in normalized else "reveal_page" if "reveal" in normalized else "standard"
            if "webtoon" in normalized:
                page_type = "vertical_scroll"
            return (
                "revise_page_direction",
                [
                    CommandAction(
                        action_type="suggest_layout",
                        target_type="page",
                        target_id=str(page_id),
                        summary="Suggest a layout direction for the page.",
                        payload={"page_type": page_type, "instruction": command},
                    ),
                    CommandAction(
                        action_type="update_panel_prompt",
                        target_type="page",
                        target_id=str(page_id),
                        summary="Add the page-level creative direction to panel prompts.",
                        payload={"instruction": command},
                    ),
                ],
                "medium",
                "I will preserve existing panels, attach the new page direction, and leave layout replacement as a reviewed suggestion.",
            )

        if target_type == "character" or any(word in normalized for word in ["tired", "injury", "outfit", "emotion"]):
            character_id = self._target_character_id(project_id, target_type, target_id, normalized)
            return (
                "update_character_state",
                [
                    CommandAction(
                        action_type="update_character_state",
                        target_type="character",
                        target_id=str(character_id),
                        summary="Update the character continuity state.",
                        payload={"instruction": command},
                    )
                ],
                "medium",
                "I will update the character state notes and snapshot the character card first.",
            )

        if target_type == "style" or "style" in normalized or "dna" in normalized:
            style_id = self._target_style_id(project_id, target_type, target_id)
            return (
                "update_style_dna",
                [
                    CommandAction(
                        action_type="update_style_dna",
                        target_type="style",
                        target_id=str(style_id),
                        summary="Append the requested style adjustment to the active Style DNA notes.",
                        payload={"instruction": command},
                    )
                ],
                "medium",
                "I will update the active style bible with the requested original style direction.",
            )

        return (
            "capture_direction",
            [
                CommandAction(
                    action_type="update_panel_prompt" if target_type in {"panel", "page"} else "update_story_bible",
                    target_type=target_type,
                    target_id=str(target_id),
                    summary="Capture the instruction as editable project direction.",
                    payload={"instruction": command},
                )
            ],
            "medium",
            "I will capture this as project direction without deleting or replacing existing work.",
        )

    def _execute_action(self, action: CommandAction, command: str) -> dict[str, Any]:
        action_type = str(action.action_type)
        if action_type == "move_bubble":
            return self._execute_move_bubble(action)
        if action_type == "update_bubble_text":
            return self._execute_update_bubble_text(action)
        if action_type == "run_qa":
            return self._execute_run_qa(action)
        if action_type == "apply_qa_fixes":
            return self._execute_apply_qa_fixes(action)
        if action_type == "compose_page":
            return self._execute_compose_page(action)
        if action_type == "create_export":
            return self._execute_create_export(action)
        if action_type == "update_panel_prompt":
            return self._execute_update_panel_prompt(action, command)
        if action_type == "rerender_panel":
            return self._execute_rerender_panel(action, command)
        if action_type == "update_character_state":
            return self._execute_update_character_state(action, command)
        if action_type == "update_style_dna":
            return self._execute_update_style_dna(action, command)
        if action_type == "suggest_layout":
            return self._execute_suggest_layout(action)
        if action_type == "update_story_bible":
            return self._execute_update_story_bible(action, command)
        return {
            "action_type": action_type,
            "status": "skipped",
            "message": f"Command action {action_type} is not executable yet.",
            "version_ids": [],
        }

    def _execute_move_bubble(self, action: CommandAction) -> dict[str, Any]:
        bubble = self._require(Bubble, action.target_id, "Bubble not found")
        page = self._page_for_bubble(bubble)
        version = VersioningService(self.session).create_snapshot(
            page,
            entity_type="lettering",
            label=f"Page {page.page_number} lettering before command",
            reason="command_move_bubble",
        )
        before = bubble_geometry(bubble)
        margin = int((page.layout_json or {}).get("safe_margin", 80))
        left_space = bubble.x
        right_space = max(0, page.width - (bubble.x + bubble.width))
        next_x = margin if right_space < left_space else max(margin, page.width - bubble.width - margin)
        next_y = max(margin, min(page.height - bubble.height - margin, bubble.y - 120 if bubble.y > page.height / 3 else bubble.y + 120))
        bubble.x = int(max(0, min(page.width - bubble.width, next_x)))
        bubble.y = int(max(0, min(page.height - bubble.height, next_y)))
        bubble.position = {"x": bubble.x, "y": bubble.y}
        bubble.size = {"width": bubble.width, "height": bubble.height}
        touch(bubble)
        self.session.add(bubble)
        self.session.commit()
        return {
            "action_type": "move_bubble",
            "status": "applied",
            "target_type": "bubble",
            "target_id": str(bubble.id),
            "message": "Moved bubble while keeping it inside page bounds.",
            "before": before,
            "after": bubble_geometry(bubble),
            "version_ids": [str(version.id)],
        }

    def _execute_update_bubble_text(self, action: CommandAction) -> dict[str, Any]:
        bubbles = self._bubbles_for_action(action)
        if not bubbles:
            raise ValueError("No bubbles found for dialogue update")
        page = self._page_for_bubble(bubbles[0])
        version = VersioningService(self.session).create_snapshot(
            page,
            entity_type="lettering",
            label=f"Page {page.page_number} lettering before command",
            reason="command_update_bubble_text",
        )
        changed: list[dict[str, Any]] = []
        for bubble in bubbles:
            before = bubble.text
            bubble.text = shorten_text(bubble.text)
            touch(bubble)
            self.session.add(bubble)
            changed.append({"bubble_id": str(bubble.id), "before": before, "after": bubble.text})
        self.session.commit()
        return {
            "action_type": "update_bubble_text",
            "status": "applied",
            "target_type": action.target_type,
            "target_id": action.target_id,
            "message": "Shortened dialogue text.",
            "changes": changed,
            "version_ids": [str(version.id)],
        }

    def _execute_run_qa(self, action: CommandAction) -> dict[str, Any]:
        page_id = uuid.UUID(str(action.target_id))
        report = PageQAService(self.session, MockQAProvider()).run_page_qa(page_id, QAOptions())
        return {
            "action_type": "run_qa",
            "status": "applied",
            "target_type": "page",
            "target_id": str(page_id),
            "message": f"QA complete with score {report.overall_score}.",
            "qa_report_id": str(report.id),
            "blocking": report.blocking,
            "version_ids": [],
        }

    def _execute_apply_qa_fixes(self, action: CommandAction) -> dict[str, Any]:
        page = self._require(Page, action.target_id, "Page not found")
        versioning = VersioningService(self.session)
        layout_version = versioning.create_snapshot(page, entity_type="layout", label="Layout before command QA fix", reason="command_apply_qa_fixes")
        lettering_version = versioning.create_snapshot(page, entity_type="lettering", label="Lettering before command QA fix", reason="command_apply_qa_fixes")
        result = AutoFixService(self.session, self.storage).auto_fix_page_safe(page.id)
        return {
            "action_type": "apply_qa_fixes",
            "status": "applied",
            "target_type": "page",
            "target_id": str(page.id),
            "message": f"Applied {len(result.get('applied', []))} safe QA fixes.",
            "applied": result.get("applied", []),
            "skipped": result.get("skipped", []),
            "version_ids": [str(layout_version.id), str(lettering_version.id)],
        }

    def _execute_compose_page(self, action: CommandAction) -> dict[str, Any]:
        if self.storage is None:
            raise ValueError("Object storage is not available for composition")
        page_id = uuid.UUID(str(action.target_id))
        result = PageCompositor(self.session, self.storage).compose_page(page_id)
        return {
            "action_type": "compose_page",
            "status": "applied",
            "target_type": "page",
            "target_id": str(page_id),
            "message": "Composed final page image.",
            "asset_id": str(result.asset.id),
            "version_ids": [],
        }

    def _execute_create_export(self, action: CommandAction) -> dict[str, Any]:
        if self.storage is None:
            raise ValueError("Object storage is not available for export")
        export_format = str(action.payload.get("format") or "zip")
        export = ProjectExporter(self.session, self.storage).export_project(
            uuid.UUID(str(action.target_id)),
            export_format,
            force=bool(action.payload.get("force", True)),
            options={"source": "command_center"},
        )
        return {
            "action_type": "create_export",
            "status": "applied",
            "target_type": "project",
            "target_id": action.target_id,
            "message": f"Created {export.format.upper()} export.",
            "export_id": str(export.id),
            "version_ids": [],
        }

    def _execute_update_panel_prompt(self, action: CommandAction, command: str) -> dict[str, Any]:
        targets = self._panels_for_prompt_action(action)
        version_ids: list[str] = []
        changes: list[dict[str, Any]] = []
        for panel in targets:
            version = VersioningService(self.session).create_snapshot(
                panel,
                label=f"Panel {panel.reading_order} before command prompt edit",
                reason="command_update_panel_prompt",
            )
            before = panel.prompt or ""
            addition = f"[Command Center] {command.strip()}"
            panel.prompt = append_text(before, addition, limit=4000)
            touch(panel)
            self.session.add(panel)
            version_ids.append(str(version.id))
            changes.append({"panel_id": str(panel.id), "before": before, "after": panel.prompt})
        self.session.commit()
        return {
            "action_type": "update_panel_prompt",
            "status": "applied",
            "target_type": action.target_type,
            "target_id": action.target_id,
            "message": f"Updated {len(targets)} panel prompt(s).",
            "changes": changes,
            "version_ids": version_ids,
        }

    def _execute_rerender_panel(self, action: CommandAction, command: str) -> dict[str, Any]:
        if self.storage is None:
            raise ValueError("Object storage is not available for rendering")
        panel = self._require(Panel, action.target_id, "Panel not found")
        page = self._require(Page, panel.page_id, "Page not found")
        prompt = PanelRenderDirector(self.session).build_prompt(
            panel.id,
            provider_name="mock",
            render_mode=str(action.payload.get("render_mode") or "draft"),
            additional_user_instruction=command,
            camera_instruction=action.payload.get("camera_instruction"),
            preserve_layout=True,
        )
        job = GenerationJob(
            project_id=page.project_id,
            page_id=page.id,
            panel_id=panel.id,
            provider="mock",
            job_type="render_panel",
            status="queued",
            input_payload={"panel_render_prompt_id": str(prompt.id), "source": "command_center"},
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        rendered_job = RenderOrchestrator(self.session, self.storage).render_panel(
            panel.id,
            "mock",
            options={"panel_render_prompt_id": str(prompt.id), "render_mode": prompt.quality_mode, "quality_mode": prompt.quality_mode},
            job=job,
        )
        return {
            "action_type": "rerender_panel",
            "status": rendered_job.status,
            "target_type": "panel",
            "target_id": str(panel.id),
            "message": "Created a new mock render attempt." if rendered_job.status == "succeeded" else rendered_job.error_message,
            "job_id": str(rendered_job.id),
            "asset_id": (rendered_job.output_payload or {}).get("asset_id"),
            "version_ids": [],
        }

    def _execute_update_character_state(self, action: CommandAction, command: str) -> dict[str, Any]:
        character = self._require(CharacterCard, action.target_id, "Character not found")
        version = VersioningService(self.session).create_snapshot(
            character,
            label=f"{character.name} before command state edit",
            reason="command_update_character_state",
        )
        before = character.current_story_state
        character.current_story_state = append_text(character.current_story_state, command.strip(), limit=2000)
        if "tired" in normalize_command(command):
            character.emotional_baseline = append_text(character.emotional_baseline, "Looks more tired in this scene.", limit=2000)
        touch(character)
        self.session.add(character)
        self.session.commit()
        return {
            "action_type": "update_character_state",
            "status": "applied",
            "target_type": "character",
            "target_id": str(character.id),
            "message": f"Updated {character.name}'s continuity state.",
            "before": before,
            "after": character.current_story_state,
            "version_ids": [str(version.id)],
        }

    def _execute_update_style_dna(self, action: CommandAction, command: str) -> dict[str, Any]:
        style = self._require(StyleBible, action.target_id, "Style bible not found")
        version = VersioningService(self.session).create_snapshot(
            style,
            label=f"{style.name} before command style edit",
            reason="command_update_style_dna",
        )
        before = style.style_intent
        style.style_intent = append_text(style.style_intent, command.strip(), limit=3000)
        touch(style)
        self.session.add(style)
        self.session.commit()
        return {
            "action_type": "update_style_dna",
            "status": "applied",
            "target_type": "style",
            "target_id": str(style.id),
            "message": "Updated active Style DNA notes.",
            "before": before,
            "after": style.style_intent,
            "version_ids": [str(version.id)],
        }

    def _execute_suggest_layout(self, action: CommandAction) -> dict[str, Any]:
        page = self._require(Page, action.target_id, "Page not found")
        version = VersioningService(self.session).create_snapshot(
            page,
            entity_type="layout",
            label=f"Page {page.page_number} layout before command suggestion",
            reason="command_suggest_layout",
        )
        layout_json = dict(page.layout_json or {})
        suggestions = list(layout_json.get("command_suggestions") or [])
        suggestions.append(
            {
                "instruction": action.payload.get("instruction", ""),
                "page_type": action.payload.get("page_type", "standard"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        layout_json["command_suggestions"] = suggestions[-10:]
        page.layout_json = layout_json
        touch(page)
        self.session.add(page)
        self.session.commit()
        return {
            "action_type": "suggest_layout",
            "status": "applied",
            "target_type": "page",
            "target_id": str(page.id),
            "message": "Stored a layout suggestion for review.",
            "version_ids": [str(version.id)],
        }

    def _execute_update_story_bible(self, action: CommandAction, command: str) -> dict[str, Any]:
        story = self.session.exec(
            select(StoryBible)
            .where(StoryBible.project_id == uuid.UUID(str(action.target_id)) if action.target_type == "project" else StoryBible.id == uuid.UUID(str(action.target_id)))
            .order_by(StoryBible.created_at.desc())
        ).first()
        if story is None:
            return {
                "action_type": "update_story_bible",
                "status": "skipped",
                "message": "No story bible exists yet.",
                "version_ids": [],
            }
        version = VersioningService(self.session).create_snapshot(
            story,
            label="Story bible before command edit",
            reason="command_update_story_bible",
        )
        before = list(story.continuity_rules)
        story.continuity_rules = [*story.continuity_rules, f"Command direction: {command.strip()}"][-50:]
        touch(story)
        self.session.add(story)
        self.session.commit()
        return {
            "action_type": "update_story_bible",
            "status": "applied",
            "target_type": "story_bible",
            "target_id": str(story.id),
            "message": "Stored the command as a continuity rule.",
            "before": before,
            "after": story.continuity_rules,
            "version_ids": [str(version.id)],
        }

    def _execution_result(
        self,
        interpretation: CommandInterpretResult,
        history: CommandHistory,
        *,
        status: str,
        executed_actions: list[dict[str, Any]],
        version_ids: list[str],
        error_message: str | None,
    ) -> CommandExecuteResult:
        history.status = status
        history.executed_actions = executed_actions
        history.version_ids = dedupe(version_ids)
        history.error_message = error_message
        touch(history)
        self.session.add(history)
        self.session.commit()
        self.session.refresh(history)
        return CommandExecuteResult(
            **interpretation.model_dump(exclude={"command_id"}),
            command_id=history.id,
            status=status,
            executed_actions=executed_actions,
            version_ids=history.version_ids,
            error_message=error_message,
        )

    def _store_history(
        self,
        request: CommandInterpretRequest,
        result: CommandInterpretResult,
        *,
        status: str,
        confirmed: bool,
        executed_actions: list[dict[str, Any]],
        version_ids: list[str],
        error_message: str | None,
    ) -> CommandHistory:
        history = CommandHistory(
            project_id=result.project_id,
            scope_type=request.scope.type,
            scope_id=str(request.scope.id),
            command=request.command.strip(),
            intent=result.intent,
            target_type=result.target_type,
            target_id=result.target_id,
            proposed_actions=[action.model_dump(mode="json") for action in result.proposed_actions],
            executed_actions=executed_actions,
            requires_confirmation=result.requires_confirmation,
            confirmed=confirmed,
            risk_level=str(result.risk_level),
            status=status,
            summary=result.summary,
            error_message=error_message,
            version_ids=dedupe(version_ids),
        )
        self.session.add(history)
        self.session.commit()
        self.session.refresh(history)
        return history

    def _resolve_primary_target(self, project_id: uuid.UUID, scope_type: str, scope_id: uuid.UUID, normalized: str) -> tuple[str, uuid.UUID]:
        page_number = command_page_number(normalized)
        if page_number is not None:
            page = self.session.exec(
                select(Page).where(Page.project_id == project_id, Page.page_number == page_number)
            ).first()
            if page is not None:
                return "page", page.id
        if "panel" in normalized:
            return "panel", self._target_panel_id(project_id, scope_type, scope_id, normalized)
        if "bubble" in normalized or "dialogue" in normalized:
            try:
                return "bubble", self._target_bubble_id(project_id, scope_type, scope_id)
            except ValueError:
                return "page", self._target_page_id(project_id, scope_type, scope_id)
        if scope_type in {"project", "chapter", "page", "panel", "bubble", "character", "style"}:
            return scope_type, scope_id
        return "project", project_id

    def _validate_scope(self, project_id: uuid.UUID, scope_type: str, scope_id: uuid.UUID) -> None:
        if scope_type == "project":
            if project_id != scope_id:
                raise ValueError("Scope project does not match command project")
            return
        if scope_type == "page":
            page = self._require(Page, scope_id, "Page not found")
            if page.project_id != project_id:
                raise ValueError("Page does not belong to project")
            return
        if scope_type == "panel":
            panel = self._require(Panel, scope_id, "Panel not found")
            page = self._require(Page, panel.page_id, "Page not found")
            if page.project_id != project_id:
                raise ValueError("Panel does not belong to project")
            return
        if scope_type == "bubble":
            bubble = self._require(Bubble, scope_id, "Bubble not found")
            page = self._page_for_bubble(bubble)
            if page.project_id != project_id:
                raise ValueError("Bubble does not belong to project")
            return
        if scope_type == "character":
            character = self._require(CharacterCard, scope_id, "Character not found")
            if character.project_id != project_id:
                raise ValueError("Character does not belong to project")
            return
        if scope_type == "style":
            style = self._require(StyleBible, scope_id, "Style bible not found")
            if style.project_id != project_id:
                raise ValueError("Style bible does not belong to project")
            return
        if scope_type == "chapter":
            chapter = self._require(Chapter, scope_id, "Chapter not found")
            if chapter.project_id != project_id:
                raise ValueError("Chapter does not belong to project")
            return
        raise ValueError(f"Unsupported command scope: {scope_type}")

    def _target_page_id(self, project_id: uuid.UUID, target_type: str, target_id: uuid.UUID) -> uuid.UUID:
        if target_type == "page":
            return target_id
        if target_type == "panel":
            panel = self._require(Panel, target_id, "Panel not found")
            return panel.page_id
        if target_type == "bubble":
            bubble = self._require(Bubble, target_id, "Bubble not found")
            return self._page_for_bubble(bubble).id
        page = self.session.exec(
            select(Page).where(Page.project_id == project_id).order_by(Page.page_number.asc(), Page.created_at.asc())
        ).first()
        if page is None:
            raise ValueError("Project has no pages")
        return page.id

    def _target_panel_id(self, project_id: uuid.UUID, target_type: str, target_id: uuid.UUID, normalized: str) -> uuid.UUID:
        if target_type == "panel":
            return target_id
        if target_type == "bubble":
            bubble = self._require(Bubble, target_id, "Bubble not found")
            return bubble.panel_id
        page_id = self._target_page_id(project_id, target_type, target_id)
        panel_order = command_panel_number(normalized)
        query = select(Panel).where(Panel.page_id == page_id)
        if panel_order is not None:
            panel = self.session.exec(query.where(Panel.reading_order == panel_order)).first()
            if panel is not None:
                return panel.id
        panel = self.session.exec(query.order_by(Panel.reading_order.asc(), Panel.created_at.asc())).first()
        if panel is None:
            raise ValueError("Page has no panels")
        return panel.id

    def _target_bubble_id(self, project_id: uuid.UUID, target_type: str, target_id: uuid.UUID) -> uuid.UUID:
        if target_type == "bubble":
            return target_id
        if target_type == "panel":
            panel_ids = [target_id]
        else:
            page_id = self._target_page_id(project_id, target_type, target_id)
            panel_ids = [
                panel.id
                for panel in self.session.exec(
                    select(Panel).where(Panel.page_id == page_id).order_by(Panel.reading_order.asc(), Panel.created_at.asc())
                ).all()
            ]
        if not panel_ids:
            raise ValueError("No panels available for bubble command")
        bubble = self.session.exec(
            select(Bubble)
            .where(Bubble.panel_id.in_(panel_ids))
            .order_by(Bubble.z_index.desc(), Bubble.created_at.asc())
        ).first()
        if bubble is None:
            raise ValueError("No bubbles found for command scope")
        return bubble.id

    def _target_bubble_or_page(self, project_id: uuid.UUID, target_type: str, target_id: uuid.UUID) -> tuple[str, uuid.UUID]:
        try:
            return "bubble", self._target_bubble_id(project_id, target_type, target_id)
        except ValueError:
            return "page", self._target_page_id(project_id, target_type, target_id)

    def _target_character_id(self, project_id: uuid.UUID, target_type: str, target_id: uuid.UUID, normalized: str) -> uuid.UUID:
        if target_type == "character":
            return target_id
        characters = self.session.exec(
            select(CharacterCard).where(CharacterCard.project_id == project_id).order_by(CharacterCard.created_at.asc())
        ).all()
        for character in characters:
            if normalize_command(character.name) in normalized:
                return character.id
        if not characters:
            raise ValueError("Project has no character cards")
        return characters[0].id

    def _target_style_id(self, project_id: uuid.UUID, target_type: str, target_id: uuid.UUID) -> uuid.UUID:
        if target_type == "style":
            return target_id
        project = self._require_project(project_id)
        if project.active_style_bible_id is not None:
            return project.active_style_bible_id
        style = self.session.exec(
            select(StyleBible).where(StyleBible.project_id == project_id).order_by(StyleBible.created_at.desc())
        ).first()
        if style is None:
            raise ValueError("Project has no style bible")
        return style.id

    def _bubbles_for_action(self, action: CommandAction) -> list[Bubble]:
        if action.target_type == "bubble":
            return [self._require(Bubble, action.target_id, "Bubble not found")]
        page = self._require(Page, action.target_id, "Page not found")
        panels = self.session.exec(select(Panel).where(Panel.page_id == page.id)).all()
        panel_ids = [panel.id for panel in panels]
        if not panel_ids:
            return []
        return list(self.session.exec(select(Bubble).where(Bubble.panel_id.in_(panel_ids))).all())

    def _panels_for_prompt_action(self, action: CommandAction) -> list[Panel]:
        if action.target_type == "panel":
            return [self._require(Panel, action.target_id, "Panel not found")]
        if action.target_type == "page":
            page = self._require(Page, action.target_id, "Page not found")
            return list(
                self.session.exec(
                    select(Panel).where(Panel.page_id == page.id).order_by(Panel.reading_order.asc(), Panel.created_at.asc())
                ).all()
            )
        return []

    def _page_for_bubble(self, bubble: Bubble) -> Page:
        panel = self._require(Panel, bubble.panel_id, "Bubble panel not found")
        return self._require(Page, panel.page_id, "Bubble page not found")

    def _require_project(self, project_id: uuid.UUID | str) -> Project:
        return self._require(Project, project_id, "Project not found")

    def _require(self, model, row_id: uuid.UUID | str, message: str):
        row = self.session.get(model, uuid.UUID(str(row_id)))
        if row is None:
            raise ValueError(message)
        return row


def normalize_command(command: str) -> str:
    return re.sub(r"\s+", " ", command.strip().lower().replace("-", " "))


def command_page_number(normalized: str) -> int | None:
    match = re.search(r"\bpage\s+(\d+)\b", normalized)
    return int(match.group(1)) if match else None


def command_panel_number(normalized: str) -> int | None:
    match = re.search(r"\bpanel\s+(\d+)\b", normalized)
    return int(match.group(1)) if match else None


def shorten_text(text: str) -> str:
    words = text.strip().split()
    if len(words) <= 5:
        return " ".join(words[: max(1, len(words) - 1)]).rstrip(".,!?") + "."
    kept = words[: max(4, int(len(words) * 0.6))]
    return " ".join(kept).rstrip(".,!?") + "."


def append_text(existing: str | None, addition: str, *, limit: int) -> str:
    base = (existing or "").strip()
    combined = f"{base}\n{addition}".strip() if base else addition.strip()
    if len(combined) <= limit:
        return combined
    return combined[-limit:]


def bubble_geometry(bubble: Bubble) -> dict[str, int]:
    return {"x": bubble.x, "y": bubble.y, "width": bubble.width, "height": bubble.height}


def touch(row: Any) -> None:
    row.updated_at = datetime.now(timezone.utc)


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
