"use client";

import { GitCompareArrows, History, RotateCcw, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { VersionDiffResult, VersionRecord, VersionRestoreResult } from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function VersionHistorySidebar({ projectId, onRestored }: { projectId: string; onRestored?: () => void }) {
  const [versions, setVersions] = useState<VersionRecord[]>([]);
  const [checkpointLabel, setCheckpointLabel] = useState("Manual checkpoint");
  const [compareA, setCompareA] = useState<string | null>(null);
  const [compareB, setCompareB] = useState<string | null>(null);
  const [diff, setDiff] = useState<VersionDiffResult | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadVersions() {
    try {
      setVersions(await apiFetch<VersionRecord[]>(`/projects/${projectId}/versions`));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load versions");
    }
  }

  async function createCheckpoint() {
    setIsBusy(true);
    setError(null);
    try {
      await apiFetch<VersionRecord[]>(`/projects/${projectId}/checkpoint`, {
        method: "POST",
        body: JSON.stringify({ label: checkpointLabel.trim() || "Manual checkpoint", created_by: "user", reason: "manual_checkpoint" })
      });
      await loadVersions();
    } catch (checkpointError) {
      setError(checkpointError instanceof Error ? checkpointError.message : "Unable to create checkpoint");
    } finally {
      setIsBusy(false);
    }
  }

  async function restoreVersion(versionId: string) {
    setIsBusy(true);
    setError(null);
    try {
      await apiFetch<VersionRestoreResult>(`/versions/${versionId}/restore`, { method: "POST" });
      await loadVersions();
      onRestored?.();
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : "Unable to restore version");
    } finally {
      setIsBusy(false);
    }
  }

  useEffect(() => {
    void loadVersions();
  }, [projectId]);

  useEffect(() => {
    if (!compareA || !compareB || compareA === compareB) {
      setDiff(null);
      return;
    }
    let cancelled = false;
    apiFetch<VersionDiffResult>(`/versions/${compareA}/diff/${compareB}`)
      .then((nextDiff) => {
        if (!cancelled) {
          setDiff(nextDiff);
        }
      })
      .catch((diffError) => {
        if (!cancelled) {
          setError(diffError instanceof Error ? diffError.message : "Unable to compare versions");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [compareA, compareB]);

  const selectedA = useMemo(() => versions.find((version) => version.id === compareA) ?? null, [versions, compareA]);
  const selectedB = useMemo(() => versions.find((version) => version.id === compareB) ?? null, [versions, compareB]);
  const imageA = selectedA ? imageUrlForVersion(selectedA) : null;
  const imageB = selectedB ? imageUrlForVersion(selectedB) : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="h-5 w-5" />
          Version History
        </CardTitle>
        <CardDescription>{versions.length} recoverable snapshots</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex gap-2">
          <Input value={checkpointLabel} onChange={(event) => setCheckpointLabel(event.target.value)} />
          <Button onClick={() => void createCheckpoint()} disabled={isBusy} title="Create checkpoint">
            <Save className="h-4 w-4" />
          </Button>
        </div>
        {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">{error}</div> : null}

        {diff ? (
          <div className="rounded-md border bg-muted/40 p-3 text-xs">
            <div className="mb-2 flex items-center gap-2 font-medium">
              <GitCompareArrows className="h-4 w-4" />
              Compare
            </div>
            {imageA || imageB ? (
              <div className="mb-3 grid grid-cols-2 gap-2">
                <ImagePreview label="A" url={imageA} />
                <ImagePreview label="B" url={imageB} />
              </div>
            ) : null}
            <pre className="max-h-48 overflow-auto rounded-md bg-white p-2">{JSON.stringify(diff.changed, null, 2)}</pre>
          </div>
        ) : null}

        <div className="flex max-h-[520px] flex-col gap-2 overflow-auto pr-1">
          {versions.length === 0 ? <p className="text-sm text-muted-foreground">No versions yet</p> : null}
          {versions.map((version) => (
            <div key={version.id} className="rounded-md border bg-white p-3 text-sm">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge>{version.entity_type}</Badge>
                    {version.is_checkpoint ? <Badge className="border-primary/30 text-primary">checkpoint</Badge> : null}
                  </div>
                  <p className="mt-2 truncate font-medium">{version.label || version.reason || version.id.slice(0, 8)}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{new Date(version.created_at).toLocaleString()}</p>
                  {version.asset_ids.length ? <p className="mt-1 truncate text-xs text-muted-foreground">Assets: {version.asset_ids.join(", ")}</p> : null}
                </div>
                <Button variant="outline" size="sm" onClick={() => void restoreVersion(version.id)} disabled={isBusy}>
                  <RotateCcw className="h-4 w-4" />
                </Button>
              </div>
              <div className="mt-3 flex gap-2">
                <Button variant={compareA === version.id ? "default" : "outline"} size="sm" onClick={() => setCompareA(version.id)}>
                  A
                </Button>
                <Button variant={compareB === version.id ? "default" : "outline"} size="sm" onClick={() => setCompareB(version.id)}>
                  B
                </Button>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function ImagePreview({ label, url }: { label: string; url: string | null }) {
  return (
    <div className="rounded-md border bg-white p-2">
      <p className="mb-1 text-xs font-medium">Version {label}</p>
      {url ? <img src={url} alt={`Version ${label}`} className="h-28 w-full object-contain" /> : <p className="text-xs text-muted-foreground">No image URL</p>}
    </div>
  );
}

function imageUrlForVersion(version: VersionRecord): string | null {
  const snapshot = version.snapshot_json as Record<string, unknown>;
  const render = snapshot["render"] as Record<string, unknown> | undefined;
  if (typeof render?.["public_url"] === "string") {
    return render["public_url"];
  }
  const asset = snapshot["asset"] as Record<string, unknown> | undefined;
  const metadata = asset?.["metadata_json"] as Record<string, unknown> | undefined;
  if (typeof metadata?.["public_url"] === "string") {
    return metadata["public_url"];
  }
  return null;
}
