"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Activity, ArrowLeft, BarChart3, CheckCircle2, ExternalLink, Play, RefreshCcw, XCircle } from "lucide-react";
import type { EvalRunReport, EvalScenario } from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const metricLabels: Record<string, string> = {
  pipeline_completion_rate: "Pipeline",
  story_schema_validity: "Story Schema",
  page_count_accuracy: "Pages",
  panel_count_accuracy: "Panels",
  character_state_coverage: "Character State",
  prompt_anchor_coverage: "Prompt Anchors",
  render_asset_coverage: "Renders",
  composition_success_rate: "Composition",
  lettering_readability_score: "Lettering",
  qa_blocking_issue_count: "Blocking QA",
  export_success_rate: "Exports",
  total_generation_time: "Time",
  estimated_cost: "Cost"
};

export function EvalHarnessAdminView() {
  const [scenarios, setScenarios] = useState<EvalScenario[]>([]);
  const [scenario, setScenario] = useState("all");
  const [provider, setProvider] = useState("mock");
  const [qualityMode, setQualityMode] = useState("fast");
  const [report, setReport] = useState<EvalRunReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadScenarios() {
    setIsLoading(true);
    setError(null);
    try {
      setScenarios(await apiFetch<EvalScenario[]>("/eval/scenarios"));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load evaluation scenarios");
    } finally {
      setIsLoading(false);
    }
  }

  async function runEval() {
    setIsRunning(true);
    setError(null);
    try {
      setReport(
        await apiFetch<EvalRunReport>("/eval/run", {
          method: "POST",
          body: JSON.stringify({
            scenario,
            provider,
            quality_mode: qualityMode,
            write_reports: true
          })
        })
      );
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Evaluation run failed");
    } finally {
      setIsRunning(false);
    }
  }

  useEffect(() => {
    void loadScenarios();
  }, []);

  const selectedScenarioName = useMemo(() => {
    if (scenario === "all") {
      return "All scenarios";
    }
    return scenarios.find((item) => item.id === scenario)?.name ?? scenario;
  }, [scenario, scenarios]);

  return (
    <main className="min-h-screen bg-muted/20 px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="flex flex-col gap-4 border-b bg-background/80 pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex flex-col gap-3">
            <Button asChild variant="ghost" size="sm" className="w-fit">
              <Link href="/">
                <ArrowLeft className="h-4 w-4" />
                Dashboard
              </Link>
            </Button>
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-semibold tracking-normal">Evaluation Harness</h1>
                <Badge>Dev only</Badge>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                {report ? `Latest run: ${report.scenario_count} scenario${report.scenario_count === 1 ? "" : "s"}` : selectedScenarioName}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void loadScenarios()} disabled={isLoading || isRunning}>
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </Button>
            <Button onClick={() => void runEval()} disabled={isLoading || isRunning}>
              <Play className="h-4 w-4" />
              {isRunning ? "Running" : "Run Eval"}
            </Button>
          </div>
        </header>

        {error ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        ) : null}

        <section className="grid gap-4 lg:grid-cols-[360px_1fr]">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5" />
                Run Setup
              </CardTitle>
              <CardDescription>{scenarios.length} scenarios loaded</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <label className="flex flex-col gap-2 text-sm font-medium">
                Scenario
                <select
                  value={scenario}
                  onChange={(event) => setScenario(event.target.value)}
                  className="h-10 rounded-md border bg-background px-3 text-sm"
                >
                  <option value="all">All scenarios</option>
                  {scenarios.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="flex flex-col gap-2 text-sm font-medium">
                Provider
                <select
                  value={provider}
                  onChange={(event) => setProvider(event.target.value)}
                  className="h-10 rounded-md border bg-background px-3 text-sm"
                >
                  <option value="mock">Mock</option>
                  <option value="openai">OpenAI</option>
                  <option value="comfyui">ComfyUI</option>
                </select>
              </label>

              <label className="flex flex-col gap-2 text-sm font-medium">
                Quality
                <select
                  value={qualityMode}
                  onChange={(event) => setQualityMode(event.target.value)}
                  className="h-10 rounded-md border bg-background px-3 text-sm"
                >
                  <option value="fast">Fast</option>
                  <option value="balanced">Balanced</option>
                  <option value="high">High</option>
                </select>
              </label>

              <div className="rounded-md border bg-white p-3 text-xs text-muted-foreground">
                Reports write to <span className="font-medium text-foreground">eval_reports/latest.json</span> and{" "}
                <span className="font-medium text-foreground">eval_reports/latest.md</span>.
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                Aggregate Metrics
              </CardTitle>
              <CardDescription>
                {report ? `${report.provider} · ${report.quality_mode} · ${new Date(report.completed_at).toLocaleString()}` : "No run yet"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isRunning ? (
                <div className="rounded-md border bg-white px-4 py-10 text-center text-sm text-muted-foreground">
                  Running evaluation pipeline
                </div>
              ) : report ? (
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {Object.entries(report.metrics).map(([key, value]) => (
                    <MetricTile key={key} label={metricLabels[key] ?? key} value={value} />
                  ))}
                </div>
              ) : (
                <div className="rounded-md border bg-white px-4 py-10 text-center text-sm text-muted-foreground">
                  Run an evaluation to populate metrics
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        <section className="grid gap-4">
          {isLoading ? (
            <div className="rounded-md border bg-white px-4 py-8 text-sm text-muted-foreground">Loading scenarios</div>
          ) : report ? (
            report.scenarios.map((item) => <ScenarioResultCard key={item.project_id} result={item} />)
          ) : (
            scenarios.map((item) => <ScenarioDefinitionCard key={item.id} scenario={item} />)
          )}
        </section>
      </div>
    </main>
  );
}

function ScenarioDefinitionCard({ scenario }: { scenario: EvalScenario }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle>{scenario.name}</CardTitle>
            <CardDescription>{scenario.premise}</CardDescription>
          </div>
          <Badge>{scenario.page_count} pages</Badge>
        </div>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-3">
        <DefinitionList title="Expected" values={[`${scenario.expected_character_count} characters`, `${scenario.expected_location_count} location`, `${scenario.expected_panel_count ?? scenario.page_count * 2} panels`]} />
        <DefinitionList title="Beats" values={scenario.expected_key_beats} />
        <DefinitionList title="Page Types" values={scenario.expected_page_types} />
      </CardContent>
    </Card>
  );
}

