from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from manga_api.compositor import PageCompositor, StorageClient
from manga_api.layout_planner import LayoutPlanner
from manga_api.lettering import Box, clamp_box, fit_text_to_box
from manga_api.models import Bubble, Page, PagePlan, Panel, Project, QAReport, StyleBible
from manga_api.panel_render_director import PanelRenderDirector
from manga_api.qa import MockQAProvider, PageQAService, QAOptions, latest_qa_report, summarize_issues


SAFE_ACTIONS = {
    "move_bubble_inside_page",
    "shrink_overflowing_text",
    "regenerate_page_layout",
    "rebuild_panel_prompt",
    "mark_page_for_rerender",
    "create_missing_composition",
}


class AutoFixService:
    def __init__(self, session: Session, storage: StorageClient | None = None) -> None:
        self.session = session
        self.storage = storage

    def apply_report_fix(
        self,
        report_id: uuid.UUID | str,
        *,
        issue_id: str | None = None,
        issue_code: str | None = None,
        safe_only: bool = True,
    ) -> dict[str, Any]:
        report = self.session.get(QAReport, uuid.UUID(str(report_id)))
        if report is None:
            raise ValueError("QA report not found")
        issues = self._matching_issues(report, issue_id=issue_id, issue_code=issue_code)
        applied: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for issue in issues:
            result = self._apply_issue(issue, safe_only=safe_only)
            if result["status"] == "applied":
                applied.append(result)
            else:
                skipped.append(result)
            if applied:
                break

        after_report = None
        if report.target_type == "page":
            after_report = PageQAService(self.session, MockQAProvider()).run_page_qa(report.target_id, QAOptions())
        return {
            "report_id": report.id,
            "project_id": None,
            "page_id": report.target_id if report.target_type == "page" else report.page_id,
            "applied": applied,
            "skipped": skipped,
            "before_report": report,
            "after_report": after_report,
            "page_reports": [],
            "project_report": None,
        }

    def auto_fix_page_safe(self, page_id: uuid.UUID | str) -> dict[str, Any]:
        parsed_page_id = uuid.UUID(str(page_id))
        before = latest_qa_report(self.session, "page", parsed_page_id)
        if before is None:
            before = PageQAService(self.session, MockQAProvider()).run_page_qa(parsed_page_id, QAOptions())
        applied: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for issue in before.issues:
            if not issue.get("auto_fix_available"):
                continue
            result = self._apply_issue(issue, safe_only=True)
            if result["status"] == "applied":
                applied.append(result)
            else:
                skipped.append(result)
        after = PageQAService(self.session, MockQAProvider()).run_page_qa(parsed_page_id, QAOptions())
        return {
            "report_id": before.id,
            "project_id": None,
            "page_id": parsed_page_id,
            "applied": applied,
            "skipped": skipped,
            "before_report": before,
            "after_report": after,
            "page_reports": [],
            "project_report": None,
        }

    def run_project_full(self, project_id: uuid.UUID | str, options: QAOptions | None = None) -> tuple[QAReport, list[QAReport]]:
        parsed_project_id = uuid.UUID(str(project_id))
        project = self.session.get(Project, parsed_project_id)
        if project is None:
            raise ValueError("Project not found")
        pages = self.session.exec(
            select(Page)
            .where(Page.project_id == project.id)
            .order_by(Page.page_number.asc(), Page.created_at.asc())
        ).all()
        page_reports = [PageQAService(self.session, MockQAProvider()).run_page_qa(page.id, options or QAOptions()) for page in pages]
        issues: list[dict[str, Any]] = []
        recommendations: list[dict[str, Any]] = []
        score_totals: dict[str, list[int]] = {}
        for report in page_reports:
            for issue in report.issues:
                issue_copy = dict(issue)
                issue_copy["id"] = f"page-{report.page_id or report.target_id}-{issue_copy['id']}"
                issue_copy["page_id"] = str(report.page_id or report.target_id)
                issues.append(issue_copy)
            recommendations.extend(report.recommendations)
            for category, score in report.scores.items():
                if isinstance(score, int):
                    score_totals.setdefault(category, []).append(score)
        scores = {
            category: round(sum(values) / len(values))
            for category, values in score_totals.items()
            if values
        }
        overall = round(sum(report.overall_score for report in page_reports) / max(1, len(page_reports)))
        summary = summarize_issues(issues, "project", project.id)
        project_report = QAReport(
            target_type="project",
            target_id=project.id,
            issue_code=summary["issue_code"],
            issue_category=summary["issue_category"],
            severity=summary["severity"],
            confidence=summary["confidence"],
            panel_id=summary["panel_id"],
            auto_fix_available=summary["auto_fix_available"],
            auto_fix_action=summary["auto_fix_action"],
            overall_score=overall,
            scores=scores,
            issues=issues,
            recommendations=recommendations,
            blocking=any(report.blocking for report in page_reports),
        )
        self.session.add(project_report)
        self.session.commit()
        self.session.refresh(project_report)
        return project_report, page_reports

    def _matching_issues(self, report: QAReport, *, issue_id: str | None, issue_code: str | None) -> list[dict[str, Any]]:
        issues = list(report.issues or [])
        if issue_id:
            issues = [issue for issue in issues if issue.get("id") == issue_id]
        if issue_code:
            issues = [issue for issue in issues if issue.get("code") == issue_code or issue.get("issue_code") == issue_code]
        return sorted(issues, key=lambda issue: 0 if issue.get("auto_fix_available") else 1)

    def _apply_issue(self, issue: dict[str, Any], *, safe_only: bool) -> dict[str, Any]:
        action = issue.get("auto_fix_action") if isinstance(issue.get("auto_fix_action"), dict) else {}
        action_type = str(action.get("type") or "")
        if not action_type:
            return skipped(issue, "No auto-fix action is available")
        if safe_only and action_type not in SAFE_ACTIONS:
            return skipped(issue, "Auto-fix action is not marked safe")
        try:
            if action_type == "move_bubble_inside_page":
                return self._move_bubble_inside_page(issue)
            if action_type == "shrink_overflowing_text":
                return self._shrink_overflowing_text(issue)
            if action_type == "regenerate_page_layout":
                return self._regenerate_page_layout(issue)
            if action_type == "rebuild_panel_prompt":
                return self._rebuild_panel_prompt(issue)
            if action_type == "mark_page_for_rerender":
                return self._mark_page_for_rerender(issue)
            if action_type == "create_missing_composition":
                return self._create_missing_composition(issue)
        except ValueError as exc:
            return skipped(issue, str(exc))
        return skipped(issue, f"Unsupported auto-fix action: {action_type}")

    def _move_bubble_inside_page(self, issue: dict[str, Any]) -> dict[str, Any]:
        bubble = self._bubble_for_issue(issue)
        panel = self.session.get(Panel, bubble.panel_id)
        page = self.session.get(Page, panel.page_id) if panel else None
        if page is None:
            raise ValueError("Bubble page not found")
        before = bubble_geometry(bubble)
        box = clamp_box(Box(bubble.x, bubble.y, bubble.width, bubble.height), page.width, page.height)
        bubble.x = box.x
        bubble.y = box.y
        bubble.width = box.width
        bubble.height = box.height
        bubble.position = {"x": box.x, "y": box.y}
        bubble.size = {"width": box.width, "height": box.height}
        touch(bubble)
        self.session.add(bubble)
        self.session.commit()
        return applied(issue, "Moved bubble inside page bounds", before=before, after=bubble_geometry(bubble))

    def _shrink_overflowing_text(self, issue: dict[str, Any]) -> dict[str, Any]:
        bubble = self._bubble_for_issue(issue)
        before = {"font_size": bubble.font_size}
        fit = fit_text_to_box(
            bubble.text,
            bubble.width,
            bubble.height,
            font_size=bubble.font_size,
            vertical_text=bubble.vertical_text,
            manual_override=False,
        )
        bubble.font_size = fit.font_size
        touch(bubble)
        self.session.add(bubble)
        self.session.commit()
        return applied(issue, "Shrank bubble text to fit current box", before=before, after={"font_size": bubble.font_size, "overflow": fit.overflow})

    def _regenerate_page_layout(self, issue: dict[str, Any]) -> dict[str, Any]:
        page = self._page_for_issue(issue)
        panels = self.session.exec(
            select(Panel)
            .where(Panel.page_id == page.id)
            .order_by(Panel.reading_order.asc(), Panel.created_at.asc())
        ).all()
        page_plan = self.session.exec(
            select(PagePlan)
            .where(PagePlan.project_id == page.project_id, PagePlan.page_number == page.page_number)
            .order_by(PagePlan.created_at.desc())
        ).first()
        style = latest_style_bible(self.session, page.project_id)
        direction = str((page.layout_json or {}).get("reading_direction", "rtl"))
        suggestion = LayoutPlanner(self.session).generate_layout(page_plan, style, direction, page=page)
        suggested_by_order = {panel.reading_order: panel for panel in suggestion.panels}
        before = [panel_geometry(panel) for panel in panels]
        for panel in panels:
            suggested = suggested_by_order.get(panel.reading_order)
            if suggested is None:
                continue
            panel.x = suggested.x
            panel.y = suggested.y
            panel.width = suggested.width
            panel.height = suggested.height
            panel.polygon = [point.model_dump() for point in suggested.polygon]
            touch(panel)
            self.session.add(panel)
        layout = dict(page.layout_json or {})
        layout.update(
            {
                "reading_direction": suggestion.reading_direction,
                "safe_margin": suggestion.safe_margin,
                "bleed": suggestion.bleed,
                "layout_reasoning": suggestion.layout_reasoning,
            }
        )
        page.layout_json = layout
        touch(page)
        self.session.add(page)
        self.session.commit()
        return applied(issue, "Regenerated page layout preserving panel count", before=before, after=[panel_geometry(panel) for panel in panels])

    def _rebuild_panel_prompt(self, issue: dict[str, Any]) -> dict[str, Any]:
        panel = self._panel_for_issue(issue)
        prompt = PanelRenderDirector(self.session).build_prompt(panel.id, provider_name="mock", render_mode="draft")
        return applied(issue, "Rebuilt panel render prompt with current anchors", after={"panel_render_prompt_id": str(prompt.id)})

    def _mark_page_for_rerender(self, issue: dict[str, Any]) -> dict[str, Any]:
        page = self._page_for_issue(issue)
        layout = dict(page.layout_json or {})
        rerender = dict(layout.get("rerender") or {})
        panel_id = issue.get("panel_id")
        marked_panels = set(rerender.get("panel_ids") or [])
        if panel_id:
            marked_panels.add(str(panel_id))
        rerender["panel_ids"] = sorted(marked_panels)
        rerender["reason"] = issue.get("code")
        rerender["marked_at"] = datetime.now(timezone.utc).isoformat()
        layout["rerender"] = rerender
        page.layout_json = layout
        touch(page)
        self.session.add(page)
        self.session.commit()
        return applied(issue, "Marked page/panel for rerender", after=rerender)

    def _create_missing_composition(self, issue: dict[str, Any]) -> dict[str, Any]:
        page = self._page_for_issue(issue)
        result = PageCompositor(self.session, self.storage).compose_page(page.id)
        return applied(issue, "Created missing page composition", after={"asset_id": str(result.asset.id), "storage_key": result.asset.storage_key})

    def _bubble_for_issue(self, issue: dict[str, Any]) -> Bubble:
        bubble_id = issue.get("bubble_id") or issue.get("target_id")
        if not bubble_id:
            raise ValueError("Issue does not target a bubble")
        bubble = self.session.get(Bubble, uuid.UUID(str(bubble_id)))
        if bubble is None:
            raise ValueError("Bubble not found")
        return bubble

    def _panel_for_issue(self, issue: dict[str, Any]) -> Panel:
        panel_id = issue.get("panel_id") or issue.get("target_id")
        if not panel_id:
            raise ValueError("Issue does not target a panel")
        panel = self.session.get(Panel, uuid.UUID(str(panel_id)))
        if panel is None:
            raise ValueError("Panel not found")
        return panel

    def _page_for_issue(self, issue: dict[str, Any]) -> Page:
        page_id = issue.get("page_id")
        if not page_id and issue.get("target_type") == "page":
            page_id = issue.get("target_id")
        if not page_id and issue.get("panel_id"):
            panel = self.session.get(Panel, uuid.UUID(str(issue["panel_id"])))
            page_id = panel.page_id if panel else None
        if not page_id and issue.get("bubble_id"):
            bubble = self.session.get(Bubble, uuid.UUID(str(issue["bubble_id"])))
            panel = self.session.get(Panel, bubble.panel_id) if bubble else None
            page_id = panel.page_id if panel else None
        if not page_id:
            raise ValueError("Issue does not target a page")
        page = self.session.get(Page, uuid.UUID(str(page_id)))
        if page is None:
            raise ValueError("Page not found")
        return page


