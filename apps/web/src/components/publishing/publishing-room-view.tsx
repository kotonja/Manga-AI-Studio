"use client";

import Link from "next/link";
import { AlertTriangle, ArrowLeft, CheckCircle2, Download, FileArchive, FileCheck2, FileText, Layers, Package, RefreshCcw } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type {
  ExportPreview,
  ExportPreset,
  ExportReadiness,
  ProjectDetail,
  ProjectExport,
  ProjectPublishingMetadata,
  ProjectPublishingMetadataDraft,
  ProjectWorkspaceSummary
} from "@manga-ai/shared";

import { apiFetch, getApiBaseUrl } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LearningFeedbackControls } from "@/components/learning/learning-feedback-controls";
import { Textarea } from "@/components/ui/textarea";

const presetIcons: Record<string, LucideIcon> = {
  web_preview_png: FileArchive,
  high_res_png_sequence: FileArchive,
  print_pdf: FileText,
  kindle_fixed_layout: Package,
  epub_fixed_layout: Package,
  webtoon_vertical_strip: FileArchive,
  layered_production_package: Layers,
  archive_package: FileArchive
};

export function PublishingRoomView({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [summary, setSummary] = useState<ProjectWorkspaceSummary | null>(null);
  const [presets, setPresets] = useState<ExportPreset[]>([]);
  const [presetId, setPresetId] = useState("archive_package");
  const [readiness, setReadiness] = useState<ExportReadiness | null>(null);
  const [preview, setPreview] = useState<ExportPreview | null>(null);
  const [metadata, setMetadata] = useState<ProjectPublishingMetadataDraft | null>(null);
  const [force, setForce] = useState(false);
  const [exportResult, setExportResult] = useState<ProjectExport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSavingMetadata, setIsSavingMetadata] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadProject() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextProject, nextSummary, nextPresets, nextMetadata] = await Promise.all([
        apiFetch<ProjectDetail>(`/projects/${projectId}`),
        apiFetch<ProjectWorkspaceSummary>(`/projects/${projectId}/workspace-summary`).catch(() => null),
        apiFetch<ExportPreset[]>("/export-presets"),
        apiFetch<ProjectPublishingMetadata>(`/projects/${projectId}/publishing-metadata`)
      ]);
      setProject(nextProject);
      setSummary(nextSummary);
      setPresets(nextPresets);
      setMetadata(metadataDraft(nextMetadata));
      await loadReadiness(presetId);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load project");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadProject();
  }, [projectId]);

  useEffect(() => {
    if (!project) {
      return;
    }
    void loadReadiness(presetId);
    setPreview(null);
  }, [presetId]);

  async function loadReadiness(nextPresetId = presetId) {
    try {
      const nextReadiness = await apiFetch<ExportReadiness>(`/projects/${projectId}/export-readiness?preset_id=${encodeURIComponent(nextPresetId)}`);
      setReadiness(nextReadiness);
    } catch {
      setReadiness(null);
    }
  }

  const selectedPreset = useMemo(() => presets.find((item) => item.id === presetId) ?? presets[0] ?? null, [presetId, presets]);
  const SelectedFormatIcon = selectedPreset ? presetIcons[selectedPreset.id] ?? FileArchive : FileArchive;
  const downloadUrl = exportResult?.status === "succeeded" ? `${getApiBaseUrl()}/exports/${exportResult.id}/download` : null;

  async function saveMetadata() {
    if (!metadata) {
      return null;
    }
    setIsSavingMetadata(true);
    setError(null);
    try {
      const saved = await apiFetch<ProjectPublishingMetadata>(`/projects/${projectId}/publishing-metadata`, {
        method: "PUT",
        body: JSON.stringify(metadata)
      });
      setMetadata(metadataDraft(saved));
      await loadReadiness(presetId);
      return saved;
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to save publishing metadata");
      return null;
    } finally {
      setIsSavingMetadata(false);
    }
  }

  async function runPreview() {
    setIsPreviewing(true);
    setError(null);
    try {
      if (metadata) {
        await saveMetadata();
      }
      const result = await apiFetch<ExportPreview>(`/projects/${projectId}/exports/preview`, {
        method: "POST",
        body: JSON.stringify({
          preset_id: presetId,
          force,
          metadata,
          options: previewOptions(selectedPreset)
        })
      });
      setPreview(result);
      setReadiness(result.readiness);
    } catch (previewError) {
      setError(previewError instanceof Error ? previewError.message : "Unable to preview export");
    } finally {
      setIsPreviewing(false);
    }
  }

  async function runExport() {
    setIsExporting(true);
    setError(null);
    try {
      if (metadata) {
        await saveMetadata();
      }
      const result = await apiFetch<ProjectExport>(`/projects/${projectId}/exports/create`, {
        method: "POST",
        body: JSON.stringify({
          preset_id: presetId,
          force,
          metadata,
          options: {
            ...previewOptions(selectedPreset),
            source: "publishing_room"
          }
        })
      });
      setExportResult(result);
      if (result.status === "failed") {
        setError(result.error_message ?? "Export failed");
      }
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : "Unable to run export");
    } finally {
      setIsExporting(false);
    }
  }

  if (isLoading && project === null) {
    return (
      <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl rounded-md border bg-white px-4 py-8 text-sm text-muted-foreground">
          Loading Publishing Room
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
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
                <h1 className="text-3xl font-semibold tracking-normal">Publishing Room</h1>
                {project ? <Badge>{project.pages.length} pages</Badge> : null}
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{project?.name ?? "Project export"}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={() => void loadProject()}>
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </Button>
            <Button asChild variant="outline">
              <Link href={`/projects/${projectId}/provenance`}>
                <FileCheck2 className="h-4 w-4" />
                Disclosure
              </Link>
            </Button>
            <Button onClick={() => void runExport()} disabled={isExporting || project === null}>
              <SelectedFormatIcon className="h-4 w-4" />
              {isExporting ? "Exporting" : "Create Export"}
            </Button>
          </div>
        </header>

        {error ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        ) : null}

        {summary?.qa_blocking ? (
          <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <div className="flex items-center gap-2 font-medium">
              <AlertTriangle className="h-4 w-4" />
              Blocking QA issues detected
            </div>
            <p className="mt-1">Use force export only for internal review packages.</p>
          </div>
        ) : null}

        <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <Card>
            <CardHeader>
              <CardTitle>Export Preset</CardTitle>
              <CardDescription>{selectedPreset?.name ?? "Loading presets"}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="grid gap-3 sm:grid-cols-2">
                {presets.map((item) => {
                  const Icon = presetIcons[item.id] ?? FileArchive;
                  const isSelected = item.id === presetId;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setPresetId(item.id)}
                      className={`flex items-center justify-between rounded-md border bg-white px-4 py-3 text-left transition-colors hover:border-primary/60 ${
                        isSelected ? "border-primary bg-primary/5" : ""
                      }`}
                    >
                      <span className="flex items-center gap-3">
                        <Icon className="h-5 w-5" />
                        <span>
                          <span className="block font-medium">{item.name}</span>
                          <span className="text-xs text-muted-foreground">{item.file_format} - {item.dpi} DPI - {item.color_mode}</span>
                        </span>
                      </span>
                      {isSelected ? <Badge>Selected</Badge> : null}
                    </button>
                  );
                })}
              </div>

              {selectedPreset ? (
                <div className="grid gap-2 rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground sm:grid-cols-2">
                  <p><span className="font-medium text-foreground">Target:</span> {selectedPreset.page_width}x{selectedPreset.page_height || "strip"}</p>
                  <p><span className="font-medium text-foreground">Bleed:</span> {selectedPreset.bleed}</p>
                  <p><span className="font-medium text-foreground">Safe:</span> {selectedPreset.safe_margin}</p>
                  <p><span className="font-medium text-foreground">Quality:</span> {selectedPreset.compression_quality}</p>
                  <p className="sm:col-span-2">{selectedPreset.description}</p>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Project Metadata</CardTitle>
              <CardDescription>Used in EPUB/PDF/package metadata and disclosure files</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              {metadata ? (
                <>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <MetaField label="Title" value={metadata.title} onChange={(title) => setMetadata({ ...metadata, title })} />
                    <MetaField label="Subtitle" value={metadata.subtitle} onChange={(subtitle) => setMetadata({ ...metadata, subtitle })} />
                    <MetaField label="Author" value={metadata.author_name} onChange={(author_name) => setMetadata({ ...metadata, author_name })} />
                    <MetaField label="Publisher" value={metadata.publisher} onChange={(publisher) => setMetadata({ ...metadata, publisher })} />
                    <MetaField label="Language" value={metadata.language} onChange={(language) => setMetadata({ ...metadata, language })} />
                    <MetaField label="Age Rating" value={metadata.age_rating} onChange={(age_rating) => setMetadata({ ...metadata, age_rating })} />
                    <MetaField label="Genres" value={metadata.genres.join(", ")} onChange={(value) => setMetadata({ ...metadata, genres: splitList(value) })} />
                    <MetaField label="Tags" value={metadata.tags.join(", ")} onChange={(value) => setMetadata({ ...metadata, tags: splitList(value) })} />
                  </div>
                  <label className="flex flex-col gap-2 text-sm font-medium">
                    Synopsis
                    <Textarea value={metadata.synopsis} onChange={(event) => setMetadata({ ...metadata, synopsis: event.target.value })} />
                  </label>
                  <label className="flex flex-col gap-2 text-sm font-medium">
                    Copyright Notice
                    <Textarea value={metadata.copyright_notice} onChange={(event) => setMetadata({ ...metadata, copyright_notice: event.target.value })} />
                  </label>
                  <label className="flex flex-col gap-2 text-sm font-medium">
                    AI Disclosure Text
                    <Textarea value={metadata.ai_disclosure_text} onChange={(event) => setMetadata({ ...metadata, ai_disclosure_text: event.target.value })} />
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" onClick={() => void saveMetadata()} disabled={isSavingMetadata}>
                      <FileCheck2 className="h-4 w-4" />
                      {isSavingMetadata ? "Saving" : "Save Metadata"}
                    </Button>
                    <Button variant="outline" onClick={() => void runPreview()} disabled={isPreviewing}>
                      <FileText className="h-4 w-4" />
                      {isPreviewing ? "Previewing" : "Preview Export"}
                    </Button>
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">Loading metadata</p>
              )}
            </CardContent>
          </Card>

          <aside className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Readiness Checklist</CardTitle>
                <CardDescription>Export gates for review and publishing</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {readiness?.checklist.length ? (
                  readiness.checklist.map((item) => <ChecklistItem key={item.key} ok={item.passed} label={item.label} message={item.message} />)
                ) : (
                  <>
                    <ChecklistItem ok={(summary?.page_count ?? project?.pages.length ?? 0) > 0} label="Pages exist" />
                    <ChecklistItem ok={!summary?.qa_blocking || force} label="No blocking QA issues" />
                  </>
                )}
                <label className="mt-2 flex items-center gap-3 rounded-md border bg-muted/30 px-3 py-2 text-sm font-medium">
                  <input type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} />
                  Force export
                </label>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Preview</CardTitle>
                <CardDescription>{preview ? `${preview.estimated_files.length} files` : "Not generated"}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {preview ? (
                  <>
                    <div className="rounded-md border bg-muted/30 p-3 text-sm">
                      <p className="font-medium">{Math.ceil(preview.estimated_size_bytes / 1024)} KB estimated</p>
                      <p className="mt-1 text-xs text-muted-foreground">{preview.preset.name}</p>
                    </div>
                    <div className="max-h-48 overflow-auto rounded-md border bg-white p-2 text-xs text-muted-foreground">
                      {preview.estimated_files.slice(0, 24).map((file) => <p key={file}>{file}</p>)}
                    </div>
                    {preview.warnings.length ? (
                      <div className="rounded-md border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900">
                        {preview.warnings.slice(0, 4).map((warning) => <p key={warning}>{warning}</p>)}
                      </div>
                    ) : null}
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">Preview an export to inspect package contents and warnings.</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Export</CardTitle>
                <CardDescription>{exportResult ? exportResult.id.slice(0, 8) : "No export yet"}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {exportResult ? (
                  <>
                    <div className="flex items-center justify-between gap-3 rounded-md border bg-white px-3 py-2 text-sm">
                      <span className="font-medium">{exportResult.format}</span>
                      <Badge className={exportResult.status === "failed" ? "border-destructive/40 text-destructive" : ""}>
                        {exportResult.status}
                      </Badge>
                    </div>
                    {exportResult.file_asset ? (
                      <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm">
                        <p className="font-medium">{exportResult.file_asset.filename}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{Math.ceil(exportResult.file_asset.size_bytes / 1024)} KB</p>
                      </div>
                    ) : null}
                    {downloadUrl ? (
                      <Button asChild>
                        <a href={downloadUrl}>
                          <Download className="h-4 w-4" />
                          Download Export
                        </a>
                      </Button>
                    ) : null}
                    <LearningFeedbackControls projectId={projectId} targetType="export" targetId={exportResult.id} compact />
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">No export has been created in this session.</p>
                )}
              </CardContent>
            </Card>
          </aside>
        </section>
      </div>
    </main>
  );
}

function ChecklistItem({ ok, label, message }: { ok: boolean; label: string; message?: string }) {
  return (
    <div className={`flex items-start gap-2 rounded-md border px-3 py-2 text-sm ${ok ? "bg-emerald-50 text-emerald-800" : "bg-muted/30 text-muted-foreground"}`}>
      {ok ? <CheckCircle2 className="mt-0.5 h-4 w-4" /> : <AlertTriangle className="mt-0.5 h-4 w-4" />}
      <span>
        <span className="block font-medium">{label}</span>
        {message ? <span className="mt-0.5 block text-xs opacity-80">{message}</span> : null}
      </span>
    </div>
  );
}

function MetaField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="flex flex-col gap-2 text-sm font-medium">
      {label}
      <Input value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function metadataDraft(metadata: ProjectPublishingMetadata): ProjectPublishingMetadataDraft {
  return {
    title: metadata.title,
    subtitle: metadata.subtitle,
    author_name: metadata.author_name,
    publisher: metadata.publisher,
    language: metadata.language,
    synopsis: metadata.synopsis,
    age_rating: metadata.age_rating,
    genres: metadata.genres,
    tags: metadata.tags,
    copyright_notice: metadata.copyright_notice,
    ai_disclosure_text: metadata.ai_disclosure_text,
    metadata_json: metadata.metadata_json
  };
}

function splitList(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function previewOptions(preset: ExportPreset | null) {
  if (!preset || preset.id !== "webtoon_vertical_strip") {
    return {};
  }
  return {
    spacing: 80,
    max_image_height: 16000,
    panel_slicing: false
  };
}
