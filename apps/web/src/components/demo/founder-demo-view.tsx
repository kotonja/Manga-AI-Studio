"use client";

import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Circle,
  Clapperboard,
  Download,
  FileArchive,
  FileText,
  Loader2,
  PanelTop,
  Play,
  ShieldCheck,
  Sparkles,
  Users,
  Wand2
} from "lucide-react";
import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import type {
  CharacterCard,
  CompositePage,
  DirectorProgressEvent,
  FounderDemoRunRequest,
  FounderDemoRunResponse,
  GenerationJob,
  JobEvent,
  ProjectDetail,
  ProviderName,
  QAReport,
  ReadingDirection,
  StoryBible
} from "@manga-ai/shared";

import { apiFetch, getApiBaseUrl } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

type StyleOption = {
  id: string;
  name: string;
  intent: string;
  tags: string[];
};

type FounderState = {
  project_id?: string;
  page_ids?: string[];
  panel_ids?: string[];
  render_job_ids?: string[];
  composite_asset_ids?: string[];
  qa_report_ids?: string[];
  exports?: Record<string, string>;
  style_option?: string;
  premise?: string;
};

const premise = "A lonely swordsman protects a ghost child in a ruined city.";

const styleOptions: StyleOption[] = [
  {
    id: "ruined_ink_elegy",
    name: "Ruined Ink Elegy",
    intent: "Rain, ruins, silhouettes, and lantern-white hope.",
    tags: ["high contrast", "rain tone", "quiet emotion"]
  },
  {
    id: "moonlit_screentone_noir",
    name: "Moonlit Screentone Noir",
    intent: "Mist, moonlit negative space, and soft ghost-story tension.",
    tags: ["mist layers", "noir mood", "slow reveal"]
  },
  {
    id: "kinetic_ash_action",
    name: "Kinetic Ash Action",
    intent: "Bold motion cuts, ash bursts, and sharp impact timing.",
    tags: ["speed lines", "action beats", "cracked frames"]
  }
];

const eventSteps: Array<{ value: DirectorProgressEvent; label: string }> = [
  { value: "queued", label: "Queued" },
  { value: "creating_project", label: "Project" },
  { value: "writing_story_bible", label: "Story" },
  { value: "designing_characters", label: "Characters" },
  { value: "creating_style_dna", label: "Style DNA" },
  { value: "planning_pages", label: "Plans" },
  { value: "drawing_layouts", label: "Layouts" },
  { value: "lettering_pages", label: "Lettering" },
  { value: "rendering_panels", label: "Panels" },
  { value: "composing_final_pages", label: "Pages" },
  { value: "checking_quality", label: "QA" },
  { value: "exporting_files", label: "Exports" },
  { value: "complete", label: "Complete" },
  { value: "failed", label: "Failed" }
];

const pageCounts = [4, 6, 8];
const directions: ReadingDirection[] = ["rtl", "ltr", "vertical-rl"];
const providers: ProviderName[] = ["mock", "openai", "comfyui"];

