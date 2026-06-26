"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle,
  Download,
  Grid2X2,
  History,
  ImageIcon,
  Lock,
  Maximize2,
  Unlock,
  MessageCircle,
  PanelTop,
  RefreshCcw,
  Save,
  ShieldCheck,
  Sparkles,
  Type,
  View,
  Zap,
  ZoomIn,
  ZoomOut
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type {
  Bubble,
  BubbleKind,
  ChapterPlan,
  CompositePage,
  CommandExecuteResult,
  GenerationJob,
  ImageProviderStatus,
  LayoutSuggestion,
  LayoutTemplate,
  PagePlan,
  PageLayout,
  PageReferencePacks,
  PanelPlan,
  PanelRenderDryRunResult,
  PanelRenderHistoryItem,
  PanelRenderMode,
  PanelRenderPrompt,
  PanelRenderStartResult,
  PanelRerenderControl,
  PageType,
  PanelLayout,
  ProjectDetail,
  ProviderHealth,
  ProviderName,
  QAExportPreset,
  QAIssue,
  QAReport,
  ReadingDirection
} from "@manga-ai/shared";

import { apiFetch, getApiBaseUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LearningFeedbackControls } from "@/components/learning/learning-feedback-controls";
import { Textarea } from "@/components/ui/textarea";

const StudioCanvas = dynamic(() => import("./studio-canvas").then((module) => module.StudioCanvas), {
  ssr: false,
  loading: () => <div className="rounded-md border bg-white px-4 py-10 text-sm text-muted-foreground">Loading canvas</div>
});

