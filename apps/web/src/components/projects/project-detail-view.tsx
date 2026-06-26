"use client";

import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, BookOpen, Brush, Clapperboard, FileCheck2, FileDown, Image, Layers, PanelTop, Plus, RefreshCcw, RotateCcw, ShieldCheck, Type, UserRound, Wand2 } from "lucide-react";
import type { GenerationJob, GenerationJobRetryResult, PageWithPanels, Panel, ProjectDetail } from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { VersionHistorySidebar } from "@/components/version-history/version-history-sidebar";

type PanelDraft = {
  x: number;
  y: number;
  width: number;
  height: number;
  prompt: string;
};

const defaultPanelDraft: PanelDraft = {
  x: 120,
  y: 140,
  width: 620,
  height: 460,
  prompt: "A dramatic manga panel with clean ink lines"
};

export function ProjectDetailView({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [selectedPageId, setSelectedPageId] = useState<string | null>(null);
  const [panelDraft, setPanelDraft] = useState<PanelDraft>(defaultPanelDraft);
  const [jobsByPanel, setJobsByPanel] = useState<Record<string, GenerationJob>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadProject() {
    setIsLoading(true);
    setError(null);
    try {
      const nextProject = await apiFetch<ProjectDetail>(`/projects/${projectId}`);
      setProject(nextProject);
      setSelectedPageId((current) => current ?? nextProject.pages[0]?.id ?? null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load project");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadProject();
  }, [projectId]);

  const selectedPage = useMemo(() => {
    return project?.pages.find((page) => page.id === selectedPageId) ?? project?.pages[0] ?? null;
  }, [project, selectedPageId]);

  useEffect(() => {
    const activeJobs = Object.values(jobsByPanel).filter((job) => job.status === "queued" || job.status === "running");
    if (activeJobs.length === 0) {
      return;
    }

    const timer = window.setInterval(async () => {
      const updates = await Promise.all(
        activeJobs.map((job) => apiFetch<GenerationJob>(`/jobs/${job.id}`).catch(() => job))
      );
      setJobsByPanel((current) => {
        const next = { ...current };
        for (const job of updates) {
          if (job.panel_id) {
            next[job.panel_id] = job;
          }
        }
        return next;
      });
    }, 1600);

    return () => window.clearInterval(timer);
  }, [jobsByPanel]);

  async function createPage() {
    setIsBusy(true);
    setError(null);
    try {
      const page = await apiFetch<PageWithPanels>(`/projects/${projectId}/pages`, {
        method: "POST",
        body: JSON.stringify({ width: 1600, height: 2400 })
      });
      await loadProject();
      setSelectedPageId(page.id);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Unable to create page");
    } finally {
      setIsBusy(false);
    }
  }

  async function createPanel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPage) {
      return;
    }

    setIsBusy(true);
    setError(null);
    try {
      await apiFetch<Panel>(`/pages/${selectedPage.id}/panels`, {
        method: "POST",
        body: JSON.stringify({
          ...panelDraft,
          prompt: panelDraft.prompt.trim() || null
        })
      });
      setPanelDraft(defaultPanelDraft);
      await loadProject();
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Unable to create panel");
    } finally {
      setIsBusy(false);
    }
  }

  async function renderPanel(panelId: string) {
    setError(null);
    try {
      const job = await apiFetch<GenerationJob>("/jobs/mock-render-panel", {
        method: "POST",
        body: JSON.stringify({ panel_id: panelId })
      });
      if (job.panel_id) {
        setJobsByPanel((current) => ({ ...current, [job.panel_id as string]: job }));
      }
    } catch (renderError) {
      setError(renderError instanceof Error ? renderError.message : "Unable to start render job");
    }
  }

  async function retryJob(jobId: string) {
    setError(null);
    try {
      const result = await apiFetch<GenerationJobRetryResult>(`/jobs/${jobId}/retry`, {
        method: "POST",
        body: JSON.stringify({ provider_name: "mock", use_mock_fallback: true })
      });
      if (result.job.panel_id) {
        setJobsByPanel((current) => ({ ...current, [result.job.panel_id as string]: result.job }));
      }
    } catch (retryError) {
      setError(retryError instanceof Error ? retryError.message : "Unable to retry job");
    }
  }

  if (isLoading && project === null) {
    return (
      <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-md border bg-white px-4 py-8 text-sm text-muted-foreground">
          Loading project
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
              <Link href="/">
                <ArrowLeft className="h-4 w-4" />
                Projects
              </Link>
            </Button>
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-semibold tracking-normal">{project.name}</h1>
                <Badge>{project.status}</Badge>
              </div>
              <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
                {project.description || "Untitled manga project"}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button asChild variant="outline">
              <Link href={`/projects/${projectId}/director`}>
                <Clapperboard className="h-4 w-4" />
                Director Mode
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href={`/projects/${projectId}/story`}>
                <BookOpen className="h-4 w-4" />
                Story Room
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href={`/projects/${projectId}/characters`}>
                <UserRound className="h-4 w-4" />
                Character Lab
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href={`/projects/${projectId}/style`}>
                <Brush className="h-4 w-4" />
                Style Lab
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href={`/projects/${projectId}/publishing`}>
                <FileDown className="h-4 w-4" />
                Publishing
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href={`/projects/${projectId}/provenance`}>
                <FileCheck2 className="h-4 w-4" />
                Provenance
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href={`/projects/${projectId}/qa`}>
                <ShieldCheck className="h-4 w-4" />
                QA Room
              </Link>
            </Button>
            {selectedPage ? (
              <>
                <Button asChild variant="outline">
                  <Link href={`/projects/${projectId}/pages/${selectedPage.id}/studio`}>
                    <PanelTop className="h-4 w-4" />
                    Page Studio
                  </Link>
                </Button>
                <Button asChild variant="outline">
                  <Link href={`/projects/${projectId}/pages/${selectedPage.id}/lettering`}>
                    <Type className="h-4 w-4" />
                    Lettering
                  </Link>
                </Button>
              </>
            ) : null}
            <Button variant="outline" onClick={() => void loadProject()}>
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </Button>
            <Button onClick={() => void createPage()} disabled={isBusy}>
              <Plus className="h-4 w-4" />
              Page
            </Button>
          </div>
        </header>

        {error ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)_360px]">
          <aside className="flex flex-col gap-3">
            <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-normal text-muted-foreground">
              <Layers className="h-4 w-4" />
              Pages
            </h2>
            {project.pages.length === 0 ? (
              <div className="rounded-md border bg-white px-4 py-6 text-sm text-muted-foreground">No pages yet</div>
            ) : (
              <div className="flex flex-col gap-2">
                {project.pages.map((page) => (
                  <button
                    type="button"
                    key={page.id}
                    onClick={() => setSelectedPageId(page.id)}
                    className={cn(
                      "rounded-md border bg-white px-3 py-3 text-left text-sm transition-colors hover:border-primary/60",
                      selectedPage?.id === page.id && "border-primary bg-primary/5"
                    )}
                  >
                    <span className="block font-medium">Page {page.page_number}</span>
                    <span className="text-xs text-muted-foreground">
                      {page.panels.length} panels - {page.width}x{page.height}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </aside>

          <section className="flex min-w-0 flex-col gap-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 text-lg font-semibold">
                <Image className="h-5 w-5" />
                Page Preview
              </h2>
              {selectedPage ? <Badge>Page {selectedPage.page_number}</Badge> : null}
            </div>
            {selectedPage ? (
              <PagePreview page={selectedPage} jobsByPanel={jobsByPanel} onRenderPanel={renderPanel} />
            ) : (
              <div className="rounded-md border bg-white px-4 py-10 text-sm text-muted-foreground">
                Create a page to start panel layout
              </div>
            )}
          </section>

          <aside className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Panel</CardTitle>
                <CardDescription>{selectedPage ? `Page ${selectedPage.page_number}` : "No page selected"}</CardDescription>
              </CardHeader>
              <CardContent>
                <form className="flex flex-col gap-3" onSubmit={createPanel}>
                  <div className="grid grid-cols-2 gap-3">
                    <NumberField label="X" value={panelDraft.x} onChange={(x) => setPanelDraft((current) => ({ ...current, x }))} />
                    <NumberField label="Y" value={panelDraft.y} onChange={(y) => setPanelDraft((current) => ({ ...current, y }))} />
                    <NumberField
                      label="Width"
                      value={panelDraft.width}
                      onChange={(width) => setPanelDraft((current) => ({ ...current, width }))}
                    />
                    <NumberField
                      label="Height"
                      value={panelDraft.height}
                      onChange={(height) => setPanelDraft((current) => ({ ...current, height }))}
                    />
                  </div>
                  <label className="flex flex-col gap-2 text-sm font-medium">
                    Prompt
                    <Textarea
                      value={panelDraft.prompt}
                      onChange={(event) => setPanelDraft((current) => ({ ...current, prompt: event.target.value }))}
                    />
                  </label>
                  <Button type="submit" disabled={!selectedPage || isBusy}>
                    <Plus className="h-4 w-4" />
                    Add Panel
                  </Button>
                </form>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Render Job Status</CardTitle>
                <CardDescription>Mock panel renders</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {Object.values(jobsByPanel).length === 0 ? (
                  <p className="text-sm text-muted-foreground">No active jobs</p>
                ) : (
                  Object.values(jobsByPanel).map((job) => (
                    <div key={job.id} className="rounded-md border bg-white p-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="truncate text-sm font-medium">{job.id.slice(0, 8)}</span>
                        <JobStatusBadge status={job.status} />
                      </div>
                      {job.render?.public_url ? (
                        <img
                          src={job.render.public_url}
                          alt="Rendered panel"
                          className="mt-3 aspect-[4/3] w-full rounded-md border object-cover"
                        />
                      ) : null}
                      {job.status === "failed" ? (
                        <div className="mt-3 flex flex-col gap-2">
                          <p className="text-xs text-destructive">{job.error_message ?? "Render failed"}</p>
                          <Button size="sm" variant="outline" onClick={() => void retryJob(job.id)}>
                            <RotateCcw className="h-4 w-4" />
                            Retry with mock
                          </Button>
                        </div>
                      ) : null}
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            <VersionHistorySidebar projectId={projectId} onRestored={() => void loadProject()} />
          </aside>
        </div>
      </div>
    </main>
  );
}

function NumberField({
  label,
  value,
  onChange
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="flex flex-col gap-2 text-sm font-medium">
      {label}
      <Input
        type="number"
        min={label === "X" || label === "Y" ? 0 : 1}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}

function PagePreview({
  page,
  jobsByPanel,
  onRenderPanel
}: {
  page: PageWithPanels;
  jobsByPanel: Record<string, GenerationJob>;
  onRenderPanel: (panelId: string) => void;
}) {
  return (
    <div className="rounded-md border bg-white p-4">
      <div
        className="relative mx-auto w-full max-w-[520px] overflow-hidden rounded-sm border-2 border-foreground bg-[#fffdf7] shadow-sm"
        style={{ aspectRatio: `${page.width} / ${page.height}` }}
      >
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(0,0,0,0.04)_1px,transparent_1px),linear-gradient(180deg,rgba(0,0,0,0.04)_1px,transparent_1px)] bg-[size:48px_48px]" />
        {page.panels.map((panel) => {
          const job = jobsByPanel[panel.id];
          return (
            <button
              type="button"
              key={panel.id}
              onClick={() => void onRenderPanel(panel.id)}
              className="absolute flex min-h-8 min-w-10 items-center justify-center border-2 border-foreground bg-white/80 text-[10px] font-semibold transition-colors hover:bg-accent"
              title="Render panel"
              style={{
                left: `${(panel.x / page.width) * 100}%`,
                top: `${(panel.y / page.height) * 100}%`,
                width: `${(panel.width / page.width) * 100}%`,
                height: `${(panel.height / page.height) * 100}%`
              }}
            >
              {job ? job.status : panel.id.slice(0, 4)}
            </button>
          );
        })}
      </div>

      {page.panels.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground">No panels on this page</p>
      ) : (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {page.panels.map((panel) => (
            <PanelRow key={panel.id} panel={panel} job={jobsByPanel[panel.id]} onRenderPanel={onRenderPanel} />
          ))}
        </div>
      )}
    </div>
  );
}

function PanelRow({
  panel,
  job,
  onRenderPanel
}: {
  panel: Panel;
  job: GenerationJob | undefined;
  onRenderPanel: (panelId: string) => void;
}) {
  return (
    <div className="rounded-md border bg-background p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">Panel {panel.id.slice(0, 8)}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {panel.x}, {panel.y} - {panel.width}x{panel.height}
          </p>
        </div>
        {job ? <JobStatusBadge status={job.status} /> : null}
      </div>
      <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">{panel.prompt || "No prompt"}</p>
      <Button className="mt-3 w-full" variant="outline" size="sm" onClick={() => void onRenderPanel(panel.id)}>
        <Wand2 className="h-4 w-4" />
        Mock Render
      </Button>
    </div>
  );
}

function JobStatusBadge({ status }: { status: GenerationJob["status"] }) {
  return (
    <Badge
      className={cn(
        "shrink-0",
        status === "succeeded" && "border-primary/30 bg-primary/10 text-primary",
        status === "failed" && "border-destructive/30 bg-destructive/10 text-destructive",
        (status === "queued" || status === "running") && "border-accent bg-accent text-accent-foreground"
      )}
    >
      {status}
    </Badge>
  );
}
