"use client";

import { useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { Bug, Clipboard, MessageSquare, X } from "lucide-react";
import type { FeedbackItem } from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type FeedbackDraft = {
  category: string;
  severity: "low" | "medium" | "high" | "blocking";
  title: string;
  description: string;
  contact_email: string;
};

const emptyDraft: FeedbackDraft = {
  category: "bug",
  severity: "medium",
  title: "",
  description: "",
  contact_email: ""
};

export function FeedbackButton() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(emptyDraft);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const context = useMemo(() => contextFromPath(pathname), [pathname]);

  async function submit() {
    if (!draft.title.trim() || !draft.description.trim()) {
      setMessage("Please add a title and description.");
      return;
    }
    setIsSubmitting(true);
    setMessage(null);
    try {
      await apiFetch<FeedbackItem>("/feedback", {
        method: "POST",
        body: JSON.stringify({
          ...context,
          category: draft.category,
          severity: draft.severity,
          title: draft.title.trim(),
          description: draft.description.trim(),
          contact_email: draft.contact_email.trim() || null,
          browser_info: {
            userAgent: navigator.userAgent,
            language: navigator.language,
            viewport: `${window.innerWidth}x${window.innerHeight}`
          },
          context: {
            pathname,
            href: window.location.href,
            project_id: context.project_id,
            page_id: context.page_id,
            panel_id: context.panel_id
          },
          diagnostic_info: {
            timestamp: new Date().toISOString(),
            app: "manga-ai-studio-web"
          }
        })
      });
      setMessage("Feedback sent. Thank you.");
      setDraft(emptyDraft);
      window.setTimeout(() => setOpen(false), 900);
    } catch (submitError) {
      setMessage(submitError instanceof Error ? submitError.message : "Unable to submit feedback.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function copyDiagnostics() {
    const diagnostic = {
      pathname,
      href: window.location.href,
      context,
      userAgent: navigator.userAgent,
      timestamp: new Date().toISOString()
    };
    await navigator.clipboard.writeText(JSON.stringify(diagnostic, null, 2));
    setMessage("Diagnostic info copied.");
  }

  return (
    <>
      <Button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-50 shadow-lg"
        size="sm"
      >
        <MessageSquare className="h-4 w-4" />
        Feedback
      </Button>

      {open ? (
        <div className="fixed inset-0 z-[60] flex items-end justify-end bg-black/30 p-4 sm:items-end">
          <div className="w-full max-w-md rounded-md border bg-white p-4 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">Send Alpha Feedback</h2>
                <p className="mt-1 text-sm text-muted-foreground">Bug reports include current project/page context when available.</p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="mt-4 grid gap-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="flex flex-col gap-1 text-sm font-medium">
                  Category
                  <select
                    value={draft.category}
                    onChange={(event) => setDraft((current) => ({ ...current, category: event.target.value }))}
                    className="h-10 rounded-md border bg-background px-3 text-sm"
                  >
                    <option value="bug">Bug</option>
                    <option value="confusing">Confusing</option>
                    <option value="quality">Quality</option>
                    <option value="idea">Idea</option>
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-sm font-medium">
                  Severity
                  <select
                    value={draft.severity}
                    onChange={(event) => setDraft((current) => ({ ...current, severity: event.target.value as FeedbackDraft["severity"] }))}
                    className="h-10 rounded-md border bg-background px-3 text-sm"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="blocking">Blocking</option>
                  </select>
                </label>
              </div>
              <Input
                placeholder="Short title"
                value={draft.title}
                onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
              />
              <Textarea
                placeholder="What happened? What did you expect?"
                value={draft.description}
                onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))}
              />
              <Input
                placeholder="Email, Discord, or blank"
                value={draft.contact_email}
                onChange={(event) => setDraft((current) => ({ ...current, contact_email: event.target.value }))}
              />
              <div className="rounded-md border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
                Context: {context.project_id ? `project ${context.project_id.slice(0, 8)}` : "app-wide"}
                {context.page_id ? ` / page ${context.page_id.slice(0, 8)}` : ""}
              </div>
              {message ? <div className="rounded-md border bg-muted/50 px-3 py-2 text-sm">{message}</div> : null}
              <div className="flex flex-wrap justify-between gap-2">
                <Button variant="outline" onClick={() => void copyDiagnostics()}>
                  <Clipboard className="h-4 w-4" />
                  Copy diagnostics
                </Button>
                <Button onClick={() => void submit()} disabled={isSubmitting}>
                  <Bug className="h-4 w-4" />
                  {isSubmitting ? "Sending" : "Send feedback"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

function contextFromPath(pathname: string) {
  const parts = pathname.split("/").filter(Boolean);
  const projectIndex = parts.indexOf("projects");
  const pagesIndex = parts.indexOf("pages");
  return {
    project_id: projectIndex >= 0 ? parts[projectIndex + 1] ?? null : null,
    page_id: pagesIndex >= 0 ? parts[pagesIndex + 1] ?? null : null,
    panel_id: null
  };
}
