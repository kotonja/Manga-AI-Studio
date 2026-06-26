import { CheckCircle2, Clock3, Download, Eye, Loader2, PencilLine } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

const chipStyles: Record<string, { className: string; icon: LucideIcon }> = {
  Draft: { className: "border-slate-300 bg-white text-slate-700", icon: PencilLine },
  Planning: { className: "border-sky-200 bg-sky-50 text-sky-800", icon: Clock3 },
  Rendering: { className: "border-violet-200 bg-violet-50 text-violet-800", icon: Loader2 },
  "Needs Review": { className: "border-amber-300 bg-amber-50 text-amber-900", icon: Eye },
  "QA Passed": { className: "border-emerald-300 bg-emerald-50 text-emerald-800", icon: CheckCircle2 },
  Exported: { className: "border-teal-300 bg-teal-50 text-teal-800", icon: Download }
};

export function StatusChip({ status, className }: { status: string | null | undefined; className?: string }) {
  const label = normalizeStatus(status);
  const config = chipStyles[label] ?? chipStyles.Draft;
  const Icon = config.icon;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium", config.className, className)}>
      <Icon className={cn("h-3.5 w-3.5", label === "Rendering" && "animate-spin")} />
      {label}
    </span>
  );
}

export function normalizeStatus(status: string | null | undefined) {
  if (!status) {
    return "Draft";
  }
  const normalized = status
    .replaceAll("_", " ")
    .split(" ")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
  if (normalized === "Qa Passed") {
    return "QA Passed";
  }
  return normalized;
}
