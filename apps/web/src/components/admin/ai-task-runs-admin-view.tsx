"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, BrainCircuit, RefreshCcw } from "lucide-react";
import type { AITaskRun } from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function AITaskRunsAdminView() {
  const [runs, setRuns] = useState<AITaskRun[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadRuns() {
    setIsLoading(true);
    setError(null);
    try {
      setRuns(await apiFetch<AITaskRun[]>("/admin/ai-task-runs?limit=75"));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load AI task runs");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadRuns();
  }, []);

  const latestRun = useMemo(() => runs[0] ?? null, [runs]);

  return (
    <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="flex flex-col gap-4 border-b pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex flex-col gap-3">
            <Button asChild variant="ghost" size="sm" className="w-fit">
              <Link href="/">
                <ArrowLeft className="h-4 w-4" />
                Dashboard
              </Link>
            </Button>
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-semibold tracking-normal">AI Task Runs</h1>
                <Badge>Dev only</Badge>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                {latestRun ? `Latest: ${latestRun.task_type}` : "Prompt registry execution history"}
              </p>
            </div>
          </div>
          <Button variant="outline" onClick={() => void loadRuns()} disabled={isLoading}>
            <RefreshCcw className="h-4 w-4" />
            Refresh
          </Button>
        </header>

        {error ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BrainCircuit className="h-5 w-5" />
              Recent Runs
            </CardTitle>
            <CardDescription>{runs.length} records</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="rounded-md border bg-white px-4 py-8 text-sm text-muted-foreground">Loading task runs</div>
            ) : runs.length === 0 ? (
              <div className="rounded-md border bg-white px-4 py-8 text-sm text-muted-foreground">No AI task runs yet</div>
            ) : (
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full min-w-[1080px] border-collapse bg-white text-sm">
                  <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-3 py-3 font-medium">Task</th>
                      <th className="px-3 py-3 font-medium">Status</th>
                      <th className="px-3 py-3 font-medium">Provider</th>
                      <th className="px-3 py-3 font-medium">Created</th>
                      <th className="px-3 py-3 font-medium">Error</th>
                      <th className="px-3 py-3 font-medium">Raw Output</th>
                      <th className="px-3 py-3 font-medium">Parsed Output</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => (
                      <tr key={run.id} className="border-t align-top">
                        <td className="max-w-[180px] px-3 py-3">
                          <p className="font-medium">{run.task_type}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{run.prompt_template_id}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{run.schema_name}</p>
                        </td>
                        <td className="px-3 py-3">
                          <RunStatusBadge status={run.status} />
                        </td>
                        <td className="px-3 py-3">
                          <p>{run.provider}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{run.model ?? "no model"}</p>
                        </td>
                        <td className="px-3 py-3 text-xs text-muted-foreground">
                          {new Date(run.created_at).toLocaleString()}
                        </td>
                        <td className="max-w-[180px] px-3 py-3 text-xs text-destructive">
                          {run.error_message ? preview(run.error_message, 220) : ""}
                        </td>
                        <td className="max-w-[260px] px-3 py-3">
                          <PreviewBlock value={run.raw_output ?? ""} />
                        </td>
                        <td className="max-w-[300px] px-3 py-3">
                          <PreviewBlock value={previewJson(run.parsed_output)} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}

function RunStatusBadge({ status }: { status: AITaskRun["status"] }) {
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

function PreviewBlock({ value }: { value: string }) {
  return (
    <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-muted/60 p-3 text-xs leading-5 text-muted-foreground">
      {preview(value, 1200)}
    </pre>
  );
}

function previewJson(value: unknown) {
  if (value == null) {
    return "";
  }
  return JSON.stringify(value, null, 2);
}

function preview(value: string, maxLength: number) {
  return value.length > maxLength ? `${value.slice(0, maxLength - 3)}...` : value;
}
