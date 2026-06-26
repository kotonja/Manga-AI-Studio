"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Database, FileCheck2, RefreshCcw, Settings, ShieldCheck } from "lucide-react";
import type { ProjectDataControls, ProjectDetail, ProjectProvenance, ProjectWorkspaceSummary } from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { StatusChip } from "@/components/layout/status-chip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

export function ProjectSettingsView({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [summary, setSummary] = useState<ProjectWorkspaceSummary | null>(null);
  const [provenance, setProvenance] = useState<ProjectProvenance | null>(null);
  const [dataControls, setDataControls] = useState<ProjectDataControls | null>(null);
  const [isSavingControls, setIsSavingControls] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadSettings() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextProject, nextSummary, nextProvenance, nextControls] = await Promise.all([
        apiFetch<ProjectDetail>(`/projects/${projectId}`),
        apiFetch<ProjectWorkspaceSummary>(`/projects/${projectId}/workspace-summary`).catch(() => null),
        apiFetch<ProjectProvenance>(`/projects/${projectId}/provenance`).catch(() => null),
        apiFetch<ProjectDataControls>(`/projects/${projectId}/data-controls`).catch(() => null)
      ]);
      setProject(nextProject);
      setSummary(nextSummary);
      setProvenance(nextProvenance);
      setDataControls(nextControls);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load project settings");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadSettings();
  }, [projectId]);

  async function saveDataControls() {
    if (!dataControls) {
      return;
    }
    setIsSavingControls(true);
    setError(null);
    try {
      const saved = await apiFetch<ProjectDataControls>(`/projects/${projectId}/data-controls`, {
        method: "PUT",
        body: JSON.stringify({
          allow_training: dataControls.allow_training,
          allow_product_improvement: dataControls.allow_product_improvement,
          data_collection_notes: dataControls.data_collection_notes
        })
      });
      setDataControls(saved);
      await loadSettings();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to save data controls");
    } finally {
      setIsSavingControls(false);
    }
  }

  if (isLoading && !project) {
    return (
      <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-md border bg-white px-4 py-8 text-sm text-muted-foreground">Loading Settings</div>
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
                <h1 className="text-3xl font-semibold tracking-normal">Settings</h1>
                <StatusChip status={summary?.status_chip ?? project?.status} />
              </div>
              <p className="mt-2 max-w-3xl text-sm text-muted-foreground">Project operations, readiness, rights metadata, and local development status.</p>
            </div>
          </div>
          <Button variant="outline" onClick={() => void loadSettings()}>
            <RefreshCcw className="h-4 w-4" />
            Refresh
          </Button>
        </header>

        {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div> : null}

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings className="h-4 w-4" />
                  Project Profile
                </CardTitle>
                <CardDescription>{project?.name ?? "Project"}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <SettingRow label="Status" value={project?.status ?? "draft"} />
                <SettingRow label="Active style" value={project?.active_style_bible_id ?? "Not selected"} />
                <SettingRow label="Pages" value={String(summary?.page_count ?? project?.pages.length ?? 0)} />
                <SettingRow label="Panels" value={String(summary?.panel_count ?? 0)} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4" />
                  Publishing Readiness
                </CardTitle>
                <CardDescription>Current project gates</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <SettingRow label="QA score" value={summary?.qa_score != null ? String(summary.qa_score) : "Not run"} />
                <SettingRow label="Blocking QA" value={summary?.qa_blocking ? "Yes" : "No"} />
                <SettingRow label="Export" value={summary?.export_status ?? "No export"} />
                <SettingRow label="AI disclosure" value={provenance?.summary.ai_disclosure_required ? "Required" : "Not required"} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileCheck2 className="h-4 w-4" />
                  Creator Rights
                </CardTitle>
                <CardDescription>Upload and export declarations</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <Badge>{provenance?.rights_declaration ? "Declaration saved" : "Declaration missing"}</Badge>
                <p className="text-sm text-muted-foreground">{provenance?.rights_declaration?.notes || "Add rights notes before registering uploaded references."}</p>
                <Button asChild variant="outline">
                  <Link href={`/projects/${projectId}/provenance`}>
                    <FileCheck2 className="h-4 w-4" />
                    Open Provenance
                  </Link>
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="h-4 w-4" />
                  Product Learning
                </CardTitle>
                <CardDescription>Private by default</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={Boolean(dataControls?.allow_product_improvement)}
                    onChange={(event) => setDataControls((current) => current ? { ...current, allow_product_improvement: event.target.checked } : current)}
                  />
                  <span>Allow opted-in ratings and corrections to improve Manga AI Studio</span>
                </label>
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={Boolean(dataControls?.allow_training)}
                    onChange={(event) => setDataControls((current) => current ? { ...current, allow_training: event.target.checked } : current)}
                  />
                  <span>Allow training use for this project</span>
                </label>
                <Textarea
                  value={dataControls?.data_collection_notes ?? ""}
                  onChange={(event) => setDataControls((current) => current ? { ...current, data_collection_notes: event.target.value } : current)}
                  placeholder="Notes for this project's data permissions"
                />
                <p className="text-xs text-muted-foreground">{dataControls?.explanation ?? "Project data controls are loading."}</p>
                <Button variant="outline" onClick={() => void saveDataControls()} disabled={!dataControls || isSavingControls}>
                  {isSavingControls ? "Saving" : "Save Data Controls"}
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="h-4 w-4" />
                  Local Stack
                </CardTitle>
                <CardDescription>Development services</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-2 text-sm">
                <Badge>PostgreSQL</Badge>
                <Badge>Redis</Badge>
                <Badge>MinIO</Badge>
                <Badge>FastAPI</Badge>
                <Badge>Next.js</Badge>
              </CardContent>
            </Card>
          </div>

          <aside className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Room Shortcuts</CardTitle>
                <CardDescription>Common recovery paths</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                <Button asChild variant="outline"><Link href={`/projects/${projectId}/director`}>Director Mode</Link></Button>
                <Button asChild variant="outline"><Link href={`/projects/${projectId}/qa`}>Run QA</Link></Button>
                <Button asChild variant="outline"><Link href={`/projects/${projectId}/publishing`}>Export Room</Link></Button>
              </CardContent>
            </Card>
          </aside>
        </section>
      </div>
    </main>
  );
}

function SettingRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-md border bg-muted/30 px-3 py-2">
      <span className="text-muted-foreground">{label}</span>
      <span className="max-w-[220px] truncate font-medium">{value}</span>
    </div>
  );
}
