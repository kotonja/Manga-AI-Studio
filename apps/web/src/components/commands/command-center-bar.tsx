"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Bot, CheckCircle2, ChevronDown, History, Loader2, Play, Sparkles, XCircle } from "lucide-react";
import { usePathname } from "next/navigation";
import type {
  CommandExecuteResult,
  CommandHistory as CommandHistoryItem,
  CommandInterpretResult,
  CommandScope,
  CommandScopeType
} from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const scopeOptions: CommandScopeType[] = ["project", "page", "panel", "bubble", "character", "style", "chapter"];

export function CommandCenterBar() {
  const pathname = usePathname();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const routeContext = useMemo(() => inferRouteContext(pathname), [pathname]);
  const [open, setOpen] = useState(false);
  const [scopeType, setScopeType] = useState<CommandScopeType>("project");
  const [scopeId, setScopeId] = useState("");
  const [command, setCommand] = useState("");
  const [interpretation, setInterpretation] = useState<CommandInterpretResult | null>(null);
  const [execution, setExecution] = useState<CommandExecuteResult | null>(null);
  const [history, setHistory] = useState<CommandHistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"interpret" | "execute" | null>(null);

  useEffect(() => {
    if (!routeContext.projectId) {
      return;
    }
    setScopeType(routeContext.scope.type);
    setScopeId(routeContext.scope.id);
    setInterpretation(null);
    setExecution(null);
    setError(null);
  }, [routeContext.projectId, routeContext.scope.id, routeContext.scope.type]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((current) => !current);
        window.setTimeout(() => inputRef.current?.focus(), 0);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!open || !routeContext.projectId) {
      return;
    }
    void loadHistory(routeContext.projectId);
  }, [open, routeContext.projectId]);

  async function loadHistory(projectId: string) {
    try {
      const nextHistory = await apiFetch<CommandHistoryItem[]>(`/projects/${projectId}/commands?limit=6`);
      setHistory(nextHistory);
    } catch {
      setHistory([]);
    }
  }

  async function interpret(event?: FormEvent) {
    event?.preventDefault();
    if (!routeContext.projectId || !scopeId.trim() || !command.trim()) {
      return;
    }
    setBusy("interpret");
    setError(null);
    setExecution(null);
    try {
      const result = await apiFetch<CommandInterpretResult>("/commands/interpret", {
        method: "POST",
        body: JSON.stringify({
          project_id: routeContext.projectId,
          scope: { type: scopeType, id: scopeId.trim() },
          command: command.trim()
        })
      });
      setInterpretation(result);
      await loadHistory(routeContext.projectId);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Command interpretation failed");
    } finally {
      setBusy(null);
    }
  }

  async function execute(confirmed: boolean) {
    if (!routeContext.projectId || !scopeId.trim() || !command.trim()) {
      return;
    }
    setBusy("execute");
    setError(null);
    try {
      const result = await apiFetch<CommandExecuteResult>("/commands/execute", {
        method: "POST",
        body: JSON.stringify({
          project_id: routeContext.projectId,
          scope: { type: scopeType, id: scopeId.trim() },
          command: command.trim(),
          confirmed
        })
      });
      setExecution(result);
      setInterpretation(result);
      await loadHistory(routeContext.projectId);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Command execution failed");
    } finally {
      setBusy(null);
    }
  }

  const disabled = !routeContext.projectId;
  const canSubmit = Boolean(routeContext.projectId && scopeId.trim() && command.trim() && !busy);
  const riskTone = riskClass(interpretation?.risk_level);

  return (
    <div className="fixed inset-x-0 bottom-4 z-50 flex justify-center px-4 pointer-events-none">
      <div className="w-full max-w-3xl pointer-events-auto">
        {!open ? (
          <button
            type="button"
            onClick={() => {
              setOpen(true);
              window.setTimeout(() => inputRef.current?.focus(), 0);
            }}
            className="mx-auto flex h-12 items-center gap-3 rounded-md border bg-foreground px-4 text-sm font-medium text-background shadow-2xl transition hover:translate-y-[-1px]"
          >
            <Bot className="h-4 w-4" />
            Command Center
          </button>
        ) : (
          <div className="rounded-md border bg-white shadow-2xl">
            <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold">Manga AI Command Center</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {routeContext.projectId ? `Targeting ${scopeType}` : "Open a project to run editing commands"}
                  </p>
                </div>
              </div>
              <button
                type="button"
                className="rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
                onClick={() => setOpen(false)}
                aria-label="Close Command Center"
              >
                <XCircle className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={interpret} className="space-y-3 p-4">
              <div className="grid gap-2 md:grid-cols-[11rem_1fr]">
                <label className="relative">
                  <span className="sr-only">Target type</span>
                  <select
                    value={scopeType}
                    onChange={(event) => setScopeType(event.target.value as CommandScopeType)}
                    disabled={disabled}
                    className="h-10 w-full appearance-none rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                  >
                    {scopeOptions.map((scope) => (
                      <option key={scope} value={scope}>
                        {scope}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-muted-foreground" />
                </label>
                <label>
                  <span className="sr-only">Target id</span>
                  <input
                    value={scopeId}
                    onChange={(event) => setScopeId(event.target.value)}
                    disabled={disabled}
                    className="h-10 w-full rounded-md border bg-background px-3 font-mono text-xs outline-none focus:ring-2 focus:ring-ring"
                    placeholder="Target id"
                  />
                </label>
              </div>

              <div className="flex gap-2">
                <label className="min-w-0 flex-1">
                  <span className="sr-only">Command</span>
                  <input
                    ref={inputRef}
                    value={command}
                    onChange={(event) => {
                      setCommand(event.target.value);
                      setInterpretation(null);
                      setExecution(null);
                    }}
                    disabled={disabled}
                    className="h-11 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                    placeholder="Make page 3 more dramatic."
                  />
                </label>
                <Button type="submit" disabled={!canSubmit} variant="outline">
                  {busy === "interpret" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  Interpret
                </Button>
              </div>

              {error ? <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{error}</div> : null}

              {interpretation ? (
                <div className="rounded-md border bg-muted/35 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge className={cn("border-transparent", riskTone)}>{interpretation.risk_level}</Badge>
                    <Badge>{interpretation.intent.replaceAll("_", " ")}</Badge>
                    {interpretation.requires_confirmation ? <Badge className="border-amber-300 bg-amber-50 text-amber-900">confirmation required</Badge> : null}
                    {execution ? <Badge className="border-emerald-300 bg-emerald-50 text-emerald-800">{execution.status}</Badge> : null}
                  </div>
                  <p className="mt-2 text-sm text-foreground">{interpretation.summary}</p>
                  <div className="mt-3 grid gap-2">
                    {interpretation.proposed_actions.map((action, index) => (
                      <div key={`${action.action_type}-${index}`} className="rounded-md border bg-white p-2 text-xs">
                        <div className="flex items-center justify-between gap-3">
                          <span className="font-semibold">{action.action_type.replaceAll("_", " ")}</span>
                          <span className="text-muted-foreground">{action.target_type}</span>
                        </div>
                        <p className="mt-1 text-muted-foreground">{action.summary}</p>
                      </div>
                    ))}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      disabled={!canSubmit}
                      onClick={() => execute(Boolean(interpretation.requires_confirmation))}
                      variant={interpretation.requires_confirmation ? "destructive" : "default"}
                    >
                      {busy === "execute" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                      {interpretation.requires_confirmation ? "Confirm and Execute" : "Execute"}
                    </Button>
                    {execution?.status === "executed" ? (
                      <span className="inline-flex items-center gap-2 text-sm text-emerald-700">
                        <CheckCircle2 className="h-4 w-4" />
                        Applied {execution.executed_actions.length} action{execution.executed_actions.length === 1 ? "" : "s"}
                      </span>
                    ) : null}
                  </div>
                </div>
              ) : null}

              {history.length ? (
                <div className="border-t pt-3">
                  <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-normal text-muted-foreground">
                    <History className="h-3.5 w-3.5" />
                    Recent Commands
                  </div>
                  <div className="grid gap-2">
                    {history.slice(0, 4).map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => {
                          setCommand(item.command);
                          setScopeType(item.scope_type as CommandScopeType);
                          setScopeId(String(item.scope_id));
                          setInterpretation(null);
                          setExecution(null);
                        }}
                        className="rounded-md border bg-background px-3 py-2 text-left text-xs hover:bg-muted"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <span className="truncate font-medium">{item.command}</span>
                          <Badge className={riskClass(item.risk_level)}>{item.status}</Badge>
                        </div>
                        <p className="mt-1 truncate text-muted-foreground">{item.summary}</p>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
            </form>
          </div>
        )}
      </div>
    </div>
  );
}

function inferRouteContext(pathname: string): { projectId: string | null; scope: CommandScope } {
  const projectMatch = pathname.match(/\/projects\/([^/]+)/);
  const projectId = projectMatch?.[1] ?? null;
  if (!projectId) {
    return { projectId: null, scope: { type: "project", id: "" } };
  }
  const pageMatch = pathname.match(/\/projects\/[^/]+\/pages\/([^/]+)/);
  if (pageMatch?.[1]) {
    return { projectId, scope: { type: "page", id: pageMatch[1] } };
  }
  return { projectId, scope: { type: "project", id: projectId } };
}

function riskClass(risk?: string | null) {
  if (risk === "high" || risk === "failed") {
    return "border-destructive/30 bg-destructive/10 text-destructive";
  }
  if (risk === "medium" || risk === "blocked") {
    return "border-amber-300 bg-amber-50 text-amber-900";
  }
  if (risk === "executed" || risk === "low") {
    return "border-emerald-300 bg-emerald-50 text-emerald-800";
  }
  return "bg-white";
}
