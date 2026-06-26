"use client";

import Link from "next/link";
import { ArrowLeft, BookOpen, CheckCircle2, Circle, CircleAlert, Clapperboard, Loader2, PanelTop, RefreshCcw, Sparkles } from "lucide-react";
import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import type {
  DirectorGenerateDraftRequest,
  DirectorGenerateDraftResponse,
  DirectorProgressEvent,
  GenerationJob,
  JobEvent,
  ProjectDetail,
  ProviderName,
  ReadingDirection
} from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type DirectorDraft = {
  premise: string;
  chapter_count: number;
  page_count: number;
  target_audience: string;
  genre: string[];
  tone: string;
  reading_direction: ReadingDirection;
  render_provider: ProviderName;
  quality_mode: DirectorGenerateDraftRequest["quality_mode"];
  allow_mock_assets: boolean;
};

const defaultDraft: DirectorDraft = {
  premise: "A lonely swordsman protects a ghost child in a ruined city.",
  chapter_count: 1,
  page_count: 4,
  target_audience: "Teen and young adult manga readers",
  genre: ["dark fantasy", "action"],
  tone: "melancholic, cinematic, hopeful",
  reading_direction: "rtl",
  render_provider: "mock",
  quality_mode: "fast",
  allow_mock_assets: true
};

const genreOptions = ["action", "dark fantasy", "drama", "mystery", "romance", "sci-fi", "slice of life", "supernatural"];
const toneOptions = ["melancholic, cinematic, hopeful", "tense and atmospheric", "warm and adventurous", "bleak and suspenseful"];
const audienceOptions = ["Teen and young adult manga readers", "All-ages adventure readers", "Older teen seinen readers"];

const progressSteps: Array<{ value: DirectorProgressEvent; label: string }> = [
  { value: "queued", label: "Queued" },
  { value: "generating_story_bible", label: "Story Bible" },
  { value: "generating_characters", label: "Characters" },
  { value: "generating_style", label: "Style" },
  { value: "planning_pages", label: "Plans" },
  { value: "creating_layouts", label: "Layouts" },
  { value: "rendering_panels", label: "Renders" },
  { value: "composing_pages", label: "Composites" },
  { value: "running_qa", label: "QA" },
  { value: "exporting", label: "Export" },
  { value: "complete", label: "Complete" },
  { value: "failed", label: "Failed" }
];

