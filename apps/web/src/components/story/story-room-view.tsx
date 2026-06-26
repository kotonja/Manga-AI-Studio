"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Activity, ArrowLeft, BookOpen, FileJson, Layers3, RefreshCcw, Wand2 } from "lucide-react";
import type { ChapterPlan, PagePlan, PacingAnalysisResult, PacingRebalanceResult, ProjectDetail, StoryBible } from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { LearningFeedbackControls } from "@/components/learning/learning-feedback-controls";
import { Textarea } from "@/components/ui/textarea";

export function StoryRoomView({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [storyBible, setStoryBible] = useState<StoryBible | null>(null);
  const [storyJson, setStoryJson] = useState("");
  const [chapters, setChapters] = useState<ChapterPlan[]>([]);
  const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null);
  const [pagePlansByChapter, setPagePlansByChapter] = useState<Record<string, PagePlan[]>>({});
  const [pacingAnalysis, setPacingAnalysis] = useState<PacingAnalysisResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isBusy, setIsBusy] = useState(false);
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadStoryRoom() {
    setIsLoading(true);
    setError(null);
    try {
      const nextProject = await apiFetch<ProjectDetail>(`/projects/${projectId}`);
      setProject(nextProject);

      try {
        const bible = await apiFetch<StoryBible>(`/projects/${projectId}/story/bible`);
        setStoryBible(bible);
        setStoryJson(JSON.stringify(bible, null, 2));
      } catch {
        setStoryBible(null);
        setStoryJson("");
      }

      const nextChapters = await apiFetch<ChapterPlan[]>(`/projects/${projectId}/story/chapters`).catch(() => []);
      setChapters(nextChapters);
      setSelectedChapterId((current) => current ?? nextChapters[0]?.id ?? null);
      const nextPlans: Record<string, PagePlan[]> = {};
      await Promise.all(
        nextChapters.map(async (chapter) => {
          if (!chapter.id) {
            return;
          }
          nextPlans[chapter.id] = await apiFetch<PagePlan[]>(`/chapters/${chapter.id}/story/page-plans`).catch(() => []);
        })
      );
      setPagePlansByChapter(nextPlans);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load Story Room");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadStoryRoom();
  }, [projectId]);

  const selectedChapter = useMemo(() => {
    return chapters.find((chapter) => chapter.id === selectedChapterId) ?? chapters[0] ?? null;
  }, [chapters, selectedChapterId]);

  async function generateStoryBible() {
    setIsBusy(true);
    setError(null);
    try {
      const bible = await apiFetch<StoryBible>(`/projects/${projectId}/story/generate-bible`, {
        method: "POST",
        body: JSON.stringify({
          premise: project?.description || project?.name || null,
          genre: null,
          tone: null,
          target_audience: null,
          chapter_count: 3
        })
      });
      setStoryBible(bible);
      setStoryJson(JSON.stringify(bible, null, 2));
      setJsonError(null);
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : "Unable to generate story bible");
    } finally {
      setIsBusy(false);
    }
  }

  async function generateChapterPlan() {
    setIsBusy(true);
    setError(null);
    try {
      const nextChapters = await apiFetch<ChapterPlan[]>(`/projects/${projectId}/story/generate-chapter-plan`, {
        method: "POST"
      });
      setChapters(nextChapters);
      setSelectedChapterId(nextChapters[0]?.id ?? null);
      setPagePlansByChapter({});
      setPacingAnalysis(null);
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : "Unable to generate chapter plan");
    } finally {
      setIsBusy(false);
    }
  }

  async function generatePagePlans(chapterId: string) {
    setIsBusy(true);
    setError(null);
    try {
      const pagePlans = await apiFetch<PagePlan[]>(`/chapters/${chapterId}/story/generate-page-plans`, {
        method: "POST"
      });
      setPagePlansByChapter((current) => ({ ...current, [chapterId]: pagePlans }));
      setPacingAnalysis(null);
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : "Unable to generate page plans");
    } finally {
      setIsBusy(false);
    }
  }

  function updateStoryJson(value: string) {
    setStoryJson(value);
    try {
      const parsed = JSON.parse(value) as StoryBible;
      setStoryBible(parsed);
      setJsonError(null);
    } catch (parseError) {
      setJsonError(parseError instanceof Error ? parseError.message : "Invalid JSON");
    }
  }

  async function analyzePacing() {
    setIsBusy(true);
    setError(null);
    try {
      const result = await apiFetch<PacingAnalysisResult>(`/projects/${projectId}/pacing/analyze`, {
        method: "POST"
      });
      setPacingAnalysis(result);
      await refreshPagePlans(chapters);
    } catch (analyzeError) {
      setError(analyzeError instanceof Error ? analyzeError.message : "Unable to analyze pacing");
    } finally {
      setIsBusy(false);
    }
  }

  async function rebalancePacing(chapterId: string) {
    setIsBusy(true);
    setError(null);
    try {
      const result = await apiFetch<PacingRebalanceResult>(`/chapters/${chapterId}/pacing/rebalance`, {
        method: "POST"
      });
      setPacingAnalysis(result);
      await refreshPagePlans(chapters);
    } catch (rebalanceError) {
      setError(rebalanceError instanceof Error ? rebalanceError.message : "Unable to rebalance pacing");
    } finally {
      setIsBusy(false);
    }
  }

  async function refreshPagePlans(sourceChapters: ChapterPlan[]) {
    const nextPlans: Record<string, PagePlan[]> = {};
    await Promise.all(
      sourceChapters.map(async (chapter) => {
        if (!chapter.id) {
          return;
        }
        nextPlans[chapter.id] = await apiFetch<PagePlan[]>(`/chapters/${chapter.id}/story/page-plans`).catch(() => []);
      })
    );
    setPagePlansByChapter(nextPlans);
  }

  if (isLoading && project === null) {
    return (
      <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-md border bg-white px-4 py-8 text-sm text-muted-foreground">
          Loading Story Room
        </div>
      </main>
    );
  }

  if (project === null) {
    return (
      <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-md border bg-white px-4 py-8 text-sm text-destructive">
          {error || "Project not found"}
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
                <h1 className="text-3xl font-semibold tracking-normal">Story Room</h1>
                <Badge>{project.name}</Badge>
              </div>
              <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
                {storyBible?.logline || project.description || "Story planning workspace"}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={() => void loadStoryRoom()}>
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </Button>
            <Button onClick={() => void generateStoryBible()} disabled={isBusy}>
              <Wand2 className="h-4 w-4" />
              Generate Story Bible
            </Button>
            <Button variant="outline" onClick={() => void analyzePacing()} disabled={isBusy}>
              <Activity className="h-4 w-4" />
              Analyze Pacing
            </Button>
          </div>
        </header>

        {error ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle>Story Bible Summary</CardTitle>
            <CardDescription>Editable source of truth is still the JSON view; this section is optimized for review.</CardDescription>
          </CardHeader>
          <CardContent>
            {storyBible ? (
              <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
                <div className="rounded-md border bg-white p-4">
                  <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">Logline</p>
                  <p className="mt-2 text-lg font-semibold">{storyBible.logline}</p>
                  <p className="mt-4 text-sm text-muted-foreground">{storyBible.synopsis}</p>
                  <div className="mt-4">
                    <LearningFeedbackControls projectId={projectId} targetType="story" targetId={storyBible.id} />
                  </div>
                </div>
                <div className="flex flex-col gap-3">
                  <StorySection label="Main Conflict" value={storyBible.main_conflict} />
                  <StorySection label="Themes" value={storyBible.themes.join(", ") || "No themes yet"} />
                  <StorySection label="World Rules" value={storyBible.world_rules.slice(0, 3).join(" / ") || "No world rules yet"} />
                </div>
              </div>
            ) : (
              <div className="rounded-md border bg-muted/30 px-4 py-8 text-center text-sm text-muted-foreground">
                No story bible yet. Generate one to unlock chapter cards, world rules, page plans, and panel plans.
              </div>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
          <section className="flex min-w-0 flex-col gap-4">
            <div className="grid gap-4 lg:grid-cols-3">
              <StoryMetric label="Genre" value={storyBible?.genre} />
              <StoryMetric label="Tone" value={storyBible?.tone} />
              <StoryMetric label="Audience" value={storyBible?.target_audience} />
            </div>

            <PacingGraph
              analysis={pacingAnalysis}
              pages={Object.values(pagePlansByChapter).flat()}
              selectedChapterId={selectedChapter?.id ?? null}
              isBusy={isBusy}
              onAnalyze={analyzePacing}
              onRebalance={rebalancePacing}
            />

            <Card>
              <CardHeader className="flex flex-row items-center justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <BookOpen className="h-4 w-4" />
                    Chapter Plan
                  </CardTitle>
                  <CardDescription>{chapters.length ? `${chapters.length} chapters` : "No chapters"}</CardDescription>
                </div>
                <Button onClick={() => void generateChapterPlan()} disabled={!storyBible || isBusy}>
                  <Wand2 className="h-4 w-4" />
                  Generate Chapter Plan
                </Button>
              </CardHeader>
              <CardContent className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
                <div className="flex flex-col gap-2">
                  {chapters.length === 0 ? (
                    <div className="rounded-md border bg-background px-3 py-4 text-sm text-muted-foreground">
                      No chapter plans yet
                    </div>
                  ) : (
                    chapters.map((chapter) => (
                      <button
                        type="button"
                        key={chapter.id ?? chapter.chapter_number}
                        onClick={() => setSelectedChapterId(chapter.id ?? null)}
                        className={cn(
                          "rounded-md border bg-background px-3 py-3 text-left text-sm transition-colors hover:border-primary/60",
                          selectedChapter?.id === chapter.id && "border-primary bg-primary/5"
                        )}
                      >
                        <span className="block font-medium">
                          {chapter.chapter_number}. {chapter.title}
                        </span>
                        <span className="text-xs text-muted-foreground">{chapter.scenes.length} scenes</span>
                      </button>
                    ))
                  )}
                </div>

                {selectedChapter ? (
                  <ChapterPlanViewer
                    chapter={selectedChapter}
                    pages={selectedChapter.id ? pagePlansByChapter[selectedChapter.id] ?? [] : []}
                    isBusy={isBusy}
                    onGeneratePagePlans={generatePagePlans}
                  />
                ) : (
                  <div className="rounded-md border bg-background px-4 py-8 text-sm text-muted-foreground">
                    No chapter selected
                  </div>
                )}
              </CardContent>
            </Card>
          </section>

          <aside className="flex min-w-0 flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileJson className="h-4 w-4" />
                  Story Bible JSON
                </CardTitle>
                <CardDescription>{jsonError ? "Invalid JSON" : storyBible ? "Loaded" : "Empty"}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <Textarea
                  value={storyJson}
                  onChange={(event) => updateStoryJson(event.target.value)}
                  className="min-h-[560px] resize-y font-mono text-xs leading-relaxed"
                  spellCheck={false}
                />
                {jsonError ? (
                  <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                    {jsonError}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </aside>
        </div>
      </div>
    </main>
  );
}

function StoryMetric({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-md border bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">{label}</p>
      <p className="mt-2 text-sm font-semibold">{value || "Unplanned"}</p>
    </div>
  );
}

function StorySection({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-muted/30 p-3">
      <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm">{value}</p>
    </div>
  );
}

function PacingGraph({
  analysis,
  pages,
  selectedChapterId,
  isBusy,
  onAnalyze,
  onRebalance
}: {
  analysis: PacingAnalysisResult | null;
  pages: PagePlan[];
  selectedChapterId: string | null;
  isBusy: boolean;
  onAnalyze: () => void;
  onRebalance: (chapterId: string) => void;
}) {
  const graphPages = analysis?.pages.length
    ? analysis.pages
    : pages.map((page) => ({
        page_plan_id: page.id ?? `page-${page.page_number}`,
        page_number: page.page_number,
        page_role: page.page_role,
        emotional_intensity: page.emotional_intensity,
        action_intensity: page.action_intensity,
        dialogue_density: page.dialogue_density,
        silence_level: page.silence_level,
        reveal_level: page.reveal_level,
        page_turn_importance: page.page_turn_importance,
        recommended_page_type: page.recommended_page_type,
        pacing_notes: page.pacing_notes,
        panel_count: page.panels.length,
        panels: []
      }));
  const warnings = analysis?.recommendations.filter((item) => item.code === "overcrowded_dialogue" || item.code === "panel_count_change") ?? [];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Manga Pacing
          </CardTitle>
          <CardDescription>
            {graphPages.length ? `${graphPages.length} scored pages` : "No page plans scored yet"}
          </CardDescription>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void onAnalyze()} disabled={isBusy}>
            Analyze
          </Button>
          <Button onClick={() => selectedChapterId && void onRebalance(selectedChapterId)} disabled={isBusy || !selectedChapterId}>
            Rebalance
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {graphPages.length ? (
          <div className="overflow-x-auto pb-1">
            <div className="flex min-w-[560px] items-end gap-3">
              {graphPages.map((page) => (
                <div key={page.page_plan_id} className="flex min-w-20 flex-1 flex-col gap-2">
                  <div className="flex h-32 items-end gap-1 rounded-md border bg-white p-2">
                    <MetricBar label="emotion" value={page.emotional_intensity} className="bg-primary" />
                    <MetricBar label="action" value={page.action_intensity} className="bg-destructive" />
                    <MetricBar label="dialogue" value={page.dialogue_density} className="bg-amber-500" />
                    <MetricBar label="reveal" value={page.reveal_level} className="bg-slate-700" />
                  </div>
                  <div className="text-center">
                    <p className="text-xs font-semibold">P{page.page_number}</p>
                    <p className="truncate text-[11px] text-muted-foreground">{String(page.recommended_page_type).replaceAll("_", " ")}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="rounded-md border bg-muted/30 px-4 py-6 text-sm text-muted-foreground">
            Generate page plans, then run pacing analysis to see emotional intensity, dialogue density, reveal pressure, and page-turn candidates.
          </div>
        )}

        {analysis?.summary ? (
          <div className="grid gap-3 md:grid-cols-4">
            <StoryMetric label="Avg Emotion" value={String(analysis.summary.average_emotional_intensity ?? "-")} />
            <StoryMetric label="Avg Dialogue" value={String(analysis.summary.average_dialogue_density ?? "-")} />
            <StoryMetric label="Warnings" value={String(analysis.summary.warning_count ?? 0)} />
            <StoryMetric label="Turns" value={Array.isArray(analysis.summary.page_turn_candidates) ? analysis.summary.page_turn_candidates.join(", ") || "-" : "-"} />
          </div>
        ) : null}

        {warnings.length ? (
          <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
            <p className="font-medium">Dialogue density warnings</p>
            <div className="mt-2 grid gap-1 text-xs">
              {warnings.slice(0, 4).map((item) => (
                <p key={`${item.code}-${item.target_id}`}>Page {item.page_number}: {item.message}</p>
              ))}
            </div>
          </div>
        ) : null}

        {analysis?.recommendations.length ? (
          <div className="grid gap-2">
            {analysis.recommendations.slice(0, 6).map((item) => (
              <div key={`${item.code}-${item.target_id}-${item.suggested_action}`} className="rounded-md border bg-white p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge>{item.code.replaceAll("_", " ")}</Badge>
                  {item.page_number ? <Badge>Page {item.page_number}</Badge> : null}
                </div>
                <p className="mt-2 text-muted-foreground">{item.message}</p>
              </div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function MetricBar({ label, value, className }: { label: string; value: number; className: string }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-end gap-1">
      <div title={`${label}: ${value}`} className={cn("w-full min-w-2 rounded-sm", className)} style={{ height: `${Math.max(6, value)}%` }} />
      <span className="sr-only">{label}</span>
    </div>
  );
}

function ChapterPlanViewer({
  chapter,
  pages,
  isBusy,
  onGeneratePagePlans
}: {
  chapter: ChapterPlan;
  pages: PagePlan[];
  isBusy: boolean;
  onGeneratePagePlans: (chapterId: string) => void;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="rounded-md border bg-background p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold">{chapter.title}</h2>
            <p className="mt-2 text-sm text-muted-foreground">{chapter.summary}</p>
          </div>
          {chapter.id ? (
            <Button onClick={() => void onGeneratePagePlans(chapter.id as string)} disabled={isBusy}>
              <Layers3 className="h-4 w-4" />
              Page Plans
            </Button>
          ) : null}
        </div>
        <p className="mt-3 text-sm">
          <span className="font-medium">Goal:</span> {chapter.goal}
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {chapter.scenes.map((scene) => (
          <div key={scene.id ?? scene.scene_order} className="rounded-md border bg-white p-3">
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-semibold">
                {scene.scene_order}. {scene.title}
              </p>
              <Badge>{scene.location_name || "Location"}</Badge>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">{scene.summary}</p>
            {scene.emotional_turn ? <p className="mt-2 text-xs">{scene.emotional_turn}</p> : null}
          </div>
        ))}
      </div>

      {pages.length ? (
        <div className="flex flex-col gap-3">
          {pages.map((page) => (
            <PagePlanCard key={page.id ?? page.page_number} page={page} />
          ))}
        </div>
      ) : (
        <div className="rounded-md border bg-background px-4 py-5 text-sm text-muted-foreground">No page plans yet</div>
      )}
    </div>
  );
}

function PagePlanCard({ page }: { page: PagePlan }) {
  return (
    <div className="rounded-md border bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold">Page {page.page_number}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{page.summary}</p>
        </div>
        <Badge>{page.pacing}</Badge>
      </div>
      <div className="mt-3 grid gap-2 text-xs md:grid-cols-4">
        <PacingMini label="Emotion" value={page.emotional_intensity} />
        <PacingMini label="Action" value={page.action_intensity} />
        <PacingMini label="Dialogue" value={page.dialogue_density} />
        <PacingMini label="Reveal" value={page.reveal_level} />
      </div>
      {page.pacing_notes ? <p className="mt-3 text-xs text-muted-foreground">{page.pacing_notes}</p> : null}
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {page.panels.map((panel) => (
          <details key={panel.id ?? panel.panel_order} className="rounded-md border bg-background p-3" open={panel.panel_order === 1}>
            <summary className="cursor-pointer list-none">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-semibold">Panel {panel.panel_order}</p>
                <div className="flex flex-wrap justify-end gap-1">
                  <Badge>{panel.shot_type}</Badge>
                  <Badge>{panel.recommended_panel_size}</Badge>
                  {panel.silence ? <Badge className="border-slate-400 text-slate-700">silent</Badge> : null}
                </div>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">{panel.story_beat}</p>
            </summary>
            <div className="mt-3 border-t pt-3">
              <p className="text-xs">
                {panel.camera_angle} - {panel.emotional_intent}
              </p>
              <p className="mt-2 text-xs text-muted-foreground">
                Impact {panel.impact_level} - dialogue {panel.dialogue_weight} - {panel.transition_type.replaceAll("_", " ")}
              </p>
              <p className="mt-2 text-xs text-muted-foreground">{panel.visual_notes}</p>
              {panel.dialogue ? <p className="mt-2 text-xs font-medium">"{panel.dialogue}"</p> : null}
              {panel.narration ? <p className="mt-2 text-xs italic">{panel.narration}</p> : null}
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}

function PacingMini({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border bg-background p-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-semibold">{value}</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
    </div>
  );
}
