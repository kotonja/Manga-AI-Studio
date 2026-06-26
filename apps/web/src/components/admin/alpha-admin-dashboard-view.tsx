"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowLeft, MessageSquare, RefreshCcw, ShieldCheck, TrendingUp } from "lucide-react";
import type { AlphaDashboard, ImprovementReport } from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function AlphaAdminDashboardView() {
  const [dashboard, setDashboard] = useState<AlphaDashboard | null>(null);
  const [report, setReport] = useState<ImprovementReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadDashboard() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextDashboard, nextReport] = await Promise.all([
        apiFetch<AlphaDashboard>("/admin/alpha-dashboard"),
        apiFetch<ImprovementReport>("/admin/improvement-report")
      ]);
      setDashboard(nextDashboard);
      setReport(nextReport);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load alpha dashboard");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

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
                <h1 className="text-3xl font-semibold tracking-normal">Alpha Dashboard</h1>
                <Badge>Protected</Badge>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">Tester health, failures, QA blockers, and feedback intake.</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link href="/admin/alpha-readiness">
                <ShieldCheck className="h-4 w-4" />
                Readiness
              </Link>
            </Button>
            <Button variant="outline" onClick={() => void loadDashboard()} disabled={isLoading}>
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </Button>
          </div>
        </header>

        {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div> : null}

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {(dashboard?.metrics ?? []).map((metric) => (
            <Card key={metric.label}>
              <CardHeader className="pb-2">
                <CardDescription>{metric.label}</CardDescription>
                <CardTitle className="text-3xl">{metric.value}</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">{metric.detail}</CardContent>
            </Card>
          ))}
          {isLoading && !dashboard ? [0, 1, 2].map((item) => <div key={item} className="h-32 animate-pulse rounded-md border bg-white" />) : null}
        </section>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Improvement Report
            </CardTitle>
            <CardDescription>{report ? new Date(report.generated_at).toLocaleString() : "Aggregate-only product learning"}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Metric label="Generation" value={percent(report?.generation_success_rate)} />
              <Metric label="Retry" value={percent(report?.retry_rate)} />
              <Metric label="Page QA" value={report?.average_page_qa_score ?? "-"} />
              <Metric label="Export" value={percent(report?.export_success_rate)} />
            </div>
            <div className="rounded-md border bg-muted/35 p-3 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">Weakest stage: {report?.worst_performing_pipeline_stage ?? "-"}</p>
              <p className="mt-2">Best preset: {report?.best_performing_style_or_preset ?? "Not enough data"}</p>
              <p className="mt-2 text-xs">{report?.privacy_note}</p>
            </div>
            <div className="lg:col-span-2 grid gap-3 md:grid-cols-2">
              <div className="rounded-md border bg-white p-3">
                <p className="text-sm font-medium">Common failures</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {(report?.most_common_failures ?? []).length ? (
                    report?.most_common_failures.map((item) => <Badge key={String(item.issue_type)}>{String(item.issue_type)}: {String(item.count)}</Badge>)
                  ) : (
                    <span className="text-sm text-muted-foreground">No opted-in failure ratings yet</span>
                  )}
                </div>
              </div>
              <div className="rounded-md border bg-white p-3">
                <p className="text-sm font-medium">Priorities</p>
                <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-muted-foreground">
                  {(report?.recommended_engineering_priorities ?? []).map((priority) => (
                    <li key={priority}>{priority}</li>
                  ))}
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>

        <section className="grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5" />
                Latest Feedback
              </CardTitle>
              <CardDescription>{dashboard?.feedback_items.length ?? 0} recent items</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {dashboard?.feedback_items.length ? (
                dashboard.feedback_items.map((item) => (
                  <div key={item.id} className="rounded-md border bg-white p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium">{item.title}</p>
                        <p className="mt-1 text-sm text-muted-foreground">{item.description}</p>
                        {item.internal_notes ? <p className="mt-2 text-xs text-muted-foreground">Internal: {item.internal_notes}</p> : null}
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <Badge>{item.status}</Badge>
                        <Badge className={item.severity === "blocker" || item.severity === "blocking" ? "border-destructive/40 bg-destructive/10 text-destructive" : ""}>{item.severity}</Badge>
                      </div>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">{new Date(item.created_at).toLocaleString()}</p>
                  </div>
                ))
              ) : (
                <EmptyState label="No feedback yet" />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                Failed Jobs
              </CardTitle>
              <CardDescription>{dashboard?.failed_jobs.length ?? 0} recent failures</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {dashboard?.failed_jobs.length ? (
                dashboard.failed_jobs.map((job) => (
                  <div key={job.id} className="rounded-md border bg-white p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-medium">{job.job_type}</p>
                      <Badge>{job.provider}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-destructive">{job.error_message ?? "No error message"}</p>
                    <p className="mt-2 text-xs text-muted-foreground">{new Date(job.updated_at).toLocaleString()}</p>
                  </div>
                ))
              ) : (
                <EmptyState label="No failed jobs" />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5" />
                Recent QA Blockers
              </CardTitle>
              <CardDescription>{dashboard?.recent_qa_failures.length ?? 0} reports</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {dashboard?.recent_qa_failures.length ? (
                dashboard.recent_qa_failures.map((report) => (
                  <div key={report.id} className="rounded-md border bg-white p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-medium">{report.target_type}</p>
                      <Badge>{report.overall_score}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{report.issues.length} issue records</p>
                  </div>
                ))
              ) : (
                <EmptyState label="No blocking QA reports" />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Provider Errors</CardTitle>
              <CardDescription>Safe metadata only, no secrets</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {dashboard?.provider_errors.length ? (
                dashboard.provider_errors.map((job) => (
                  <pre key={job.id} className="max-h-40 overflow-auto rounded-md bg-muted/60 p-3 text-xs">
                    {JSON.stringify(job.output_payload.error_metadata ?? job.output_payload, null, 2)}
                  </pre>
                ))
              ) : (
                <EmptyState label="No provider errors" />
              )}
            </CardContent>
          </Card>
        </section>
      </div>
    </main>
  );
}

function EmptyState({ label }: { label: string }) {
  return <div className="rounded-md border bg-muted/40 px-4 py-8 text-center text-sm text-muted-foreground">{label}</div>;
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border bg-white p-3">
      <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
    </div>
  );
}

function percent(value: number | undefined) {
  return value == null ? "-" : `${Math.round(value * 100)}%`;
}