export function DirectorModeView({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [draft, setDraft] = useState<DirectorDraft>(defaultDraft);
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [isLoadingProject, setIsLoadingProject] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadProject() {
    setIsLoadingProject(true);
    setError(null);
    try {
      const nextProject = await apiFetch<ProjectDetail>(`/projects/${projectId}`);
      setProject(nextProject);
      if (!draft.premise.trim() && nextProject.description) {
        setDraft((current) => ({ ...current, premise: nextProject.description ?? current.premise }));
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load project");
    } finally {
      setIsLoadingProject(false);
    }
  }

  useEffect(() => {
    void loadProject();
  }, [projectId]);

  const latestEvent = events.at(-1);
  const activeEvent = latestEvent?.event_type ?? (job?.status === "failed" ? "failed" : null);
  const completed = job?.status === "succeeded" || activeEvent === "complete";
  const failed = job?.status === "failed" || activeEvent === "failed";

  const completedStepIndex = useMemo(() => {
    if (failed) {
      return progressSteps.findIndex((step) => step.value === activeEvent);
    }
    if (completed) {
      return progressSteps.findIndex((step) => step.value === "complete");
    }
    return Math.max(
      -1,
      progressSteps.findIndex((step) => step.value === activeEvent)
    );
  }, [activeEvent, completed, failed]);

  useEffect(() => {
    if (!job || job.status === "succeeded" || job.status === "failed") {
      return;
    }

    const timer = window.setInterval(async () => {
      try {
        const [nextJob, nextEvents] = await Promise.all([
          apiFetch<GenerationJob>(`/jobs/${job.id}`),
          apiFetch<JobEvent[]>(`/jobs/${job.id}/events`)
        ]);
        setJob(nextJob);
        setEvents(nextEvents);
        if (nextJob.status === "succeeded") {
          await loadProject();
          setIsGenerating(false);
        }
        if (nextJob.status === "failed") {
          setError(nextJob.error_message ?? "Director job failed");
          setIsGenerating(false);
        }
      } catch (pollError) {
        setError(pollError instanceof Error ? pollError.message : "Unable to poll director job");
        setIsGenerating(false);
      }
    }, 1600);

    return () => window.clearInterval(timer);
  }, [job]);

  async function generateDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.premise.trim()) {
      setError("Premise is required");
      return;
    }

    setIsGenerating(true);
    setError(null);
    setJob(null);
    setEvents([]);
    try {
      const payload: DirectorGenerateDraftRequest = {
        ...draft,
        premise: draft.premise.trim(),
        genre: draft.genre.length > 0 ? draft.genre : ["drama"]
      };
      const response = await apiFetch<DirectorGenerateDraftResponse>(`/projects/${projectId}/director/generate-draft`, {
        method: "POST",
        body: JSON.stringify(payload)
      });
      const [nextJob, nextEvents] = await Promise.all([
        apiFetch<GenerationJob>(`/jobs/${response.job_id}`),
        apiFetch<JobEvent[]>(`/jobs/${response.job_id}/events`)
      ]);
      setJob(nextJob);
      setEvents(nextEvents);
      if (nextJob.status === "succeeded") {
        await loadProject();
        setIsGenerating(false);
      }
      if (nextJob.status === "failed") {
        setError(nextJob.error_message ?? "Director job failed");
        setIsGenerating(false);
      }
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : "Unable to generate draft manga");
      setIsGenerating(false);
    }
  }

  function toggleGenre(value: string) {
    setDraft((current) => {
      const selected = current.genre.includes(value);
      return {
        ...current,
        genre: selected ? current.genre.filter((item) => item !== value) : [...current.genre, value]
      };
    });
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
                <h1 className="text-3xl font-semibold tracking-normal">Director Mode</h1>
                {job ? <JobStatusBadge status={job.status} /> : null}
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{project?.name ?? "Draft manga project"}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={() => void loadProject()} disabled={isLoadingProject}>
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </Button>
            {project?.pages[0] ? (
              <Button asChild variant="outline">
                <Link href={`/projects/${projectId}/pages/${project.pages[0].id}/studio`}>
                  <PanelTop className="h-4 w-4" />
                  First Page
                </Link>
              </Button>
            ) : null}
          </div>
        </header>

        {error ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span>{error}</span>
              <Button variant="outline" size="sm" onClick={() => {
                setError(null);
                setIsGenerating(false);
              }}>
                Recover
              </Button>
            </div>
          </div>
        ) : null}

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
          <Card>
            <CardHeader>
              <CardTitle>Draft Manga</CardTitle>
              <CardDescription>{draft.page_count} pages, {draft.reading_direction}</CardDescription>
            </CardHeader>
            <CardContent>
              <form className="flex flex-col gap-5" onSubmit={generateDraft}>
                <label className="flex flex-col gap-2 text-sm font-medium">
                  Premise
                  <Textarea
                    className="min-h-44 text-base leading-7"
                    value={draft.premise}
                    onChange={(event) => setDraft((current) => ({ ...current, premise: event.target.value }))}
                  />
                </label>

                <div className="grid gap-4 md:grid-cols-2">
                  <label className="flex flex-col gap-2 text-sm font-medium">
                    Target Audience
                    <select
                      className="h-10 rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      value={draft.target_audience}
                      onChange={(event) => setDraft((current) => ({ ...current, target_audience: event.target.value }))}
                    >
                      {audienceOptions.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="flex flex-col gap-2 text-sm font-medium">
                    Tone
                    <select
                      className="h-10 rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      value={draft.tone}
                      onChange={(event) => setDraft((current) => ({ ...current, tone: event.target.value }))}
                    >
                      {toneOptions.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="flex flex-col gap-2 text-sm font-medium">
                    Chapters
                    <Input
                      type="number"
                      min={1}
                      max={24}
                      value={draft.chapter_count}
                      onChange={(event) =>
                        setDraft((current) => ({ ...current, chapter_count: clampNumber(Number(event.target.value), 1, 24) }))
                      }
                    />
                  </label>

                  <label className="flex flex-col gap-2 text-sm font-medium">
                    Pages
                    <Input
                      type="number"
                      min={1}
                      max={64}
                      value={draft.page_count}
                      onChange={(event) =>
                        setDraft((current) => ({ ...current, page_count: clampNumber(Number(event.target.value), 1, 64) }))
                      }
                    />
                  </label>

                  <label className="flex flex-col gap-2 text-sm font-medium">
                    Reading Direction
                    <select
                      className="h-10 rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      value={draft.reading_direction}
                      onChange={(event) => setDraft((current) => ({ ...current, reading_direction: event.target.value as ReadingDirection }))}
                    >
                      <option value="rtl">Right to left</option>
                      <option value="ltr">Left to right</option>
                      <option value="vertical-rl">Vertical right to left</option>
                    </select>
                  </label>

                  <label className="flex flex-col gap-2 text-sm font-medium">
                    Quality Mode
                    <select
                      className="h-10 rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      value={draft.quality_mode}
                      onChange={(event) =>
                        setDraft((current) => ({
                          ...current,
                          quality_mode: event.target.value as DirectorGenerateDraftRequest["quality_mode"]
                        }))
                      }
                    >
                      <option value="fast">Fast</option>
                      <option value="balanced">Balanced</option>
                      <option value="high">High</option>
                    </select>
                  </label>

                  <label className="flex flex-col gap-2 text-sm font-medium">
                    Render Provider
                    <select
                      className="h-10 rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      value={draft.render_provider}
                      onChange={(event) => setDraft((current) => ({ ...current, render_provider: event.target.value }))}
                    >
                      <option value="mock">Mock</option>
                      <option value="openai">OpenAI</option>
                      <option value="comfyui">ComfyUI</option>
                    </select>
                  </label>

                  <label className="flex items-center gap-3 rounded-md border bg-muted/30 px-4 py-3 text-sm font-medium md:self-end">
                    <input
                      type="checkbox"
                      checked={draft.allow_mock_assets}
                      onChange={(event) => setDraft((current) => ({ ...current, allow_mock_assets: event.target.checked }))}
                    />
                    Allow mock fallback
                  </label>
                </div>

                <div className="flex flex-col gap-2">
                  <span className="text-sm font-medium">Genre</span>
                  <div className="flex flex-wrap gap-2">
                    {genreOptions.map((genre) => {
                      const selected = draft.genre.includes(genre);
                      return (
                        <button
                          key={genre}
                          type="button"
                          onClick={() => toggleGenre(genre)}
                          className={cn(
                            "rounded-md border bg-white px-3 py-2 text-sm transition-colors hover:border-primary/60",
                            selected && "border-primary bg-primary/10 text-primary"
                          )}
                        >
                          {genre}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <Button type="submit" disabled={isGenerating}>
                  {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  {isGenerating ? "Generating Draft" : "Generate Draft Manga"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <aside className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Progress</CardTitle>
                <CardDescription>{latestEvent?.message ?? "No director job started"}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <div className="rounded-md border bg-[linear-gradient(135deg,#fffdf7,#eef7f5)] p-4">
                  <div className="flex items-center gap-3">
                    <span className={cn("h-3 w-3 rounded-full bg-primary", isGenerating && "animate-ping")} />
                    <div>
                      <p className="text-sm font-semibold">{activeEvent ? activeEvent.replaceAll("_", " ") : "Waiting for direction"}</p>
                      <p className="text-xs text-muted-foreground">{completed ? "Draft pipeline complete" : failed ? "Pipeline needs recovery" : "Current stage animation"}</p>
                    </div>
                  </div>
                </div>
                <div className="flex flex-col gap-2">
                  {progressSteps.map((step, index) => {
                    const isActive = activeEvent === step.value;
                    const isDone = index <= completedStepIndex && !failed;
                    return (
                      <div
                        key={step.value}
                        className={cn(
                          "flex items-center justify-between gap-3 rounded-md border bg-white px-3 py-2 text-sm",
                          isActive && "border-primary bg-primary/5",
                          failed && isActive && "border-destructive/40 bg-destructive/10 text-destructive"
                        )}
                      >
                        <span className="flex min-w-0 items-center gap-2">
                          {isDone ? (
                            <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" />
                          ) : failed && isActive ? (
                            <CircleAlert className="h-4 w-4 shrink-0 text-destructive" />
                          ) : isActive ? (
                            <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
                          ) : (
                            <Circle className="h-4 w-4 shrink-0 text-muted-foreground" />
                          )}
                          <span className="truncate font-medium">{step.label}</span>
                        </span>
                        {isActive ? <Badge>Now</Badge> : null}
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Output</CardTitle>
                <CardDescription>{project ? `${project.pages.length} pages available` : "Project pages"}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {project?.pages.length ? (
                  <div className="grid gap-3">
                    {project.pages.map((page) => (
                      <Link key={page.id} href={`/projects/${projectId}/pages/${page.id}/studio`} className="rounded-md border bg-white p-3 transition-colors hover:border-primary/60">
                        <div className="relative mx-auto w-20 overflow-hidden rounded-sm border bg-[#fffdf7]" style={{ aspectRatio: `${page.width} / ${page.height}` }}>
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
                        <div className="mt-3 flex items-center justify-between gap-3 text-sm">
                          <span className="flex items-center gap-2 font-medium">
                            <PanelTop className="h-4 w-4" />
                            Page {page.page_number}
                          </span>
                          <span className="text-xs text-muted-foreground">{page.panels.length} panels</span>
                        </div>
                      </Link>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Generated pages will appear here.</p>
                )}

                <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
                  <Button asChild variant="outline">
                    <Link href={`/projects/${projectId}/story`}>
                      <BookOpen className="h-4 w-4" />
                      Story Room
                    </Link>
                  </Button>
                  <Button asChild variant="outline">
                    <Link href={`/projects/${projectId}/publishing`}>
                      <Clapperboard className="h-4 w-4" />
                      Publishing
                    </Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          </aside>
        </section>
      </div>
    </main>
  );
}

function JobStatusBadge({ status }: { status: GenerationJob["status"] }) {
  return (
    <Badge
      className={cn(
        status === "succeeded" && "border-primary/30 bg-primary/10 text-primary",
        status === "failed" && "border-destructive/30 bg-destructive/10 text-destructive",
        (status === "queued" || status === "running") && "border-accent bg-accent text-accent-foreground"
      )}
    >
      {status}
    </Badge>
  );
}

function clampNumber(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) {
    return min;
  }
  return Math.min(max, Math.max(min, Math.floor(value)));
}