def latest_style_bible(session: Session, project_id: uuid.UUID) -> StyleBible | None:
    project = session.get(Project, project_id)
    if project is not None and project.active_style_bible_id is not None:
        style = session.get(StyleBible, project.active_style_bible_id)
        if style is not None:
            return style
    return session.exec(
        select(StyleBible)
        .where(StyleBible.project_id == project_id)
        .order_by(StyleBible.created_at.desc())
    ).first()


def touch(row: Any) -> None:
    row.updated_at = datetime.now(timezone.utc)


def bubble_geometry(bubble: Bubble) -> dict[str, Any]:
    return {"x": bubble.x, "y": bubble.y, "width": bubble.width, "height": bubble.height, "font_size": bubble.font_size}


def panel_geometry(panel: Panel) -> dict[str, Any]:
    return {"id": str(panel.id), "x": panel.x, "y": panel.y, "width": panel.width, "height": panel.height, "reading_order": panel.reading_order}


def applied(issue: dict[str, Any], message: str, *, before: Any = None, after: Any = None) -> dict[str, Any]:
    return {
        "status": "applied",
        "issue_id": issue.get("id"),
        "issue_code": issue.get("code") or issue.get("issue_code"),
        "action": (issue.get("auto_fix_action") or {}).get("type"),
        "message": message,
        "before": before,
        "after": after,
    }


def skipped(issue: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "status": "skipped",
        "issue_id": issue.get("id"),
        "issue_code": issue.get("code") or issue.get("issue_code"),
        "action": (issue.get("auto_fix_action") or {}).get("type") if isinstance(issue.get("auto_fix_action"), dict) else None,
        "reason": reason,
    }