function ScenarioResultCard({ result }: { result: EvalRunReport["scenarios"][number] }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              {result.status === "passed" ? <CheckCircle2 className="h-5 w-5 text-primary" /> : <XCircle className="h-5 w-5 text-destructive" />}
              <CardTitle>{result.scenario.name}</CardTitle>
              <Badge className={cn(result.status === "passed" ? "border-primary/30 bg-primary/10 text-primary" : "border-destructive/30 bg-destructive/10 text-destructive")}>
                {result.status}
              </Badge>
            </div>
            <CardDescription>{result.scenario.premise}</CardDescription>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link href={result.links.project}>
              Open Project
              <ExternalLink className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {Object.entries(result.scores).slice(0, 10).map(([key, value]) => (
            <MetricTile key={key} label={metricLabels[key] ?? key} value={value} compact />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
          <DefinitionList title="Counts" values={Object.entries(result.counts).map(([key, value]) => `${key}: ${value}`)} />
          <DefinitionList
            title="Failures"
            values={result.failures.length > 0 ? result.failures : ["No failures recorded"]}
            danger={result.failures.length > 0}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function MetricTile({
  label,
  value,
  compact = false
}: {
  label: string;
  value: number | string | null;
  compact?: boolean;
}) {
  return (
    <div className={cn("rounded-md border bg-white p-4", compact && "p-3")}>
      <p className="text-xs font-medium uppercase text-muted-foreground">{label}</p>
      <p className={cn("mt-2 font-semibold", compact ? "text-xl" : "text-2xl")}>{formatMetric(value)}</p>
    </div>
  );
}

function DefinitionList({ title, values, danger = false }: { title: string; values: string[]; danger?: boolean }) {
  return (
    <div className="rounded-md border bg-white p-4">
      <p className="text-xs font-medium uppercase text-muted-foreground">{title}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {values.map((value) => (
          <Badge key={value} className={cn(danger && "border-destructive/30 bg-destructive/10 text-destructive")}>
            {value}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function formatMetric(value: number | string | null) {
  if (value === null) {
    return "n/a";
  }
  if (typeof value === "number") {
    if (value > 0 && value <= 1) {
      return `${Math.round(value * 100)}%`;
    }
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  return value;
}