export function PageStudioView({ projectId, pageId }: { projectId: string; pageId: string }) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [layout, setLayout] = useState<PageLayout | null>(null);
  const [selectedPanelId, setSelectedPanelId] = useState<string | null>(null);
  const [selectedBubbleId, setSelectedBubbleId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isSuggesting, setIsSuggesting] = useState(false);
  const [isComposing, setIsComposing] = useState(false);
  const [isRunningQA, setIsRunningQA] = useState(false);
  const [providerName, setProviderName] = useState<ProviderName>("mock");
  const [qaPreset, setQaPreset] = useState<QAExportPreset>("draft");
  const [renderMode, setRenderMode] = useState<PanelRenderMode>("draft");
  const [providers, setProviders] = useState<ImageProviderStatus[]>([]);
  const [providerHealth, setProviderHealth] = useState<ProviderHealth | null>(null);
  const [dryRunResult, setDryRunResult] = useState<PanelRenderDryRunResult | null>(null);
  const [isDryRunning, setIsDryRunning] = useState(false);
  const [isRenderDrawerOpen, setIsRenderDrawerOpen] = useState(false);
  const [isLoadingRenderData, setIsLoadingRenderData] = useState(false);
  const [renderPrompts, setRenderPrompts] = useState<PanelRenderPrompt[]>([]);
  const [renderHistory, setRenderHistory] = useState<PanelRenderHistoryItem[]>([]);
  const [compareRenderIds, setCompareRenderIds] = useState<string[]>([]);
  const [rerenderControl, setRerenderControl] = useState<PanelRerenderControl>("same_seed");
  const [advancedPromptOverride, setAdvancedPromptOverride] = useState("");
  const [additionalInstruction, setAdditionalInstruction] = useState("");
  const [pageType, setPageType] = useState<PageType>("standard");
  const [layoutTemplates, setLayoutTemplates] = useState<LayoutTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [lockedPanelIds, setLockedPanelIds] = useState<string[]>([]);
  const [panelLabels, setPanelLabels] = useState<Record<string, string>>({});
  const [pacingByPanelOrder, setPacingByPanelOrder] = useState<Record<number, PanelPlan>>({});
  const [isPacingCommandBusy, setIsPacingCommandBusy] = useState(false);
  const [layoutReasoning, setLayoutReasoning] = useState<string[]>([]);
  const [suggestionIssues, setSuggestionIssues] = useState<LayoutSuggestion["validation_issues"]>([]);
  const [jobsByPanel, setJobsByPanel] = useState<Record<string, GenerationJob>>({});
  const [referencePacks, setReferencePacks] = useState<PageReferencePacks | null>(null);
  const [compositePage, setCompositePage] = useState<CompositePage | null>(null);
  const [qaReport, setQaReport] = useState<QAReport | null>(null);
  const [highlightedIssueId, setHighlightedIssueId] = useState<string | null>(null);
  const [highlightedPanelId, setHighlightedPanelId] = useState<string | null>(null);
  const [highlightedBubbleId, setHighlightedBubbleId] = useState<string | null>(null);
  const [canvasZoom, setCanvasZoom] = useState(1);
  const [showGrid, setShowGrid] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadProject() {
    try {
      const nextProject = await apiFetch<ProjectDetail>(`/projects/${projectId}`);
      setProject(nextProject);
      void loadPacingLabels(nextProject);
    } catch {
      setProject(null);
      setPacingByPanelOrder({});
    }
  }

  async function loadPacingLabels(nextProject = project) {
    if (!nextProject) {
      return;
    }
    const currentPage = nextProject.pages.find((page) => page.id === pageId);
    if (!currentPage) {
      setPacingByPanelOrder({});
      return;
    }
    try {
      const chapters = await apiFetch<ChapterPlan[]>(`/projects/${projectId}/story/chapters`);
      const pagePlansByChapter = await Promise.all(
        chapters
          .filter((chapter) => chapter.id)
          .map((chapter) => apiFetch<PagePlan[]>(`/chapters/${chapter.id}/story/page-plans`).catch(() => []))
      );
      const pagePlan = pagePlansByChapter.flat().find((plan) => plan.page_number === currentPage.page_number);
      const nextPacing: Record<number, PanelPlan> = {};
      for (const panel of pagePlan?.panels ?? []) {
        nextPacing[panel.panel_order] = panel;
      }
      setPacingByPanelOrder(nextPacing);
    } catch {
      setPacingByPanelOrder({});
    }
  }

  async function loadProviders() {
    try {
      const nextProviders = await apiFetch<ImageProviderStatus[]>("/providers");
      setProviders(nextProviders);
    } catch {
      setProviders([]);
    }
  }

  async function loadProviderHealth(nextProviderName = providerName) {
    try {
      const health = await apiFetch<ProviderHealth>(`/providers/${nextProviderName}/health`);
      setProviderHealth(health);
    } catch {
      setProviderHealth(null);
    }
  }

  async function loadLayout() {
    setIsLoading(true);
    setError(null);
    try {
      const nextLayout = await apiFetch<PageLayout>(`/pages/${pageId}/layout`);
      setLayout(nextLayout);
      setSelectedPanelId(nextLayout.panels[0]?.id ?? null);
      setSelectedBubbleId(null);
      setLockedPanelIds([]);
      setPanelLabels({});
      setLayoutReasoning([]);
      setSuggestionIssues([]);
      void loadReferencePacks();
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load layout");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadProject();
    void loadLayout();
    void loadComposite();
    void loadLatestQA();
    void loadReferencePacks();
    void loadLayoutTemplates();
    void loadProviders();
  }, [pageId]);

  useEffect(() => {
    setDryRunResult(null);
    void loadProviderHealth(providerName);
  }, [providerName]);

  const selectedPanel = useMemo(() => {
    return layout?.panels.find((panel) => panel.id === selectedPanelId) ?? null;
  }, [layout, selectedPanelId]);

  const selectedBubble = useMemo(() => {
    return selectedPanel?.bubbles.find((bubble) => bubble.id === selectedBubbleId) ?? null;
  }, [selectedPanel, selectedBubbleId]);

  const selectedPanelJob = selectedPanel ? jobsByPanel[selectedPanel.id] ?? null : null;
  const selectedPanelPacing = selectedPanel ? pacingByPanelOrder[selectedPanel.reading_order] ?? null : null;
  const selectedProviderStatus = useMemo(
    () => providers.find((provider) => provider.name === providerName) ?? null,
    [providerName, providers]
  );
  const selectedReferenceSummary = selectedPanel
    ? referencePacks?.panels.find((panel) => panel.panel_id === selectedPanel.id) ?? null
    : null;
  const selectedPanelIsRendering = selectedPanelJob?.status === "queued" || selectedPanelJob?.status === "running";
  const latestRenderPrompt = renderPrompts[0] ?? null;
  const compareItems = renderHistory.filter((item) => compareRenderIds.includes(item.render.id));

  const panelRenderUrls = useMemo(() => {
    const urls: Record<string, string> = {};
    if (selectedPanelId) {
      const preferred = renderHistory.find((item) => item.approved && renderImageUrl(item.render)) ?? renderHistory.find((item) => renderImageUrl(item.render));
      const preferredUrl = preferred ? renderImageUrl(preferred.render) : null;
      if (preferredUrl) {
        urls[selectedPanelId] = preferredUrl;
      }
    }
    for (const job of Object.values(jobsByPanel)) {
      if (!job.panel_id) {
        continue;
      }
      const payloadUrl = typeof job.output_payload.public_url === "string" ? job.output_payload.public_url : null;
      const url = job.render ? renderImageUrl(job.render) ?? payloadUrl : payloadUrl;
      if (url) {
        urls[job.panel_id] = url;
      }
    }
    return urls;
  }, [jobsByPanel, renderHistory, selectedPanelId]);

  useEffect(() => {
    const activeJobs = Object.values(jobsByPanel).filter((job) => job.status === "queued" || job.status === "running");
    if (activeJobs.length === 0) {
      return;
    }

    const timer = window.setInterval(() => {
      void Promise.all(activeJobs.map((job) => apiFetch<GenerationJob>(`/jobs/${job.id}`).catch(() => job))).then((jobs) => {
        setJobsByPanel((current) => {
          const next = { ...current };
          for (const job of jobs) {
            if (job.panel_id) {
              next[job.panel_id] = job;
            }
          }
          return next;
        });
        if (selectedPanelId && jobs.some((job) => job.panel_id === selectedPanelId && job.status !== "queued" && job.status !== "running")) {
          void loadPanelRenderData(selectedPanelId);
        }
      });
    }, 1500);

    return () => window.clearInterval(timer);
  }, [jobsByPanel]);

  useEffect(() => {
    if (!selectedPanelId || selectedPanelId.startsWith("local-")) {
      setRenderPrompts([]);
      setRenderHistory([]);
      setCompareRenderIds([]);
      return;
    }
    void loadPanelRenderData(selectedPanelId);
  }, [selectedPanelId]);

  function updateLayout(updates: Partial<PageLayout>) {
    setLayout((current) => (current ? { ...current, ...updates } : current));
  }

  function updatePanel(panel: PanelLayout) {
    setLayout((current) =>
      current
        ? {
            ...current,
            panels: current.panels.map((existing) => (existing.id === panel.id ? panel : existing))
          }
        : current
    );
  }

  function updateBubble(panelId: string, bubble: Bubble, persist: boolean) {
    setLayout((current) =>
      current
        ? {
            ...current,
            panels: current.panels.map((panel) =>
              panel.id === panelId
                ? {
                    ...panel,
                    bubbles: panel.bubbles.map((existing) => (existing.id === bubble.id ? bubble : existing))
                  }
                : panel
            )
          }
        : current
    );
    if (persist) {
      void persistBubble(bubble);
    }
  }

  function addPanel() {
    if (!layout) {
      return;
    }
    const order = Math.max(0, ...layout.panels.map((panel) => panel.reading_order)) + 1;
    const width = Math.min(420, Math.max(180, Math.round(layout.width * 0.32)));
    const height = Math.min(320, Math.max(140, Math.round(layout.height * 0.16)));
    const x = Math.max(layout.safe_margin, 80);
    const y = Math.max(layout.safe_margin, 80 + layout.panels.length * 44);
    const panel: PanelLayout = {
      id: `local-${Date.now()}`,
      page_id: layout.page_id,
      x,
      y,
      width,
      height,
      reading_order: order,
      prompt: null,
      polygon: rectPolygon(x, y, width, height),
      bubbles: []
    };
    setLayout({ ...layout, panels: [...layout.panels, panel] });
    setSelectedPanelId(panel.id);
    setSelectedBubbleId(null);
  }

  async function saveLayout() {
    if (!layout) {
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const saved = await apiFetch<PageLayout>(`/pages/${pageId}/layout`, {
        method: "PUT",
        body: JSON.stringify({
          width: layout.width,
          height: layout.height,
          bleed: layout.bleed,
          safe_margin: layout.safe_margin,
          reading_direction: layout.reading_direction,
          qa_overlay_enabled: layout.qa_overlay_enabled,
          panels: layout.panels.map((panel) => ({
            id: panel.id.startsWith("local-") ? null : panel.id,
            x: panel.x,
            y: panel.y,
            width: panel.width,
            height: panel.height,
            polygon: panel.polygon,
            reading_order: panel.reading_order,
            prompt: panel.prompt
          }))
        })
      });
      setLayout(saved);
      setSelectedPanelId(saved.panels[0]?.id ?? null);
      setSelectedBubbleId(null);
      setLockedPanelIds((current) => current.filter((id) => saved.panels.some((panel) => panel.id === id)));
      void loadReferencePacks();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to save layout");
    } finally {
      setIsSaving(false);
    }
  }

  async function loadLayoutTemplates() {
    try {
      const templates = await apiFetch<LayoutTemplate[]>(`/projects/${projectId}/layout-templates`);
      setLayoutTemplates(templates);
      setSelectedTemplateId((current) => (current && templates.some((template) => template.id === current) ? current : ""));
    } catch {
      setLayoutTemplates([]);
    }
  }

  async function suggestLayout() {
    if (!layout) {
      return;
    }
    setIsSuggesting(true);
    setError(null);
    try {
      const suggestion = await apiFetch<LayoutSuggestion>(`/pages/${pageId}/layout/suggest`, {
        method: "POST",
        body: JSON.stringify({
          page_type: pageType,
          template_id: selectedTemplateId || null,
          reading_direction: layout.reading_direction,
          locked_panel_ids: lockedPanelIds,
          safe_margin: layout.safe_margin,
          bleed: layout.bleed,
          min_gutter: 12
        })
      });
      const existingById = new Map(layout.panels.map((panel) => [panel.id, panel]));
      const localSeed = Date.now();
      const nextPanels: PanelLayout[] = suggestion.panels.map((panel, index) => {
        const id = panel.id ?? `local-suggested-${localSeed}-${index}`;
        const existing = panel.id ? existingById.get(panel.id) : null;
        return {
          id,
          page_id: layout.page_id,
          x: panel.x,
          y: panel.y,
          width: panel.width,
          height: panel.height,
          polygon: panel.polygon,
          reading_order: panel.reading_order,
          prompt: panel.prompt ?? null,
          bubbles: existing?.bubbles ?? []
        };
      });
      const nextLabels: Record<string, string> = {};
      suggestion.panels.forEach((panel, index) => {
        const id = panel.id ?? nextPanels[index]?.id;
        const label = panel.emotional_beat || panel.story_beat;
        if (id && label) {
          nextLabels[id] = label;
        }
      });
      setLayout({
        ...layout,
        width: suggestion.width,
        height: suggestion.height,
        bleed: suggestion.bleed,
        safe_margin: suggestion.safe_margin,
        reading_direction: suggestion.reading_direction,
        panels: nextPanels
      });
      setPanelLabels(nextLabels);
      setLayoutReasoning(suggestion.layout_reasoning);
      setSuggestionIssues(suggestion.validation_issues);
      setSelectedPanelId(nextPanels[0]?.id ?? null);
      setSelectedBubbleId(null);
    } catch (suggestError) {
      setError(suggestError instanceof Error ? suggestError.message : "Unable to suggest layout");
    } finally {
      setIsSuggesting(false);
    }
  }

  function toggleSelectedPanelLock() {
    if (!selectedPanel) {
      return;
    }
    if (selectedPanel.id.startsWith("local-")) {
      setError("Save the panel layout before locking a panel");
      return;
    }
    setLockedPanelIds((current) =>
      current.includes(selectedPanel.id)
        ? current.filter((id) => id !== selectedPanel.id)
        : [...current, selectedPanel.id]
    );
  }

  async function loadPanelRenderData(panelId: string) {
    setIsLoadingRenderData(true);
    try {
      const [prompts, history] = await Promise.all([
        apiFetch<PanelRenderPrompt[]>(`/panels/${panelId}/render-prompts`),
        apiFetch<PanelRenderHistoryItem[]>(`/panels/${panelId}/renders`)
      ]);
      setRenderPrompts(prompts);
      setRenderHistory(history);
      setCompareRenderIds((current) => current.filter((id) => history.some((item) => item.render.id === id)));
      const latestMode = prompts[0]?.quality_mode;
      if (latestMode === "storyboard" || latestMode === "draft" || latestMode === "final" || latestMode === "ultra") {
        setRenderMode(latestMode);
      }
    } catch {
      setRenderPrompts([]);
      setRenderHistory([]);
    } finally {
      setIsLoadingRenderData(false);
    }
  }

  async function renderSelectedPanel() {
    if (!selectedPanel) {
      setError("Select a panel first");
      return;
    }
    if (selectedPanel.id.startsWith("local-")) {
      setError("Save the panel layout before rendering");
      return;
    }
    if (selectedProviderStatus && !selectedProviderStatus.configured) {
      setError(`${selectedProviderStatus.display_name} is not configured. Use dry-run for details or switch to mock.`);
      return;
    }

    setError(null);
    try {
      const result = await apiFetch<PanelRenderStartResult>(`/panels/${selectedPanel.id}/render`, {
        method: "POST",
        body: JSON.stringify({
          provider_name: providerName,
          render_mode: renderMode,
          advanced_prompt_override: advancedPromptOverride.trim() || null,
          additional_user_instruction: additionalInstruction.trim() || null,
          provider_options: {}
        })
      });
      setJobsByPanel((current) => ({ ...current, [selectedPanel.id]: result.job }));
      setRenderPrompts((current) => [result.prompt, ...current.filter((prompt) => prompt.id !== result.prompt.id)]);
      void loadPanelRenderData(selectedPanel.id);
    } catch (renderError) {
      setError(renderError instanceof Error ? renderError.message : "Unable to start render");
    }
  }

  async function dryRunSelectedPanel() {
    if (!selectedPanel) {
      setError("Select a panel first");
      return;
    }
    if (selectedPanel.id.startsWith("local-")) {
      setError("Save the panel layout before dry-run");
      return;
    }

    setIsDryRunning(true);
    setError(null);
    try {
      const result = await apiFetch<PanelRenderDryRunResult>(`/panels/${selectedPanel.id}/render-dry-run`, {
        method: "POST",
        body: JSON.stringify({
          provider_name: providerName,
          render_mode: renderMode,
          advanced_prompt_override: advancedPromptOverride.trim() || null,
          additional_user_instruction: additionalInstruction.trim() || null,
          provider_options: {}
        })
      });
      setDryRunResult(result);
      setRenderPrompts((current) => [result.prompt, ...current.filter((prompt) => prompt.id !== result.prompt.id)]);
    } catch (dryRunError) {
      setError(dryRunError instanceof Error ? dryRunError.message : "Unable to dry-run render");
    } finally {
      setIsDryRunning(false);
    }
  }

  async function retrySelectedPanelWithMock() {
    if (!selectedPanel || selectedPanel.id.startsWith("local-")) {
      setError("Select a saved panel first");
      return;
    }
    setProviderName("mock");
    setError(null);
    try {
      const result = await apiFetch<PanelRenderStartResult>(`/panels/${selectedPanel.id}/render`, {
        method: "POST",
        body: JSON.stringify({
          provider_name: "mock",
          render_mode: renderMode,
          advanced_prompt_override: advancedPromptOverride.trim() || null,
          additional_user_instruction: additionalInstruction.trim() || null,
          provider_options: { retry_from_provider: providerName }
        })
      });
      setJobsByPanel((current) => ({ ...current, [selectedPanel.id]: result.job }));
      setRenderPrompts((current) => [result.prompt, ...current.filter((prompt) => prompt.id !== result.prompt.id)]);
      void loadPanelRenderData(selectedPanel.id);
    } catch (renderError) {
      setError(renderError instanceof Error ? renderError.message : "Unable to retry with mock");
    }
  }

  async function rerenderSelectedPanel(control = rerenderControl) {
    if (!selectedPanel) {
      setError("Select a panel first");
      return;
    }
    if (selectedPanel.id.startsWith("local-")) {
      setError("Save the panel layout before rendering");
      return;
    }
    setError(null);
    try {
      const result = await apiFetch<PanelRenderStartResult>(`/panels/${selectedPanel.id}/rerender`, {
        method: "POST",
        body: JSON.stringify({
          provider_name: providerName,
          render_mode: renderMode,
          control,
          advanced_prompt_override: advancedPromptOverride.trim() || null,
          additional_user_instruction: additionalInstruction.trim() || null,
          provider_options: {}
        })
      });
      setJobsByPanel((current) => ({ ...current, [selectedPanel.id]: result.job }));
      setRenderPrompts((current) => [result.prompt, ...current.filter((prompt) => prompt.id !== result.prompt.id)]);
      void loadPanelRenderData(selectedPanel.id);
    } catch (renderError) {
      setError(renderError instanceof Error ? renderError.message : "Unable to rerender panel");
    }
  }

  async function approveRender(renderId: string) {
    try {
      await apiFetch<PanelRenderHistoryItem>(`/renders/${renderId}/approve`, { method: "POST" });
      if (selectedPanel) {
        void loadPanelRenderData(selectedPanel.id);
      }
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : "Unable to approve render");
    }
  }

  function toggleCompareRender(renderId: string) {
    setCompareRenderIds((current) => {
      if (current.includes(renderId)) {
        return current.filter((id) => id !== renderId);
      }
      return [...current.slice(-1), renderId];
    });
  }

  async function loadComposite() {
    try {
      const composite = await apiFetch<CompositePage>(`/pages/${pageId}/composite`);
      setCompositePage(composite);
    } catch {
      setCompositePage(null);
    }
  }

  async function loadReferencePacks() {
    try {
      const packs = await apiFetch<PageReferencePacks>(`/pages/${pageId}/reference-packs`);
      setReferencePacks(packs);
    } catch {
      setReferencePacks(null);
    }
  }

  async function composePage() {
    setIsComposing(true);
    setError(null);
    try {
      const composite = await apiFetch<CompositePage>(`/pages/${pageId}/compose`, {
        method: "POST",
        body: JSON.stringify({})
      });
      setCompositePage(composite);
    } catch (composeError) {
      setError(composeError instanceof Error ? composeError.message : "Unable to compose page");
    } finally {
      setIsComposing(false);
    }
  }

  async function loadLatestQA() {
    try {
      const report = await apiFetch<QAReport>(`/pages/${pageId}/qa/latest`);
      setQaReport(report);
    } catch {
      setQaReport(null);
    }
  }

  async function runQA() {
    setIsRunningQA(true);
    setError(null);
    try {
      const report = await apiFetch<QAReport>(`/pages/${pageId}/qa`, {
        method: "POST",
        body: JSON.stringify({
          provider_name: "mock",
          export_preset: qaPreset
        })
      });
      setQaReport(report);
      setHighlightedIssueId(null);
      setHighlightedPanelId(null);
      setHighlightedBubbleId(null);
    } catch (qaError) {
      setError(qaError instanceof Error ? qaError.message : "Unable to run QA");
    } finally {
      setIsRunningQA(false);
    }
  }

  async function runPacingCommand(command: string, scopeType: "page" | "panel" = "page") {
    const scopeId = scopeType === "panel" ? selectedPanel?.id : pageId;
    if (!scopeId || scopeId.startsWith("local-")) {
      setError(scopeType === "panel" ? "Save the selected panel before running this command" : "Page is not ready for pacing command");
      return;
    }
    setIsPacingCommandBusy(true);
    setError(null);
    try {
      await apiFetch<CommandExecuteResult>("/commands/execute", {
        method: "POST",
        body: JSON.stringify({
          project_id: projectId,
          scope: { type: scopeType, id: scopeId },
          command,
          confirmed: false
        })
      });
      await Promise.all([loadLayout(), loadProject()]);
    } catch (commandError) {
      setError(commandError instanceof Error ? commandError.message : "Unable to run pacing command");
    } finally {
      setIsPacingCommandBusy(false);
    }
  }

  function focusIssue(issue: QAIssue) {
    setHighlightedIssueId(issue.id);
    const panelId = issue.panel_id ?? (issue.target_type === "panel" ? issue.target_id : null);
    const bubbleId = issue.bubble_id ?? (issue.target_type === "bubble" ? issue.target_id : null);
    setHighlightedPanelId(panelId);
    setHighlightedBubbleId(bubbleId);
    if (panelId) {
      setSelectedPanelId(panelId);
    }
    if (bubbleId) {
      setSelectedBubbleId(bubbleId);
    } else {
      setSelectedBubbleId(null);
    }
  }

  async function addBubble(kind: BubbleKind) {
    if (!selectedPanel) {
      setError("Select a panel first");
      return;
    }
    if (selectedPanel.id.startsWith("local-")) {
      setError("Save the panel layout before adding bubbles");
      return;
    }

    setError(null);
    const defaults = bubbleDefaults(kind);
    const bubble = await apiFetch<Bubble>(`/panels/${selectedPanel.id}/bubbles`, {
      method: "POST",
      body: JSON.stringify({
        kind,
        x: selectedPanel.x + 40,
        y: selectedPanel.y + 40,
        width: defaults.width,
        height: defaults.height,
        text: defaults.text
      })
    });
    setLayout((current) =>
      current
        ? {
            ...current,
            panels: current.panels.map((panel) =>
              panel.id === selectedPanel.id ? { ...panel, bubbles: [...panel.bubbles, bubble] } : panel
            )
          }
        : current
    );
    setSelectedBubbleId(bubble.id);
  }

  async function persistBubble(bubble: Bubble) {
    try {
      await apiFetch<Bubble>(`/bubbles/${bubble.id}`, {
        method: "PUT",
        body: JSON.stringify({
          kind: bubble.kind,
          x: bubble.x,
          y: bubble.y,
          width: bubble.width,
          height: bubble.height,
          text: bubble.text
        })
      });
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to update bubble");
    }
  }

  if (isLoading && layout === null) {
    return (
      <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-md border bg-white px-4 py-8 text-sm text-muted-foreground">
          Loading Page Studio
        </div>
      </main>
    );
  }

  if (layout === null) {
    return (
      <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-md border bg-white px-4 py-8 text-sm text-destructive">
          {error || "Page layout not found"}
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="flex flex-col gap-4 border-b pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex flex-col gap-3">
            <Button asChild variant="ghost" size="sm" className="w-fit">
              <Link href={`/projects/${projectId}`}>
                <ArrowLeft className="h-4 w-4" />
                Project
              </Link>
            </Button>
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-semibold tracking-normal">Page Studio</h1>
                <Badge>{layout.reading_direction}</Badge>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                {layout.width}x{layout.height} - bleed {layout.bleed} - safe {layout.safe_margin}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={() => void loadLayout()}>
              <RefreshCcw className="h-4 w-4" />
              Load
            </Button>
            <Button variant="outline" onClick={() => void loadComposite()}>
              <ImageIcon className="h-4 w-4" />
              Composite
            </Button>
            <Button onClick={() => void saveLayout()} disabled={isSaving}>
              <Save className="h-4 w-4" />
              {isSaving ? "Saving" : "Save"}
            </Button>
          </div>
        </header>

        {error ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        ) : null}

        <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-3">
              <div>
                <CardTitle>Page Thumbnails</CardTitle>
                <CardDescription>{project?.pages.length ?? 0} pages in this project</CardDescription>
              </div>
              <Badge>Selected page preview</Badge>
            </CardHeader>
            <CardContent>
              {project?.pages.length ? (
                <div className="flex gap-3 overflow-x-auto pb-1">
                  {project.pages.map((page) => (
                    <Link
                      key={page.id}
                      href={`/projects/${projectId}/pages/${page.id}/studio`}
                      className={`w-28 shrink-0 rounded-md border bg-white p-2 text-sm transition-colors hover:border-primary/60 ${
                        page.id === pageId ? "border-primary bg-primary/5" : ""
                      }`}
                    >
                      <div className="relative mx-auto w-16 overflow-hidden rounded-sm border bg-[#fffdf7]" style={{ aspectRatio: `${page.width} / ${page.height}` }}>
                        {page.panels.slice(0, 8).map((panel) => (
                          <span
                            key={panel.id}
                            className="absolute border border-foreground/60 bg-muted/70"
                            style={{
                              left: `${(panel.x / page.width) * 100}%`,
                              top: `${(panel.y / page.height) * 100}%`,
                              width: `${(panel.width / page.width) * 100}%`,
                              height: `${(panel.height / page.height) * 100}%`
                            }}
                          />
                        ))}
                      </div>
                      <span className="mt-2 block font-medium">Page {page.page_number}</span>
                      <span className="text-xs text-muted-foreground">{page.panels.length} panels</span>
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="rounded-md border bg-muted/30 px-3 py-4 text-sm text-muted-foreground">No pages are available yet.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Viewport</CardTitle>
              <CardDescription>Zoom, grid, and safe-margin QA overlay</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => setCanvasZoom((value) => Math.max(0.55, Number((value - 0.1).toFixed(2))))}>
                <ZoomOut className="h-4 w-4" />
                Zoom
              </Button>
              <Button variant="outline" size="sm" onClick={() => setCanvasZoom((value) => Math.min(1.6, Number((value + 0.1).toFixed(2))))}>
                <ZoomIn className="h-4 w-4" />
                Zoom
              </Button>
              <Button variant="outline" size="sm" onClick={() => setCanvasZoom(1)}>
                <Maximize2 className="h-4 w-4" />
                Fit
              </Button>
              <Button variant={showGrid ? "default" : "outline"} size="sm" onClick={() => setShowGrid((value) => !value)}>
                <Grid2X2 className="h-4 w-4" />
                Grid
              </Button>
              <Button variant={layout.qa_overlay_enabled ? "default" : "outline"} size="sm" onClick={() => updateLayout({ qa_overlay_enabled: !layout.qa_overlay_enabled })}>
                <ShieldCheck className="h-4 w-4" />
                Safe
              </Button>
              <Badge>{Math.round(canvasZoom * 100)}%</Badge>
            </CardContent>
          </Card>
        </section>

        <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)_340px]">
          <aside className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Page</CardTitle>
                <CardDescription>Canvas settings</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <LearningFeedbackControls projectId={projectId} targetType="page_layout" targetId={pageId} compact />
                <NumberField label="Width" value={layout.width} onChange={(width) => updateLayout({ width })} />
                <NumberField label="Height" value={layout.height} onChange={(height) => updateLayout({ height })} />
                <NumberField label="Bleed" value={layout.bleed} onChange={(bleed) => updateLayout({ bleed })} />
                <NumberField label="Safe Margin" value={layout.safe_margin} onChange={(safe_margin) => updateLayout({ safe_margin })} />
                <label className="flex flex-col gap-2 text-sm font-medium">
                  Direction
                  <select
                    value={layout.reading_direction}
                    onChange={(event) => updateLayout({ reading_direction: event.target.value as ReadingDirection })}
                    className="h-10 rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <option value="rtl">rtl</option>
                    <option value="ltr">ltr</option>
                    <option value="vertical-rl">vertical-rl</option>
                  </select>
                </label>
                <label className="flex items-center gap-2 text-sm font-medium">
                  <input
                    type="checkbox"
                    checked={layout.qa_overlay_enabled}
                    onChange={(event) => updateLayout({ qa_overlay_enabled: event.target.checked })}
                  />
                  QA overlay
                </label>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Layout</CardTitle>
                <CardDescription>Intelligence pass</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <div className="grid grid-cols-1 gap-2">
                  <Button variant="outline" onClick={() => void runPacingCommand("Make this page more dramatic.", "page")} disabled={isPacingCommandBusy}>
                    <Zap className="h-4 w-4" />
                    Make More Dramatic
                  </Button>
                  <Button variant="outline" onClick={() => void runPacingCommand("Add a silent beat before the next story action.", "page")} disabled={isPacingCommandBusy}>
                    <View className="h-4 w-4" />
                    Add Silent Beat
                  </Button>
                  <Button variant="outline" onClick={() => void runPacingCommand("Make dialogue shorter.", "page")} disabled={isPacingCommandBusy}>
                    <Type className="h-4 w-4" />
                    Compress Dialogue
                  </Button>
                </div>
                <label className="flex flex-col gap-2 text-sm font-medium">
                  Page type
                  <select
                    value={pageType}
                    onChange={(event) => setPageType(event.target.value as PageType)}
                    className="h-10 rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {PAGE_TYPE_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option.replaceAll("_", " ")}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-2 text-sm font-medium">
                  Template
                  <select
                    value={selectedTemplateId}
                    onChange={(event) => setSelectedTemplateId(event.target.value)}
                    className="h-10 rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <option value="">Auto fallback</option>
                    {layoutTemplates.map((template) => (
                      <option key={template.id} value={template.id}>
                        {template.name}
                      </option>
                    ))}
                  </select>
                </label>
                <Button variant="outline" onClick={() => void suggestLayout()} disabled={isSuggesting}>
                  <Sparkles className="h-4 w-4" />
                  {isSuggesting ? "Suggesting" : "Suggest Layout"}
                </Button>
                {lockedPanelIds.length > 0 ? (
                  <p className="text-xs text-muted-foreground">{lockedPanelIds.length} locked panel{lockedPanelIds.length === 1 ? "" : "s"}</p>
                ) : null}
                {layoutReasoning.length > 0 ? (
                  <div className="rounded-md border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
                    {layoutReasoning.slice(0, 3).map((reason) => (
                      <p key={reason}>{reason}</p>
                    ))}
                  </div>
                ) : null}
                {suggestionIssues.length > 0 ? (
                  <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    {suggestionIssues.slice(0, 2).map((issue) => (
                      <p key={`${issue.code}-${issue.panel_order ?? "page"}`}>{issue.message}</p>
                    ))}
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Panels</CardTitle>
                <CardDescription>{layout.panels.length} on page</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <Button onClick={addPanel}>
                  <PanelTop className="h-4 w-4" />
                  Add Panel
                </Button>
                <div className="flex max-h-[360px] flex-col gap-2 overflow-auto">
                  {layout.panels.map((panel) => (
                    <PanelButton
                      key={panel.id}
                      panel={panel}
                      selected={selectedPanelId === panel.id}
                      referenceSummary={referencePacks?.panels.find((summary) => summary.panel_id === panel.id) ?? null}
                      locked={lockedPanelIds.includes(panel.id)}
                      label={panelLabels[panel.id] ?? pacingByPanelOrder[panel.reading_order]?.recommended_panel_size ?? pacingByPanelOrder[panel.reading_order]?.time_duration}
                      renderStatus={jobsByPanel[panel.id]?.status ?? (panelRenderUrls[panel.id] ? "rendered" : "not rendered")}
                      qaIssueCount={(qaReport?.issues ?? []).filter((issue) => issue.panel_id === panel.id).length}
                      onClick={() => {
                        setSelectedPanelId(panel.id);
                        setSelectedBubbleId(null);
                      }}
                    />
                  ))}
                </div>
              </CardContent>
            </Card>
          </aside>

          <section className="min-w-0">
            <StudioCanvas
              layout={layout}
              selectedPanelId={selectedPanelId}
              selectedBubbleId={selectedBubbleId}
              onSelectPanel={(panelId) => {
                setSelectedPanelId(panelId);
                setSelectedBubbleId(null);
              }}
              onSelectBubble={(bubbleId, panelId) => {
                setSelectedPanelId(panelId);
                setSelectedBubbleId(bubbleId);
              }}
              onPanelChange={updatePanel}
              onBubbleChange={updateBubble}
              panelRenderUrls={panelRenderUrls}
              highlightedPanelId={highlightedPanelId}
              highlightedBubbleId={highlightedBubbleId}
              panelLabels={panelLabels}
              lockedPanelIds={lockedPanelIds}
              zoom={canvasZoom}
              showGrid={showGrid}
            />
          </section>

          <aside className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Panel</CardTitle>
                <CardDescription>{selectedPanel ? selectedPanel.id.slice(0, 8) : "None selected"}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {selectedPanel ? (
                  <>
                    <Button variant="outline" onClick={toggleSelectedPanelLock}>
                      {lockedPanelIds.includes(selectedPanel.id) ? <Unlock className="h-4 w-4" /> : <Lock className="h-4 w-4" />}
                      {lockedPanelIds.includes(selectedPanel.id) ? "Unlock Panel" : "Lock Panel"}
                    </Button>
                    <NumberField
                      label="Order"
                      value={selectedPanel.reading_order}
                      onChange={(reading_order) => updatePanel({ ...selectedPanel, reading_order })}
                    />
                    <div className="grid grid-cols-2 gap-3">
                      <NumberField label="X" value={selectedPanel.x} onChange={(x) => updatePanel(movePanel(selectedPanel, { x }))} />
                      <NumberField label="Y" value={selectedPanel.y} onChange={(y) => updatePanel(movePanel(selectedPanel, { y }))} />
                      <NumberField
                        label="Width"
                        value={selectedPanel.width}
                        onChange={(width) => updatePanel(resizePanel(selectedPanel, { width }))}
                      />
                      <NumberField
                        label="Height"
                        value={selectedPanel.height}
                        onChange={(height) => updatePanel(resizePanel(selectedPanel, { height }))}
                      />
                    </div>
                    <Textarea
                      value={selectedPanel.prompt ?? ""}
                      onChange={(event) => updatePanel({ ...selectedPanel, prompt: event.target.value || null })}
                      placeholder="Prompt"
                    />
                    {selectedPanelPacing ? (
                      <div className="rounded-md border bg-muted/40 p-3 text-xs">
                        <div className="mb-2 flex flex-wrap gap-1">
                          <Badge>{selectedPanelPacing.recommended_panel_size}</Badge>
                          <Badge>{selectedPanelPacing.time_duration.replaceAll("_", " ")}</Badge>
                          {selectedPanelPacing.silence ? <Badge className="border-slate-400 text-slate-700">silent</Badge> : null}
                        </div>
                        <p className="text-muted-foreground">
                          Impact {selectedPanelPacing.impact_level} - motion {selectedPanelPacing.motion_intensity} - dialogue {selectedPanelPacing.dialogue_weight}
                        </p>
                        <p className="mt-1 text-muted-foreground">{selectedPanelPacing.transition_type.replaceAll("_", " ")}</p>
                      </div>
                    ) : null}
                    <div className="rounded-md border bg-muted/40 p-3 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">Character State</span>
                        {selectedReferenceSummary?.warning ? (
                          <Badge className="border-amber-500 text-amber-700">missing</Badge>
                        ) : (
                          <Badge>ready</Badge>
                        )}
                      </div>
                      {selectedReferenceSummary ? (
                        <div className="mt-2 flex flex-col gap-2">
                          <p className="text-xs text-muted-foreground">
                            {selectedReferenceSummary.characters.length > 0 ? selectedReferenceSummary.characters.join(", ") : "No characters linked"}
                          </p>
                          {selectedReferenceSummary.active_states.length === 0 ? (
                            <p className="text-xs text-amber-700">No active character state is attached to this panel.</p>
                          ) : (
                            selectedReferenceSummary.active_states.map((state) => (
                              <div key={state.id} className="rounded-md bg-white px-2 py-2 text-xs">
                                <p><span className="font-medium">Outfit:</span> {state.outfit_state || "Not set"}</p>
                                <p><span className="font-medium">Injury:</span> {state.injury_state || "None"}</p>
                                <p><span className="font-medium">Emotion:</span> {state.emotional_state || "Not set"}</p>
                              </div>
                            ))
                          )}
                        </div>
                      ) : (
                        <p className="mt-2 text-xs text-muted-foreground">Save the layout to load continuity data.</p>
                      )}
                    </div>
                    <label className="flex flex-col gap-2 text-sm font-medium">
                      Provider
                      <select
                        value={providerName}
                        onChange={(event) => setProviderName(event.target.value)}
                        className="h-10 rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        {(providers.length ? providers : fallbackProviders()).map((provider) => (
                          <option key={provider.name} value={provider.name}>
                            {provider.display_name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <ProviderStatusPanel
                      provider={selectedProviderStatus}
                      health={providerHealth}
                      dryRun={dryRunResult}
                      compact
                      onRefresh={() => void loadProviderHealth(providerName)}
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <Button variant="outline" onClick={() => void dryRunSelectedPanel()} disabled={isDryRunning}>
                        <ShieldCheck className="h-4 w-4" />
                        {isDryRunning ? "Checking" : "Dry Run"}
                      </Button>
                      <Button
                        onClick={() => void renderSelectedPanel()}
                        disabled={selectedPanelIsRendering || Boolean(selectedProviderStatus && !selectedProviderStatus.configured)}
                        variant={selectedPanelJob?.status === "failed" ? "destructive" : "default"}
                      >
                        <ImageIcon className="h-4 w-4" />
                        {selectedPanelIsRendering ? "Rendering" : "Render Panel"}
                      </Button>
                    </div>
                    <Button variant="outline" onClick={() => setIsRenderDrawerOpen(true)}>
                      <History className="h-4 w-4" />
                      Render Director
                    </Button>
                    {latestRenderPrompt ? (
                      <div className="rounded-md border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
                        Prompt {latestRenderPrompt.prompt_version} - {latestRenderPrompt.quality_mode} - {latestRenderPrompt.size}
                      </div>
                    ) : null}
                    {selectedPanelJob ? (
                      <div className="rounded-md border bg-muted/40 px-3 py-2 text-sm">
                        <div className="flex items-center justify-between gap-3">
                          <span className="font-medium">{selectedPanelJob.provider}</span>
                          <Badge className={selectedPanelJob.status === "failed" ? "border-destructive/40 text-destructive" : ""}>
                            {selectedPanelJob.status}
                          </Badge>
                        </div>
                        {selectedPanelJob.error_message ? (
                          <p className="mt-2 text-xs text-destructive">{selectedPanelJob.error_message}</p>
                        ) : null}
                        {selectedPanelJob.status === "failed" ? (
                          <Button className="mt-3 w-full" variant="outline" size="sm" onClick={() => void retrySelectedPanelWithMock()}>
                            Retry with Mock
                          </Button>
                        ) : null}
                      </div>
                    ) : null}
                    <div className="grid grid-cols-2 gap-2">
                      <Button variant="outline" onClick={() => void addBubble("speech")}>
                        <MessageCircle className="h-4 w-4" />
                        Bubble
                      </Button>
                      <Button variant="outline" onClick={() => void addBubble("thought")}>
                        <Sparkles className="h-4 w-4" />
                        Thought
                      </Button>
                      <Button variant="outline" onClick={() => void addBubble("narration")}>
                        <Type className="h-4 w-4" />
                        Narration
                      </Button>
                      <Button variant="outline" onClick={() => void addBubble("shout")}>
                        <Zap className="h-4 w-4" />
                        Shout
                      </Button>
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">No panel selected</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Bubble</CardTitle>
                <CardDescription>{selectedBubble ? selectedBubble.kind : "None selected"}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {selectedPanel && selectedBubble ? (
                  <>
                    <Textarea
                      value={selectedBubble.text}
                      onChange={(event) => updateBubble(selectedPanel.id, { ...selectedBubble, text: event.target.value }, false)}
                    />
                    <div className="grid grid-cols-2 gap-3">
                      <NumberField
                        label="X"
                        value={selectedBubble.x}
                        onChange={(x) => updateBubble(selectedPanel.id, { ...selectedBubble, x }, false)}
                      />
                      <NumberField
                        label="Y"
                        value={selectedBubble.y}
                        onChange={(y) => updateBubble(selectedPanel.id, { ...selectedBubble, y }, false)}
                      />
                      <NumberField
                        label="Width"
                        value={selectedBubble.width}
                        onChange={(width) => updateBubble(selectedPanel.id, { ...selectedBubble, width }, false)}
                      />
                      <NumberField
                        label="Height"
                        value={selectedBubble.height}
                        onChange={(height) => updateBubble(selectedPanel.id, { ...selectedBubble, height }, false)}
                      />
                    </div>
                    <Button onClick={() => void persistBubble(selectedBubble)}>
                      <Save className="h-4 w-4" />
                      Save Bubble
                    </Button>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">No bubble selected</p>
                )}
              </CardContent>
            </Card>

            <Button variant="outline" onClick={() => updateLayout({ qa_overlay_enabled: !layout.qa_overlay_enabled })}>
              <View className="h-4 w-4" />
              {layout.qa_overlay_enabled ? "Hide QA" : "Show QA"}
            </Button>

            <Card>
              <CardHeader>
                <CardTitle>QA</CardTitle>
                <CardDescription>{qaReport ? `${qaReport.issues.length} issues` : "No report yet"}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <label className="flex flex-col gap-2 text-sm font-medium">
                  Export preset
                  <select
                    value={qaPreset}
                    onChange={(event) => setQaPreset(event.target.value as QAExportPreset)}
                    className="h-10 rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <option value="draft">Draft</option>
                    <option value="web">Web</option>
                    <option value="print">Print</option>
                  </select>
                </label>
                <Button onClick={() => void runQA()} disabled={isRunningQA}>
                  <ShieldCheck className="h-4 w-4" />
                  {isRunningQA ? "Checking" : "Run QA"}
                </Button>
                {qaReport ? (
                  <>
                    <div className="rounded-md border bg-muted/40 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium">Overall</span>
                        <span className={`text-2xl font-semibold ${scoreClass(qaReport.overall_score)}`}>
                          {qaReport.overall_score}
                        </span>
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                        {Object.entries(qaReport.scores).map(([label, value]) => (
                          <div key={label} className="rounded-md border bg-white px-2 py-1">
                            <span className="block capitalize text-muted-foreground">{label.replace("_", " ")}</span>
                            <span className="font-medium">{String(value)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="flex max-h-[320px] flex-col gap-2 overflow-auto">
                      {qaReport.issues.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No QA issues found.</p>
                      ) : (
                        qaReport.issues.map((issue) => (
                          <button
                            type="button"
                            key={issue.id}
                            onClick={() => focusIssue(issue)}
                            className={`rounded-md border bg-white px-3 py-2 text-left text-sm transition-colors hover:border-primary/60 ${
                              highlightedIssueId === issue.id ? "border-amber-500 bg-amber-50" : ""
                            }`}
                          >
                            <span className="flex items-center justify-between gap-2">
                              <span className="flex min-w-0 items-center gap-2 font-medium">
                                <AlertTriangle className={`h-4 w-4 shrink-0 ${issue.severity === "error" ? "text-destructive" : "text-amber-600"}`} />
                                <span className="truncate">{issue.code.replaceAll("_", " ")}</span>
                              </span>
                              <Badge className={issue.blocking ? "border-destructive/40 text-destructive" : ""}>
                                {issue.severity}
                              </Badge>
                            </span>
                            <span className="mt-1 block text-xs text-muted-foreground">{issue.message}</span>
                          </button>
                        ))
                      )}
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">Run QA to score layout, renders, lettering, and export readiness.</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Composite</CardTitle>
                <CardDescription>{compositePage ? `${compositePage.width}x${compositePage.height}` : "No final page yet"}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <Button onClick={() => void composePage()} disabled={isComposing}>
                  <ImageIcon className="h-4 w-4" />
                  {isComposing ? "Composing" : "Compose Page"}
                </Button>
                {compositePage ? (
                  <>
                    <img
                      src={assetImageUrl(compositePage.id, compositePage.public_url)}
                      alt="Final composed manga page"
                      className="max-h-[360px] rounded-md border bg-white object-contain"
                    />
                    <Button asChild variant="outline">
                      <a href={assetImageUrl(compositePage.id, compositePage.public_url)} download={compositePage.filename}>
                        <Download className="h-4 w-4" />
                        Download PNG
                      </a>
                    </Button>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">Compose a page to preview the final PNG.</p>
                )}
              </CardContent>
            </Card>
          </aside>
        </div>
      </div>
      {isRenderDrawerOpen ? (
        <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col border-l bg-white shadow-2xl">
          <div className="flex items-start justify-between gap-4 border-b px-5 py-4">
            <div>
              <h2 className="text-xl font-semibold tracking-normal">Render Director</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {selectedPanel ? `Panel ${selectedPanel.reading_order}` : "No panel selected"}
              </p>
            </div>
            <Button variant="outline" onClick={() => setIsRenderDrawerOpen(false)}>
              Close
            </Button>
          </div>
          <div className="flex-1 overflow-y-auto px-5 py-4">
            {selectedPanel ? (
              <div className="flex flex-col gap-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Controls</CardTitle>
                    <CardDescription>{selectedPanelIsRendering ? "Render in progress" : "Prompt and render settings"}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3">
                    <LearningFeedbackControls projectId={projectId} targetType="panel_render" targetId={selectedPanel.id} />
                    <div className="grid gap-3 sm:grid-cols-2">
                      <label className="flex flex-col gap-2 text-sm font-medium">
                        Provider
                        <select
                          value={providerName}
                          onChange={(event) => setProviderName(event.target.value)}
                          className="h-10 rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          {(providers.length ? providers : fallbackProviders()).map((provider) => (
                            <option key={provider.name} value={provider.name}>
                              {provider.display_name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="flex flex-col gap-2 text-sm font-medium">
                        Quality mode
                        <select
                          value={renderMode}
                          onChange={(event) => setRenderMode(event.target.value as PanelRenderMode)}
                          className="h-10 rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <option value="storyboard">Storyboard</option>
                          <option value="draft">Draft</option>
                          <option value="final">Final</option>
                          <option value="ultra">Ultra</option>
                        </select>
                      </label>
                    </div>
                    <Textarea
                      value={additionalInstruction}
                      onChange={(event) => setAdditionalInstruction(event.target.value)}
                      placeholder="Additional instruction for the next render"
                    />
                    <Textarea
                      value={advancedPromptOverride}
                      onChange={(event) => setAdvancedPromptOverride(event.target.value)}
                      placeholder="Advanced prompt override"
                      className="min-h-32"
                    />
                    <ProviderStatusPanel
                      provider={selectedProviderStatus}
                      health={providerHealth}
                      dryRun={dryRunResult}
                      onRefresh={() => void loadProviderHealth(providerName)}
                    />
                    <div className="grid gap-2 sm:grid-cols-2">
                      <Button variant="outline" onClick={() => void dryRunSelectedPanel()} disabled={isDryRunning}>
                        <ShieldCheck className="h-4 w-4" />
                        {isDryRunning ? "Checking" : "Dry Run"}
                      </Button>
                      <Button
                        onClick={() => void renderSelectedPanel()}
                        disabled={selectedPanelIsRendering || Boolean(selectedProviderStatus && !selectedProviderStatus.configured)}
                      >
                        <ImageIcon className="h-4 w-4" />
                        {selectedPanelIsRendering ? "Rendering" : "Generate Render"}
                      </Button>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      <label className="flex flex-col gap-2 text-sm font-medium">
                        Rerender control
                        <select
                          value={rerenderControl}
                          onChange={(event) => setRerenderControl(event.target.value as PanelRerenderControl)}
                          className="h-10 rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <option value="same_seed">Same seed</option>
                          <option value="new_seed">New seed</option>
                          <option value="preserve_layout">Preserve layout</option>
                          <option value="change_camera">Change camera</option>
                          <option value="change_expression">Change expression</option>
                          <option value="additional_instruction">Additional instruction</option>
                        </select>
                      </label>
                    </div>
                    <Button variant="outline" onClick={() => void rerenderSelectedPanel()} disabled={selectedPanelIsRendering || renderHistory.length === 0}>
                      <RefreshCcw className="h-4 w-4" />
                      Rerender
                    </Button>
                    {selectedPanelJob?.status === "failed" ? (
                      <Button variant="outline" onClick={() => void retrySelectedPanelWithMock()}>
                        Retry with Mock
                      </Button>
                    ) : null}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Assembled Prompt</CardTitle>
                    <CardDescription>{latestRenderPrompt ? `${latestRenderPrompt.size} - seed ${latestRenderPrompt.seed}` : "No prompt yet"}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3">
                    {latestRenderPrompt ? (
                      <>
                        <Textarea readOnly value={latestRenderPrompt.positive_prompt} className="min-h-56 font-mono text-xs" />
                        <Textarea readOnly value={latestRenderPrompt.negative_prompt} className="min-h-28 font-mono text-xs" />
                      </>
                    ) : (
                      <p className="text-sm text-muted-foreground">Generate a render to persist and inspect the director prompt.</p>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Render History</CardTitle>
                    <CardDescription>{isLoadingRenderData ? "Loading" : `${renderHistory.length} attempts`}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3">
                    {compareItems.length === 2 ? (
                      <div className="grid gap-3 sm:grid-cols-2">
                        {compareItems.map((item) => (
                          <div key={item.render.id} className="rounded-md border bg-muted/30 p-2">
                            {renderImageUrl(item.render) ? (
                              <img src={renderImageUrl(item.render) ?? ""} alt="Compared panel render" className="h-52 w-full rounded-md bg-white object-contain" />
                            ) : (
                              <div className="flex h-52 items-center justify-center rounded-md bg-white text-sm text-muted-foreground">No preview</div>
                            )}
                            <p className="mt-2 truncate text-xs text-muted-foreground">
                              {item.prompt?.quality_mode ?? item.job.provider} - seed {item.prompt?.seed ?? "n/a"}
                            </p>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {renderHistory.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No renders yet.</p>
                    ) : (
                      renderHistory.map((item) => (
                        <div key={item.render.id} className="rounded-md border bg-white p-3">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <Badge>{item.prompt?.quality_mode ?? item.job.provider}</Badge>
                                {item.approved ? <Badge className="border-emerald-600 text-emerald-700">approved</Badge> : null}
                                <span className="text-xs text-muted-foreground">seed {item.prompt?.seed ?? "n/a"}</span>
                              </div>
                              <p className="mt-1 truncate text-xs text-muted-foreground">{item.asset?.filename ?? item.render.storage_key}</p>
                            </div>
                            <div className="flex shrink-0 gap-2">
                              <Button variant="outline" size="sm" onClick={() => toggleCompareRender(item.render.id)}>
                                {compareRenderIds.includes(item.render.id) ? "Uncompare" : "Compare"}
                              </Button>
                              <Button variant="outline" size="sm" onClick={() => void approveRender(item.render.id)}>
                                <CheckCircle className="h-4 w-4" />
                                Approve
                              </Button>
                            </div>
                          </div>
                          {renderImageUrl(item.render) ? (
                            <img src={renderImageUrl(item.render) ?? ""} alt="Panel render history item" className="mt-3 max-h-64 w-full rounded-md border bg-white object-contain" />
                          ) : null}
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Select a panel to use the Render Director.</p>
            )}
          </div>
        </div>
      ) : null}
    </main>
  );
}

function assetImageUrl(assetId: string, publicUrl?: string | null) {
  return publicUrl || `${getApiBaseUrl()}/assets/${assetId}/download`;
}

function renderImageUrl(render: { asset_id?: string | null; public_url?: string | null }) {
  return render.public_url || (render.asset_id ? assetImageUrl(render.asset_id) : null);
}

function PanelButton({
  panel,
  selected,
  referenceSummary,
  locked,
  label,
  renderStatus,
  qaIssueCount,
  onClick
}: {
  panel: PanelLayout;
  selected: boolean;
  referenceSummary: PageReferencePacks["panels"][number] | null;
  locked: boolean;
  label?: string;
  renderStatus: string;
  qaIssueCount: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md border bg-white px-3 py-2 text-left text-sm transition-colors hover:border-primary/60 ${
        selected ? "border-primary bg-primary/5" : ""
      }`}
    >
      <span className="flex items-center justify-between gap-2">
        <span className="font-medium">Panel {panel.reading_order}</span>
        <span className="flex items-center gap-1">
          {locked ? <Lock className="h-4 w-4 text-primary" /> : null}
          {referenceSummary?.warning ? <AlertTriangle className="h-4 w-4 text-amber-600" /> : null}
        </span>
      </span>
      <span className="text-xs text-muted-foreground">
        {panel.width}x{panel.height} - {panel.bubbles.length} bubbles
      </span>
      <span className="mt-2 flex flex-wrap gap-1">
        <Badge className={renderStatus === "failed" ? "border-destructive/40 text-destructive" : renderStatus === "rendered" || renderStatus === "succeeded" ? "border-emerald-300 text-emerald-700" : ""}>
          {renderStatus}
        </Badge>
        <Badge>{panel.bubbles.length} bubbles</Badge>
        {qaIssueCount > 0 ? <Badge className="border-amber-400 text-amber-800">{qaIssueCount} QA</Badge> : null}
      </span>
      {label ? <span className="mt-1 block truncate text-xs text-primary">{label}</span> : null}
      {referenceSummary?.characters.length ? (
        <span className="mt-1 block truncate text-xs text-muted-foreground">{referenceSummary.characters.join(", ")}</span>
      ) : null}
    </button>
  );
}

function ProviderStatusPanel({
  provider,
  health,
  dryRun,
  compact = false,
  onRefresh
}: {
  provider: ImageProviderStatus | null;
  health: ProviderHealth | null;
  dryRun: PanelRenderDryRunResult | null;
  compact?: boolean;
  onRefresh: () => void;
}) {
  if (!provider) {
    return <div className="rounded-md border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">Provider registry unavailable.</div>;
  }
  const realProvider = provider.name !== "mock";
  return (
    <div className="rounded-md border bg-muted/30 p-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{provider.display_name}</span>
            <Badge className={provider.configured ? "border-emerald-600 text-emerald-700" : "border-amber-500 text-amber-700"}>
              {provider.configured ? "configured" : "not configured"}
            </Badge>
            {health ? <Badge>{health.status}</Badge> : null}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{provider.model_name ?? "No model configured"}</p>
        </div>
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCcw className="h-4 w-4" />
        </Button>
      </div>
      {realProvider ? (
        <div className="mt-3 rounded-md border border-amber-500/40 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          <AlertTriangle className="mr-1 inline h-3.5 w-3.5" />
          {provider.cost_warning}
        </div>
      ) : null}
      {provider.missing_env_vars.length ? (
        <p className="mt-2 text-xs text-amber-700">Missing env: {provider.missing_env_vars.join(", ")}</p>
      ) : null}
      {health?.message ? <p className="mt-2 text-xs text-muted-foreground">{health.message}</p> : null}
      {!compact ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <ProviderCapability label="Generate" value={provider.capabilities.supports_image_generation} />
          <ProviderCapability label="Edit" value={provider.capabilities.supports_image_editing} />
          <ProviderCapability label="References" value={provider.capabilities.supports_references} />
          <ProviderCapability label="Seeds" value={provider.capabilities.supports_seeds} />
          <ProviderCapability label="Async jobs" value={provider.capabilities.supports_async_jobs} />
          <div className="rounded-md border bg-white px-2 py-2 text-xs">
            Max {provider.max_resolution.width}x{provider.max_resolution.height}
          </div>
        </div>
      ) : null}
      {dryRun && dryRun.provider.name === provider.name ? (
        <div className="mt-3 rounded-md border bg-white px-3 py-2 text-xs">
          <div className="flex items-center justify-between gap-3">
            <span className="font-medium">Dry-run</span>
            <Badge className={dryRun.can_render ? "border-emerald-600 text-emerald-700" : "border-amber-500 text-amber-700"}>
              {dryRun.can_render ? "ready" : "blocked"}
            </Badge>
          </div>
          <p className="mt-1 text-muted-foreground">
            {dryRun.requested_size} - {dryRun.quality_mode}
          </p>
          {dryRun.warnings.length ? (
            <ul className="mt-2 list-disc pl-4 text-amber-700">
              {dryRun.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-muted-foreground">Prompt and provider settings validated without calling a paid API.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}

function ProviderCapability({ label, value }: { label: string; value: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-md border bg-white px-2 py-2 text-xs">
      <span>{label}</span>
      <Badge className={value ? "border-emerald-600 text-emerald-700" : ""}>{value ? "yes" : "no"}</Badge>
    </div>
  );
}

function fallbackProviders(): ImageProviderStatus[] {
  return [
    {
      name: "mock",
      display_name: "Mock",
      model_name: "mock-image-v1",
      capabilities: {
        supports_image_generation: true,
        supports_image_editing: true,
        supports_references: false,
        supports_seeds: true,
        supports_async_jobs: false
      },
      max_resolution: { width: 4096, height: 4096 },
      requires_env_vars: [],
      configured: true,
      missing_env_vars: [],
      cost_warning: "No external calls or paid usage.",
      notes: "Local deterministic mock provider."
    },
    {
      name: "openai",
      display_name: "OpenAI",
      model_name: null,
      capabilities: {
        supports_image_generation: true,
        supports_image_editing: false,
        supports_references: false,
        supports_seeds: false,
        supports_async_jobs: false
      },
      max_resolution: { width: 2048, height: 2048 },
      requires_env_vars: ["OPENAI_API_KEY", "OPENAI_IMAGE_MODEL"],
      configured: false,
      missing_env_vars: ["OPENAI_API_KEY"],
      cost_warning: "Real OpenAI image generation may incur API costs.",
      notes: "Configure env vars before use."
    },
    {
      name: "comfyui",
      display_name: "ComfyUI",
      model_name: "comfyui-workflow",
      capabilities: {
        supports_image_generation: true,
        supports_image_editing: false,
        supports_references: true,
        supports_seeds: true,
        supports_async_jobs: true
      },
      max_resolution: { width: 4096, height: 4096 },
      requires_env_vars: ["COMFYUI_BASE_URL"],
      configured: false,
      missing_env_vars: ["COMFYUI_BASE_URL"],
      cost_warning: "Local or remote ComfyUI cost depends on your deployment.",
      notes: "Requires a workflow template."
    }
  ];
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="flex flex-col gap-2 text-sm font-medium">
      {label}
      <Input type="number" min={label === "Order" ? 1 : 0} value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

function rectPolygon(x: number, y: number, width: number, height: number) {
  return [
    { x, y },
    { x: x + width, y },
    { x: x + width, y: y + height },
    { x, y: y + height }
  ];
}

function movePanel(panel: PanelLayout, updates: Partial<Pick<PanelLayout, "x" | "y">>) {
  const nextX = updates.x ?? panel.x;
  const nextY = updates.y ?? panel.y;
  return {
    ...panel,
    x: nextX,
    y: nextY,
    polygon: rectPolygon(nextX, nextY, panel.width, panel.height)
  };
}

function resizePanel(panel: PanelLayout, updates: Partial<Pick<PanelLayout, "width" | "height">>) {
  const nextWidth = updates.width ?? panel.width;
  const nextHeight = updates.height ?? panel.height;
  return {
    ...panel,
    width: nextWidth,
    height: nextHeight,
    polygon: rectPolygon(panel.x, panel.y, nextWidth, nextHeight)
  };
}

function bubbleDefaults(kind: BubbleKind) {
  if (kind === "narration") {
    return { width: 320, height: 96, text: "Narration" };
  }
  if (kind === "thought") {
    return { width: 280, height: 140, text: "Thought" };
  }
  if (kind === "shout") {
    return { width: 300, height: 140, text: "Shout!" };
  }
  return { width: 260, height: 130, text: "Dialogue" };
}

function scoreClass(score: number) {
  if (score >= 85) {
    return "text-emerald-700";
  }
  if (score >= 65) {
    return "text-amber-700";
  }
  return "text-destructive";
}

const PAGE_TYPE_OPTIONS: PageType[] = [
  "standard",
  "splash",
  "double_spread_left",
  "double_spread_right",
  "silent_page",
  "action_sequence",
  "dialogue_scene",
  "reveal_page",
  "comedy_reaction",
  "horror_build",
  "romantic_pause",
  "exposition_page"
];
