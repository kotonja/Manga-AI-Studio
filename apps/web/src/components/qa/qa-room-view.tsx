"use client";

import Link from "next/link";
import { ArrowLeft, ExternalLink, RefreshCcw, ShieldCheck, Sparkles, Wrench } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { QAAutoFixResult, QAIssue, QAProjectRunResult, QAReport, ProjectDetail } from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type SeverityFilter = "all" | "blocking" | "warning" | "info";

export function QARoomView({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [result, setResult] = useState<QAProjectRunResult | null>(null);
  const [lastFix, setLastFix] = useState<QAAutoFixResult | null>(null);
  const [severity, setSeverity] = useState<SeverityFilter>("all");
  const [category, setCategory] = useState("all");
  const [isLoading, setIsLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [isFixing, setIsFixing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadProject() {
    setIsLoading(true);
    setError(null);
    try {
      setProject(await apiFetch<ProjectDetail>(`/projects/${projectId}`));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load project");
    } finally {
      setIsLoading(false);
    }
  }

  async function runFullQA() {
    setIsRunning(true);
    setError(null);
    try {
      const next = await apiFetch<QAProjectRunResult>(`/projects/${projectId}/qa/run-full`, {
        method: "POST",
        body: JSON.stringify({ provider_name: "mock", export_preset: "draft" })
      });
      setResult(next);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Unable to run project QA");
    } finally {
      setIsRunning(false);
    }
  }

  async function applySafeFixes() {
    if (!result) {
      return;
    }
    setIsFixing(true);
    setError(null);
    try {
      let latestFix: QAAutoFixResult | null = null;
      for (const report of result.page_reports) {
        if (!report.auto_fix_available) {
          continue;
        }
        latestFix = await apiFetch<QAAutoFixResult>(`/pages/${report.target_id}/qa/auto-fix-safe`, { method: "POST" });
      }
      setLastFix(latestFix);
      await runFullQA();
    } catch (fixError) {
      setError(fixError instanceof Error ? fixError.message : "Unable to apply safe fixes");
    } finally {
      setIsFixing(false);
    }
  }

  useEffect(() => {
    void loadProject();
  }, [projectId]);

  const issues = useMemo(() => {
    return (result?.page_reports ?? []).flatMap((report) =>
      report.issues.map((issue) => ({ report, issue }))
    );
  }, [result]);
  const categories = useMemo(() => {
    return Array.from(new Set(issues.map(({ issue }) => issue.issue_category || issue.category))).sort();
  }, [issues]);
  const filteredIssues = issues.filter(({ issue }) => {
    const issueSeverity = normalizeSeverity(issue);
    const issueCategory = issue.issue_category || issue.category;
    return (severity === "all" || issueSeverity === severity) && (category === "all" || issueCategory === category);
  });
  const grouped = groupIssues(filteredIssues);

  if (isLoading && !project) {
    return (
      <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-md border bg-white px-4 py-8 text-sm text-muted-foreground">Loading QA room</div>
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
              <h1 className="text-3xl font-semibold tracking-normal">QA Room</h1>
              <p className="mt-2 max-w-3xl text-sm text-muted-foreground">{project?.name ?? "Project"} quality checks and safe repairs</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void runFullQA()} disabled={isRunning}>
              <ShieldCheck className="h-4 w-4" />
              {isRunning ? "Running" : "Run Full QA"}
            </Button>
            <Button onClick={() => void applySafeFixes()} disabled={!result?.project_report.auto_fix_available || isFixing}>
              <Wrench className="h-4 w-4" />
              {isFixing ? "Fixing" : "Apply Safe Fixes"}
            </Button>
            <Button variant="outline" onClick={() => void loadProject()}>
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </Button>
          </div>
        </header>

        {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div> : null}

        <section className="grid gap-4 md:grid-cols-4">
          <Metric label="Overall" value={result?.project_report.overall_score ?? "-"} tone={scoreTone(result?.project_report.overall_score)} />
          <Metric label="Issues" value={issues.length} />
          <Metric label="Blocking" value={issues.filter(({ issue }) => issue.blocking).length} tone="bad" />
          <Metric label="Safe Fixes" value={issues.filter(({ issue }) => issue.auto_fix_available).length} tone="good" />
        </section>

        <section className="flex flex-wrap items-center gap-2">
          {(["all", "blocking", "warning", "info"] as SeverityFilter[]).map((item) => (
            <Button key={item} variant={severity === item ? "default" : "outline"} size="sm" onClick={() => setSeverity(item)}>
              {item}
            </Button>
          ))}
          <select value={category} onChange={(event) => setCategory(event.target.value)} className="h-9 rounded-md border bg-white px-3 text-sm">
            <option value="all">all categories</option>
            {categories.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </section>

        {lastFix ? (
          <div className="rounded-md border bg-white px-4 py-3 text-sm">
            <div className="flex items-center gap-2 font-medium">
              <Sparkles className="h-4 w-4" />
              Last safe fix pass
            </div>
            <p className="mt-1 text-muted-foreground">
              Applied {lastFix.applied.length}, skipped {lastFix.skipped.length}
              {lastFix.before_report && lastFix.after_report ? ` - score ${lastFix.before_report.overall_score} to ${lastFix.after_report.overall_score}` : ""}
            </p>
          </div>
        ) : null}

        {!result ? (
          <Card>
            <CardHeader>
              <CardTitle>Run QA</CardTitle>
              <CardDescription>Check every page for layout, render, lettering, continuity, story, export, safety, and style issues.</CardDescription>
            </CardHeader>
            <CardContent>
              <Button onClick={() => void runFullQA()} disabled={isRunning}>
                <ShieldCheck className="h-4 w-4" />
                {isRunning ? "Running QA" : "Run Full QA"}
              </Button>
            </CardContent>
          </Card>
        ) : null}

        <section className="flex flex-col gap-4">
          {Object.entries(grouped).map(([group, groupIssues]) => (
            <Card key={group}>
              <CardHeader>
                <CardTitle>{group}</CardTitle>
                <CardDescription>{groupIssues.length} issues</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {groupIssues.map(({ report, issue }) => (
                  <IssueRow key={`${report.id}-${issue.id}`} projectId={projectId} report={report} issue={issue} />
                ))}
              </CardContent>
            </Card>
          ))}
        </section>
      </div>
    </main>
  );
}

function IssueRow({ projectId, report, issue }: { projectId: string; report: QAReport; issue: QAIssue }) {
  const pageId = issue.page_id ?? report.page_id ?? report.target_id;
  const issueSeverity = normalizeSeverity(issue);
  return (
    <div className="rounded-md border bg-white px-3 py-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 font-medium">
            <Badge className={issue.blocking ? "border-destructive/40 text-destructive" : ""}>{issueSeverity}</Badge>
            <Badge className="border-muted-foreground/30 text-muted-foreground">{issue.issue_category || issue.category}</Badge>
            <span>{issue.code.replaceAll("_", " ")}</span>
          </div>
          <p className="mt-1 text-muted-foreground">{issue.message}</p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link href={`/projects/${projectId}/pages/${pageId}/studio`}>
            <ExternalLink className="h-4 w-4" />
            Jump
          </Link>
        </Button>
      </div>
      {issue.auto_fix_available ? <p className="mt-2 text-xs text-muted-foreground">Safe fix: {String(issue.auto_fix_action["type"] ?? "available")}</p> : null}
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string | number; tone?: "good" | "bad" | "warn" }) {
  return (
    <div className="rounded-md border bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">{label}</p>
      <p className={`mt-2 text-3xl font-semibold ${tone === "good" ? "text-emerald-700" : tone === "bad" ? "text-destructive" : tone === "warn" ? "text-amber-700" : ""}`}>{value}</p>
    </div>
  );
}

function groupIssues(items: Array<{ report: QAReport; issue: QAIssue }>) {
  return items.reduce<Record<string, Array<{ report: QAReport; issue: QAIssue }>>>((groups, item) => {
    const pageLabel = item.issue.page_id ? `Page ${item.report.page_id === item.issue.page_id ? "" : ""}${item.issue.page_id.slice(0, 8)}` : "Project";
    const category = item.issue.issue_category || item.issue.category;
    const key = `${category} - ${pageLabel}`;
    groups[key] = [...(groups[key] ?? []), item];
    return groups;
  }, {});
}

function normalizeSeverity(issue: QAIssue): SeverityFilter {
  if (issue.blocking || issue.severity === "blocking" || issue.severity === "error") {
    return "blocking";
  }
  if (issue.severity === "info") {
    return "info";
  }
  return "warning";
}

function scoreTone(score: number | undefined): "good" | "bad" | "warn" | undefined {
  if (score === undefined) {
    return undefined;
  }
  if (score >= 85) {
    return "good";
  }
  if (score >= 65) {
    return "warn";
  }
  return "bad";
}
