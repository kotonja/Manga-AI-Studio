"use client";

import { useEffect, useState } from "react";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import type { GenerationFeedback, LearningFeedbackOptions, LearningIssueType, LearningTargetType } from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

type LearningFeedbackControlsProps = {
  projectId?: string | null;
  targetType: LearningTargetType;
  targetId?: string | null;
  compact?: boolean;
};

export function LearningFeedbackControls({ projectId, targetType, targetId, compact = false }: LearningFeedbackControlsProps) {
  const [options, setOptions] = useState<LearningFeedbackOptions | null>(null);
  const [issueType, setIssueType] = useState<LearningIssueType | "">("");
  const [comment, setComment] = useState("");
  const [correction, setCorrection] = useState("");
  const [allowUse, setAllowUse] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiFetch<LearningFeedbackOptions>("/learning/feedback-options")
      .then((payload) => {
        if (!cancelled) {
          setOptions(payload);
          setAllowUse(payload.default_allow_use_for_product_improvement);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  async function submit(rating: -1 | 1) {
    if (!targetId) {
      setMessage("Save this item first.");
      return;
    }
    setIsSubmitting(true);
    setMessage(null);
    try {
      const feedback = await apiFetch<GenerationFeedback>("/learning/feedback", {
        method: "POST",
        body: JSON.stringify({
          project_id: projectId ?? null,
          target_type: targetType,
          target_id: targetId,
          rating,
          issue_type: issueType || null,
          comment,
          user_correction: correction,
          allow_use_for_product_improvement: allowUse,
          metadata_json: { source: "web", compact }
        })
      });
      setMessage(feedback.allow_use_for_product_improvement ? "Saved for improvement." : "Saved privately.");
      if (rating > 0) {
        setIssueType("");
        setComment("");
        setCorrection("");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Feedback failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="rounded-md border bg-muted/25 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-normal text-muted-foreground">Generation Feedback</span>
        <div className="flex gap-2">
          <Button type="button" size="sm" variant="outline" onClick={() => void submit(1)} disabled={isSubmitting || !targetId}>
            <ThumbsUp className="h-4 w-4" />
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => void submit(-1)} disabled={isSubmitting || !targetId}>
            <ThumbsDown className="h-4 w-4" />
          </Button>
        </div>
      </div>
      {!compact ? (
        <div className="mt-3 grid gap-2">
          <select
            value={issueType}
            onChange={(event) => setIssueType(event.target.value)}
            className="h-9 rounded-md border bg-white px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="">Issue tag</option>
            {(options?.issue_tags ?? fallbackIssueTags()).map((issue) => (
              <option key={issue.id} value={issue.id}>
                {issue.label}
              </option>
            ))}
          </select>
          <Textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Short note" className="min-h-16 text-xs" />
          <Textarea value={correction} onChange={(event) => setCorrection(event.target.value)} placeholder="Correction" className="min-h-16 text-xs" />
          <label className="flex items-start gap-2 text-xs text-muted-foreground">
            <input type="checkbox" checked={allowUse} onChange={(event) => setAllowUse(event.target.checked)} />
            <span>Allow this item to improve Manga AI Studio</span>
          </label>
        </div>
      ) : null}
      {message ? <p className="mt-2 text-xs text-muted-foreground">{message}</p> : null}
    </div>
  );
}

function fallbackIssueTags() {
  return [
    "wrong character",
    "bad hands",
    "bad face",
    "confusing layout",
    "unreadable text",
    "inconsistent style",
    "weak story",
    "wrong tone",
    "export problem",
    "other"
  ].map((tag) => ({ id: tag, label: tag.replace(/\b\w/g, (letter) => letter.toUpperCase()) }));
}