export function FounderDemoView() {
  const [draft, setDraft] = useState<FounderDemoRunRequest>({
    premise,
    style_option: "ruined_ink_elegy",
    page_count: 4,
    reading_direction: "rtl",
    render_provider: "mock",
    quality_mode: "fast",
    allow_mock_assets: true
  });
  const [projectId, setProjectId] = useState<string | null>(null);
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [story, setStory] = useState<StoryBible | null>(null);
  const [characters, setCharacters] = useState<CharacterCard[]>([]);
  const [composites, setComposites] = useState<Record<string, CompositePage>>({});
  const [qaReports, setQaReports] = useState<Record<string, QAReport>>({});
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const latestEvent = events.at(-1);
  const failed = job?.status === "failed" || latestEvent?.event_type === "failed";
  const complete = job?.status === "succeeded" || latestEvent?.event_type === "complete";
  const founderState = readFounderState(job);
  const exportIds = founderState?.exports ?? {};

  const activeIndex = useMemo(() => {
    if (failed) {
      return eventSteps.findIndex((step) => step.value === "failed");
    }
    if (complete) {
      return eventSteps.findIndex((step) => step.value === "complete");
    }
    const active = latestEvent?.event_type;
    return Math.max(0, eventSteps.findIndex((step) => step.value === active));
  }, [complete, failed, latestEvent?.event_type]);

  const qaScore = useMemo(() => {
    const reports = Object.values(qaReports);
    if (reports.length === 0) {
      return null;
    }
    return Math.round(reports.reduce((sum, report) => sum + report.overall_score, 0) / reports.length);
  }, [qaReports]);

  useEffect(() => {
    if (!job) {
      return;
    }

    let cancelled = false;
    const poll = async () => {
      try {
        const [nextJob, nextEvents] = await Promise.all([
          apiFetch<GenerationJob>(`/jobs/${job.id}`),
          apiFetch<JobEvent[]>(`/jobs/${job.id}/events`)
        ]);
        if (cancelled) {
          return;
        }
        setJob(nextJob);
        setEvents(nextEvents);
        const nextProjectId = nextJob.project_id ?? projectId;
        if (nextProjectId) {
          setProjectId(nextProjectId);
          await loadArtifacts(nextProjectId);
        }
        if (nextJob.status === "succeeded") {
          setIsGenerating(false);
        }
        if (nextJob.status === "failed") {
          setIsGenerating(false);
          setError(nextJob.error_message ?? "Founder Demo generation failed");
        }
      } catch (pollError) {
        if (!cancelled) {
          setError(pollError instanceof Error ? pollError.message : "Unable to poll Founder Demo job");
          setIsGenerating(false);
        }
      }
    };

    void poll();
    if (job.status === "succeeded" || job.status === "failed") {
      return () => {
        cancelled = true;
      };
    }

    const timer = window.setInterval(() => void poll(), 1400);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [job?.id, job?.status]);

  async function loadArtifacts(nextProjectId: string) {
    const nextProject = await apiFetch<ProjectDetail>(`/projects/${nextProjectId}`).catch(() => null);
    if (nextProject) {
      setProject(nextProject);
      await Promise.all([
        loadComposites(nextProject),
        loadQa(nextProject)
      ]);
    }

    const [nextStory, nextCharacters] = await Promise.all([
      apiFetch<StoryBible>(`/projects/${nextProjectId}/story/bible`).catch(() => null),
      apiFetch<CharacterCard[]>(`/projects/${nextProjectId}/characters`).catch(() => [])
    ]);
    if (nextStory) {
      setStory(nextStory);
    }
    setCharacters(nextCharacters);
  }

  async function loadComposites(nextProject: ProjectDetail) {
    const entries = await Promise.all(
      nextProject.pages.map(async (page) => {
        const composite = await apiFetch<CompositePage>(`/pages/${page.id}/composite`).catch(() => null);
        return composite ? [page.id, composite] as const : null;
      })
    );
    const loaded = Object.fromEntries(entries.filter((entry): entry is readonly [string, CompositePage] => Boolean(entry)));
    setComposites((current) => ({ ...current, ...loaded }));
  }

  async function loadQa(nextProject: ProjectDetail) {
    const entries = await Promise.all(
      nextProject.pages.map(async (page) => {
        const report = await apiFetch<QAReport>(`/pages/${page.id}/qa/latest`).catch(() => null);
        return report ? [page.id, report] as const : null;
      })
    );
    const loaded = Object.fromEntries(entries.filter((entry): entry is readonly [string, QAReport] => Boolean(entry)));
    setQaReports((current) => ({ ...current, ...loaded }));
  }

  async function runDemo(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.premise.trim()) {
      setError("Premise is required");
      return;
    }

    setError(null);
    setIsGenerating(true);
    setJob(null);
    setEvents([]);
    setProject(null);
    setStory(null);
    setCharacters([]);
    setComposites({});
    setQaReports({});
    try {
      const response = await apiFetch<FounderDemoRunResponse>("/demo/founder-run", {
        method: "POST",
        body: JSON.stringify({
          ...draft,
          premise: draft.premise.trim()
        })
      });
      setProjectId(response.project_id);
      const [nextJob, nextEvents] = await Promise.all([
        apiFetch<GenerationJob>(`/jobs/${response.job_id}`),
        apiFetch<JobEvent[]>(`/jobs/${response.job_id}/events`)
      ]);
      setJob(nextJob);
      setEvents(nextEvents);
      await loadArtifacts(response.project_id);
      if (nextJob.status === "succeeded") {
        setIsGenerating(false);
      }
      if (nextJob.status === "failed") {
        setIsGenerating(false);
        setError(nextJob.error_message ?? "Founder Demo generation failed");
      }
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : "Unable to start Founder Demo");
      setIsGenerating(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f7f4ed] text-foreground">
      <section className="relative overflow-hidden bg-[#111417] text-white">
        <div className="absolute inset-0 opacity-35">
          <div className="h-full w-full bg-[linear-gradient(115deg,rgba(255,255,255,0.08)_0_1px,transparent_1px_28px),radial-gradient(circle_at_80%_20%,rgba(230,205,146,0.26),transparent_30%),radial-gradient(circle_at_12%_80%,rgba(80,177,162,0.23),transparent_32%)]" />
        </div>
        <div className="relative mx-auto grid min-h-[680px] max-w-7xl gap-8 px-4 py-8 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:px-8">
          <div className="flex flex-col justify-between gap-8">
            <div className="flex items-center justify-between gap-3">
              <Button asChild variant="ghost" className="text-white hover:bg-white/10 hover:text-white">
                <Link href="/">
                  <ArrowRight className="h-4 w-4 rotate-180" />
                  Dashboard
                </Link>
              </Button>
              <Badge className="border-white/20 bg-white/10 text-white">Founder Demo Mode</Badge>
            </div>

            <div className="max-w-3xl">
              <div className="mb-4 flex w-fit items-center gap-2 rounded-md border border-white/20 bg-white/10 px-3 py-2 text-xs font-medium text-white/90">
                <Sparkles className="h-4 w-4 text-[#f0c96b]" />
                Deterministic local demo, real studio pipeline
              </div>
              <h1 className="text-5xl font-semibold tracking-normal sm:text-6xl lg:text-7xl">
                Generate a draft manga in one run
              </h1>
              <p className="mt-5 max-w-2xl text-base leading-7 text-white/75">
                Story, characters, original style DNA, page layouts, polished mock panels, lettering, QA, and exports arrive as one inspectable project.
              </p>
            </div>

            <DemoPoster />
          </div>

          <form className="self-center rounded-md border border-white/20 bg-white/[0.07] p-4 shadow-2xl backdrop-blur md:p-5" onSubmit={runDemo}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold tracking-normal">Founder Demo</h2>
                <p className="mt-1 text-sm text-white/60">Mock assets stay local unless you choose a configured provider.</p>
              </div>
              <Wand2 className="mt-1 h-5 w-5 text-[#f0c96b]" />
            </div>

            <label className="mt-5 flex flex-col gap-2 text-sm font-medium text-white">
              Premise
              <Textarea
                value={draft.premise}
                onChange={(event) => setDraft((current) => ({ ...current, premise: event.target.value }))}
                className="min-h-32 border-white/20 bg-black/40 text-white placeholder:text-white/40"
                style={{ backgroundColor: "rgba(0, 0, 0, 0.4)", color: "#fff" }}
              />
            </label>

            <div className="mt-5">
              <p className="text-sm font-medium">Original Style</p>
              <div className="mt-2 grid gap-2">
                {styleOptions.map((style) => (
                  <button
                    key={style.id}
                    type="button"
                    onClick={() => setDraft((current) => ({ ...current, style_option: style.id }))}
                    className={cn(
                      "rounded-md border p-3 text-left transition-colors",
                      draft.style_option === style.id
                        ? "border-[#f0c96b] bg-[#f0c96b]/10"
                        : "border-white/20 bg-black/20 hover:border-white/40"
                    )}
                  >
                    <span className="block text-sm font-semibold">{style.name}</span>
                    <span className="mt-1 block text-xs leading-5 text-white/70">{style.intent}</span>
                    <span className="mt-2 flex flex-wrap gap-1">
                      {style.tags.map((tag) => (
                        <span key={tag} className="rounded-md border border-white/20 px-2 py-1 text-[11px] text-white/70">
                          {tag}
                        </span>
                      ))}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <Selector label="Pages" values={pageCounts} value={draft.page_count} onChange={(value) => setDraft((current) => ({ ...current, page_count: Number(value) }))} />
              <Selector label="Direction" values={directions} value={draft.reading_direction} onChange={(value) => setDraft((current) => ({ ...current, reading_direction: value as ReadingDirection }))} />
              <Selector label="Provider" values={providers} value={draft.render_provider} onChange={(value) => setDraft((current) => ({ ...current, render_provider: value as ProviderName }))} />
              <Selector label="Quality" values={["fast", "balanced", "high"]} value={draft.quality_mode} onChange={(value) => setDraft((current) => ({ ...current, quality_mode: value as FounderDemoRunRequest["quality_mode"] }))} />
            </div>

            <Button type="submit" className="mt-5 w-full" disabled={isGenerating}>
              {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {isGenerating ? "Generating Manga Demo" : "Generate Manga Demo"}
            </Button>
          </form>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[390px_1fr] lg:px-8">
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clapperboard className="h-5 w-5" />
                Live Timeline
              </CardTitle>
              <CardDescription>{latestEvent?.message ?? "Ready to generate"}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-2">
                {eventSteps.filter((step) => step.value !== "failed" || failed).map((step, index) => (
                  <TimelineStep
                    key={step.value}
                    label={step.label}
                    complete={index < activeIndex || (complete && step.value === "complete")}
                    active={index === activeIndex && !complete && !failed}
                    failed={failed && step.value === "failed"}
                  />
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5" />
                QA Reveal
              </CardTitle>
              <CardDescription>{qaScore === null ? "Waiting for composed pages" : `${qaScore}/100 average page score`}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-end justify-between gap-4">
                <div className="text-5xl font-semibold tracking-normal">{qaScore ?? "--"}</div>
                <Badge className={cn(qaScore !== null && qaScore >= 80 ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground")}>
                  {qaScore === null ? "Pending" : qaScore >= 80 ? "QA Passed" : "Needs Review"}
                </Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Exports</CardTitle>
              <CardDescription>{Object.keys(exportIds).length ? "Files ready" : "Exports appear after QA"}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              <ExportButton label="ZIP Package" icon="zip" exportId={exportIds.zip} />
              <ExportButton label="PDF Draft" icon="pdf" exportId={exportIds.pdf} />
              <Button asChild={Boolean(projectId)} variant="outline" disabled={!projectId}>
                {projectId ? (
                  <Link href={`/projects/${projectId}`}>
                    <PanelTop className="h-4 w-4" />
                    Open in Studio
                  </Link>
                ) : (
                  <span>
                    <PanelTop className="h-4 w-4" />
                    Open in Studio
                  </span>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="flex flex-col gap-6">
          {error ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BookOpen className="h-5 w-5" />
                Generated Story
              </CardTitle>
              <CardDescription>{story?.logline ?? "Story bible will appear first"}</CardDescription>
            </CardHeader>
            <CardContent>
              {story ? (
                <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
                  <p className="text-sm leading-6 text-muted-foreground">{story.synopsis}</p>
                  <div className="rounded-md border bg-muted/40 p-3">
                    <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">Themes</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {story.themes.map((theme) => (
                        <Badge key={theme} className="bg-secondary text-secondary-foreground">{theme}</Badge>
                      ))}
                    </div>
                    <p className="mt-4 text-xs font-medium uppercase tracking-normal text-muted-foreground">Tone</p>
                    <p className="mt-1 text-sm">{story.tone}</p>
                  </div>
                </div>
              ) : (
                <EmptyPreview title="No story yet" body="The story bible appears when the writing stage finishes." />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5" />
                Character Cards
              </CardTitle>
              <CardDescription>{characters.length ? `${characters.length} cards created` : "Characters appear during the design stage"}</CardDescription>
            </CardHeader>
            <CardContent>
              {characters.length ? (
                <div className="grid gap-3 md:grid-cols-2">
                  {characters.map((character) => (
                    <div key={character.id} className="rounded-md border bg-white p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="font-semibold">{character.name}</h3>
                          <p className="mt-1 text-xs uppercase tracking-normal text-muted-foreground">{character.role}</p>
                        </div>
                        <Badge className="bg-secondary text-secondary-foreground">{character.age_range || "profile"}</Badge>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-muted-foreground">{character.canonical_visual_summary || character.personality}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {(character.silhouette_keywords ?? []).slice(0, 4).map((keyword) => (
                          <span key={keyword} className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">{keyword}</span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyPreview title="No characters yet" body="Ren and Mio will appear here with continuity anchors." />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Page Thumbnails</CardTitle>
              <CardDescription>{project?.pages.length ? `${Object.keys(composites).length}/${project.pages.length} composed` : "Pages appear after layout generation"}</CardDescription>
            </CardHeader>
            <CardContent>
              {project?.pages.length ? (
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  {project.pages.map((page) => (
                    <PageThumb key={page.id} projectId={project.id} page={page} composite={composites[page.id]} qa={qaReports[page.id]} />
                  ))}
                </div>
              ) : (
                <EmptyPreview title="No pages yet" body="Composed page previews will fill this strip as they are exported." />
              )}
            </CardContent>
          </Card>
        </div>
      </section>
    </main>
  );
}

function Selector<T extends string | number>({
  label,
  values,
  value,
  onChange
}: {
  label: string;
  values: T[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-normal text-white/60">{label}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {values.map((item) => (
          <button
            key={String(item)}
            type="button"
            onClick={() => onChange(item)}
            className={cn(
              "rounded-md border px-3 py-2 text-sm transition-colors",
              value === item ? "border-[#f0c96b] bg-[#f0c96b]/10 text-white" : "border-white/20 bg-black/20 text-white/70 hover:border-white/40"
            )}
          >
            {String(item)}
          </button>
        ))}
      </div>
    </div>
  );
}

function TimelineStep({ label, complete, active, failed }: { label: string; complete: boolean; active: boolean; failed: boolean }) {
  return (
    <div className={cn("flex items-center gap-3 rounded-md border px-3 py-2", active ? "border-primary/40 bg-primary/10" : "bg-white")}>
      <span className={cn("flex h-8 w-8 items-center justify-center rounded-md border", complete ? "border-primary bg-primary text-primary-foreground" : failed ? "border-destructive bg-destructive text-destructive-foreground" : "bg-muted")}>
        {complete ? <CheckCircle2 className="h-4 w-4" /> : active ? <Loader2 className="h-4 w-4 animate-spin" /> : <Circle className="h-4 w-4" />}
      </span>
      <span className={cn("text-sm font-medium", active ? "text-primary" : "text-foreground")}>{label}</span>
    </div>
  );
}

function ExportButton({ label, icon, exportId }: { label: string; icon: "zip" | "pdf"; exportId?: string }) {
  const Icon = icon === "zip" ? FileArchive : FileText;
  return (
    <Button asChild={Boolean(exportId)} variant={exportId ? "default" : "outline"} disabled={!exportId}>
      {exportId ? (
        <a href={`${getApiBaseUrl()}/exports/${exportId}/download`}>
          <Icon className="h-4 w-4" />
          {label}
          <Download className="h-4 w-4" />
        </a>
      ) : (
        <span>
          <Icon className="h-4 w-4" />
          {label}
        </span>
      )}
    </Button>
  );
}

function PageThumb({
  projectId,
  page,
  composite,
  qa
}: {
  projectId: string;
  page: ProjectDetail["pages"][number];
  composite?: CompositePage;
  qa?: QAReport;
}) {
  return (
    <Link href={`/projects/${projectId}/pages/${page.id}/studio`} className="group rounded-md border bg-white p-2 transition-colors hover:border-primary/60">
      <div className="relative aspect-[2/3] overflow-hidden rounded-md bg-[#f8f8f1]">
        {composite ? (
          <img src={assetImageUrl(composite.id, composite.public_url)} alt={`Composed page ${page.page_number}`} className="h-full w-full object-cover" />
        ) : (
          <div className="h-full w-full p-3">
            {page.panels.map((panel) => (
              <div
                key={panel.id}
                className="absolute border-2 border-[#1b1d22] bg-[#ecebe4]"
                style={{
                  left: `${(panel.x / page.width) * 100}%`,
                  top: `${(panel.y / page.height) * 100}%`,
                  width: `${(panel.width / page.width) * 100}%`,
                  height: `${(panel.height / page.height) * 100}%`
                }}
              />
            ))}
          </div>
        )}
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-sm font-medium">Page {page.page_number}</span>
        <Badge className={qa?.blocking ? "border-destructive/30 bg-destructive/10 text-destructive" : "bg-secondary text-secondary-foreground"}>
          {qa ? Math.round(qa.overall_score) : "..."}
        </Badge>
      </div>
    </Link>
  );
}

function assetImageUrl(assetId: string, publicUrl?: string | null) {
  return publicUrl || `${getApiBaseUrl()}/assets/${assetId}/download`;
}

function EmptyPreview({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-md border bg-muted/40 px-4 py-6 text-center">
      <p className="font-medium">{title}</p>
      <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">{body}</p>
    </div>
  );
}

function DemoPoster() {
  return (
    <div className="grid max-w-2xl grid-cols-3 gap-3">
      {[0, 1, 2].map((item) => (
        <div key={item} className={cn("relative h-40 overflow-hidden rounded-md border border-white/20 bg-white/10", item === 1 ? "mt-8" : "")}>
          <div className="absolute inset-3 border-2 border-white/60" />
          <div className="absolute left-5 top-6 h-20 w-10 rounded-full bg-white/20" />
          <div className="absolute bottom-6 left-8 h-16 w-20 skew-x-[-16deg] bg-black/50" />
          <div className="absolute right-4 top-4 h-20 w-1 rotate-45 bg-white/40" />
          <div className="absolute bottom-5 right-5 rounded-md bg-white px-2 py-1 text-[11px] font-semibold text-[#111417]">
            P{item + 1}
          </div>
        </div>
      ))}
    </div>
  );
}

function readFounderState(job: GenerationJob | null): FounderState | null {
  const state = job?.output_payload?.founder_state;
  if (!state || typeof state !== "object" || Array.isArray(state)) {
    return null;
  }
  return state as FounderState;
}
