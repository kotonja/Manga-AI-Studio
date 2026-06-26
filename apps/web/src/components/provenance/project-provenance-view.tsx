"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowLeft, FileCheck2, RefreshCcw, Save, ShieldCheck, X } from "lucide-react";
import type { ProjectProvenance, ProvenanceAsset, RightsDeclarationDraft, SafetyCheckResult } from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

const emptyDeclaration: RightsDeclarationDraft = {
  user_confirms_upload_rights: false,
  user_confirms_no_unlicensed_ip: false,
  user_confirms_review_required_before_publish: true,
  notes: ""
};

export function ProjectProvenanceView({ projectId }: { projectId: string }) {
  const [provenance, setProvenance] = useState<ProjectProvenance | null>(null);
  const [draft, setDraft] = useState<RightsDeclarationDraft>(emptyDeclaration);
  const [selectedAsset, setSelectedAsset] = useState<ProvenanceAsset | null>(null);
  const [styleText, setStyleText] = useState("make exactly like a famous manga franchise");
  const [safety, setSafety] = useState<SafetyCheckResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadProvenance() {
    setIsLoading(true);
    setError(null);
    try {
      const next = await apiFetch<ProjectProvenance>(`/projects/${projectId}/provenance`);
      setProvenance(next);
      setDraft(next.rights_declaration ?? emptyDeclaration);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load provenance");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadProvenance();
  }, [projectId]);

  const declarationComplete = useMemo(() => {
    return Boolean(
      provenance?.rights_declaration?.user_confirms_upload_rights &&
        provenance.rights_declaration.user_confirms_no_unlicensed_ip &&
        provenance.rights_declaration.user_confirms_review_required_before_publish
    );
  }, [provenance]);

  async function saveDeclaration() {
    setIsSaving(true);
    setError(null);
    try {
      await apiFetch(`/projects/${projectId}/rights-declaration`, {
        method: "PUT",
        body: JSON.stringify(draft)
      });
      await loadProvenance();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to save rights declaration");
    } finally {
      setIsSaving(false);
    }
  }

  async function checkStyleSafety() {
    setError(null);
    try {
      const result = await apiFetch<SafetyCheckResult>("/safety/check", {
        method: "POST",
        body: JSON.stringify({
          target: "style_request",
          text: styleText,
          metadata: {}
        })
      });
      setSafety(result);
    } catch (checkError) {
      setError(checkError instanceof Error ? checkError.message : "Unable to check style/IP safety");
    }
  }

  if (isLoading && provenance === null) {
    return (
      <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-md border bg-white px-4 py-8 text-sm text-muted-foreground">
          Loading Provenance Room
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
                <h1 className="text-3xl font-semibold tracking-normal">Provenance</h1>
                <Badge>{provenance?.summary.total_assets ?? 0} assets</Badge>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">Creator rights, AI disclosure, asset source tracking, and style/IP warnings</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={() => void loadProvenance()}>
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </Button>
            <Button onClick={() => void saveDeclaration()} disabled={isSaving}>
              <Save className="h-4 w-4" />
              {isSaving ? "Saving" : "Save Rights"}
            </Button>
          </div>
        </header>

        {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div> : null}

        {safety && !safety.allowed ? (
          <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <div className="flex items-center gap-2 font-medium">
              <AlertTriangle className="h-4 w-4" />
              Style/IP warning
            </div>
            <p className="mt-1">{safety.issues[0]?.message ?? "Rewrite this as original visual attributes."}</p>
            {safety.suggested_text ? <p className="mt-2 text-xs">Suggestion: {safety.suggested_text}</p> : null}
          </div>
        ) : null}

        <section className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
          <div className="flex flex-col gap-4">
            <RightsEditor draft={draft} setDraft={setDraft} onSave={saveDeclaration} isSaving={isSaving} />
            <Card>
              <CardHeader>
                <CardTitle>Style/IP Guard</CardTitle>
                <CardDescription>Check prompts before saving style or export notes</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <Textarea value={styleText} onChange={(event) => setStyleText(event.target.value)} />
                <Button variant="outline" onClick={() => void checkStyleSafety()}>
                  <ShieldCheck className="h-4 w-4" />
                  Check Prompt
                </Button>
                {safety ? (
                  <Badge className={safety.allowed ? "" : "border-amber-400 text-amber-900"}>{safety.severity}</Badge>
                ) : null}
              </CardContent>
            </Card>
          </div>

          <div className="flex min-w-0 flex-col gap-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <Metric label="Assets" value={provenance?.summary.total_assets ?? 0} />
              <Metric label="Tracked" value={provenance?.summary.assets_with_provenance ?? 0} />
              <Metric label="Disclosure" value={provenance?.summary.ai_disclosure_required ? "Required" : "Not required"} />
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Asset Provenance</CardTitle>
                <CardDescription>Click an asset to inspect source, provider, rights, and disclosure metadata</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {provenance?.assets.length ? (
                  provenance.assets.map((item) => (
                    <button
                      key={item.asset.id}
                      type="button"
                      onClick={() => setSelectedAsset(item)}
                      className="grid gap-2 rounded-md border bg-white px-4 py-3 text-left text-sm transition-colors hover:border-primary/60 sm:grid-cols-[minmax(0,1fr)_140px_120px]"
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{item.asset.filename}</span>
                        <span className="text-xs text-muted-foreground">{item.asset.kind}</span>
                      </span>
                      <Badge>{item.provenance?.source_type ?? "missing"}</Badge>
                      <Badge className={item.provenance?.ai_disclosure_required ? "border-amber-400 text-amber-900" : ""}>
                        {item.provenance?.ai_disclosure_required ? "disclose" : "clear"}
                      </Badge>
                    </button>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">No assets have been created yet.</p>
                )}
              </CardContent>
            </Card>
          </div>
        </section>
      </div>

      {!declarationComplete ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/30 px-4">
          <div className="w-full max-w-xl rounded-md border bg-white p-5 shadow-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">Upload Rights Confirmation</h2>
                <p className="mt-1 text-sm text-muted-foreground">Confirm this before adding uploaded references or style samples.</p>
              </div>
              <FileCheck2 className="h-5 w-5" />
            </div>
            <div className="mt-4">
              <RightsEditor draft={draft} setDraft={setDraft} onSave={saveDeclaration} isSaving={isSaving} compact />
            </div>
          </div>
        </div>
      ) : null}

      {selectedAsset ? <AssetDrawer item={selectedAsset} onClose={() => setSelectedAsset(null)} /> : null}
    </main>
  );
}

function RightsEditor({
  draft,
  setDraft,
  onSave,
  isSaving,
  compact = false
}: {
  draft: RightsDeclarationDraft;
  setDraft: (draft: RightsDeclarationDraft) => void;
  onSave: () => Promise<void>;
  isSaving: boolean;
  compact?: boolean;
}) {
  return (
    <Card className={compact ? "border-0 shadow-none" : ""}>
      {!compact ? (
        <CardHeader>
          <CardTitle>Export Disclosure Metadata</CardTitle>
          <CardDescription>Rights declaration stored with the project and included in exports</CardDescription>
        </CardHeader>
      ) : null}
      <CardContent className={compact ? "flex flex-col gap-3 p-0" : "flex flex-col gap-3"}>
        <CheckboxLine
          checked={draft.user_confirms_upload_rights}
          label="I have rights to upload and use project reference assets"
          onChange={(value) => setDraft({ ...draft, user_confirms_upload_rights: value })}
        />
        <CheckboxLine
          checked={draft.user_confirms_no_unlicensed_ip}
          label="I confirm uploaded content does not include unlicensed IP"
          onChange={(value) => setDraft({ ...draft, user_confirms_no_unlicensed_ip: value })}
        />
        <CheckboxLine
          checked={draft.user_confirms_review_required_before_publish}
          label="I will review rights and disclosures before publishing"
          onChange={(value) => setDraft({ ...draft, user_confirms_review_required_before_publish: value })}
        />
        <label className="flex flex-col gap-2 text-sm font-medium">
          Notes
          <Textarea value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} />
        </label>
        <Button onClick={() => void onSave()} disabled={isSaving}>
          <Save className="h-4 w-4" />
          {isSaving ? "Saving" : "Save Declaration"}
        </Button>
      </CardContent>
    </Card>
  );
}

function CheckboxLine({ checked, label, onChange }: { checked: boolean; label: string; onChange: (value: boolean) => void }) {
  return (
    <label className="flex items-start gap-3 rounded-md border bg-muted/30 px-3 py-2 text-sm">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="mt-1" />
      <span>{label}</span>
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border bg-white px-4 py-3">
      <p className="text-xs uppercase tracking-normal text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </div>
  );
}

function AssetDrawer({ item, onClose }: { item: ProvenanceAsset; onClose: () => void }) {
  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l bg-white shadow-xl">
      <div className="flex items-start justify-between gap-4 border-b px-5 py-4">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold">{item.asset.filename}</h2>
          <p className="text-sm text-muted-foreground">{item.asset.kind}</p>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex-1 overflow-auto p-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <Metric label="Source" value={item.provenance?.source_type ?? "missing"} />
          <Metric label="License" value={item.provenance?.license_type ?? "missing"} />
          <Metric label="Provider" value={item.provenance?.provider_name ?? "none"} />
          <Metric label="Disclosure" value={item.provenance?.ai_disclosure_required ? "Required" : "Not required"} />
        </div>
        <div className="mt-5 rounded-md border bg-muted/30 p-4">
          <h3 className="text-sm font-semibold">Rights</h3>
          <p className="mt-2 text-sm text-muted-foreground">{item.provenance?.declared_rights || "No rights statement recorded."}</p>
        </div>
        <div className="mt-5 rounded-md border bg-black/90 p-4 text-xs text-white">
          <pre className="whitespace-pre-wrap break-words">{JSON.stringify(item, null, 2)}</pre>
        </div>
      </div>
    </div>
  );
}
