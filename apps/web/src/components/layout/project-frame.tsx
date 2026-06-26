"use client";

import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  Brush,
  ChevronLeft,
  Clapperboard,
  FileCheck2,
  FileDown,
  LayoutDashboard,
  Map,
  MessageSquareText,
  PanelTop,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  UserRound
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ProjectDetail, ProjectWorkspaceSummary } from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { StatusChip } from "@/components/layout/status-chip";
import { Badge } from "@/components/ui/badge";

type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  disabled?: boolean;
};

export function ProjectFrame({ projectId, children }: { projectId: string; children: ReactNode }) {
  const pathname = usePathname();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [summary, setSummary] = useState<ProjectWorkspaceSummary | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadFrame() {
      try {
        const [nextProject, nextSummary] = await Promise.all([
          apiFetch<ProjectDetail>(`/projects/${projectId}`),
          apiFetch<ProjectWorkspaceSummary>(`/projects/${projectId}/workspace-summary`).catch(() => null)
        ]);
        if (!cancelled) {
          setProject(nextProject);
          setSummary(nextSummary);
        }
      } catch {
        if (!cancelled) {
          setProject(null);
          setSummary(null);
        }
      }
    }
    void loadFrame();
    return () => {
      cancelled = true;
    };
  }, [projectId, pathname]);

  const firstPageId = project?.pages[0]?.id ?? null;
  const navItems = useMemo<NavItem[]>(() => {
    const pageHref = firstPageId ? `/projects/${projectId}/pages/${firstPageId}/studio` : `/projects/${projectId}`;
    const letteringHref = firstPageId ? `/projects/${projectId}/pages/${firstPageId}/lettering` : `/projects/${projectId}`;
    return [
      { label: "Dashboard", href: `/projects/${projectId}`, icon: LayoutDashboard },
      { label: "Director Mode", href: `/projects/${projectId}/director`, icon: Clapperboard },
      { label: "Story Room", href: `/projects/${projectId}/story`, icon: BookOpen },
      { label: "Character Lab", href: `/projects/${projectId}/characters`, icon: UserRound },
      { label: "World Room", href: `/projects/${projectId}/world`, icon: Map },
      { label: "Style Lab", href: `/projects/${projectId}/style`, icon: Brush },
      { label: "Page Studio", href: pageHref, icon: PanelTop, disabled: !firstPageId },
      { label: "Lettering Room", href: letteringHref, icon: MessageSquareText, disabled: !firstPageId },
      { label: "QA Room", href: `/projects/${projectId}/qa`, icon: ShieldCheck },
      { label: "Publishing", href: `/projects/${projectId}/publishing`, icon: FileDown },
      { label: "Settings", href: `/projects/${projectId}/settings`, icon: Settings }
    ];
  }, [firstPageId, projectId]);

  const pageCount = summary?.page_count ?? project?.pages.length ?? 0;
  const panelCount = summary?.panel_count ?? project?.pages.reduce((total, page) => total + page.panels.length, 0) ?? 0;
  const renderProgress = Math.round((summary?.render_progress ?? 0) * 100);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.9),transparent_34rem),linear-gradient(180deg,rgba(255,255,255,0.72),rgba(247,244,237,0.92))]">
      <div className="mx-auto flex min-h-screen max-w-[1800px] flex-col lg:flex-row">
        <aside className="border-b bg-white/88 backdrop-blur lg:sticky lg:top-0 lg:h-screen lg:w-72 lg:shrink-0 lg:border-b-0 lg:border-r">
          <div className="flex h-full flex-col gap-5 p-4">
            <Link href="/" className="inline-flex w-fit items-center gap-2 rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-muted">
              <ChevronLeft className="h-4 w-4" />
              Projects
            </Link>

            <div className="rounded-md border bg-background/70 p-4">
              <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">Project</p>
              <h2 className="mt-2 max-h-14 overflow-hidden text-xl font-semibold leading-tight">{project?.name ?? "Loading project"}</h2>
              <div className="mt-3 flex flex-wrap gap-2">
                <StatusChip status={summary?.status_chip ?? project?.status ?? "Draft"} />
                <Badge>{project?.status ?? "draft"}</Badge>
              </div>
              <p className="mt-3 max-h-12 overflow-hidden text-xs text-muted-foreground">{project?.description || "No series brief yet"}</p>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <SidebarMetric label="Chapter" value={summary?.active_chapter_title ?? "Unplanned"} />
              <SidebarMetric label="Pages" value={pageCount} />
              <SidebarMetric label="Panels" value={panelCount} />
              <SidebarMetric label="QA" value={summary?.qa_score != null ? `${summary.qa_score}` : "-"} />
            </div>

            <div className="rounded-md border bg-white p-3">
              <div className="mb-2 flex items-center justify-between gap-3 text-xs">
                <span className="font-medium text-muted-foreground">Render progress</span>
                <span className="font-semibold">{renderProgress}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-primary" style={{ width: `${renderProgress}%` }} />
              </div>
              <div className="mt-3 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                <span>{summary?.rendered_panel_count ?? 0}/{panelCount} panels</span>
                <span>{summary?.active_job_count ?? 0} active jobs</span>
              </div>
            </div>

            <nav className="flex flex-col gap-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                const active = pathname === item.href || (item.href !== `/projects/${projectId}` && pathname.startsWith(item.href));
                return (
                  <Link
                    key={item.label}
                    href={item.href}
                    aria-disabled={item.disabled}
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                      active && "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground",
                      item.disabled && "pointer-events-none opacity-45"
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            <div className="mt-auto rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
              <div className="flex items-center gap-2 font-medium text-foreground">
                <FileCheck2 className="h-4 w-4" />
                Export status
              </div>
              <p className="mt-1">{summary?.export_status ? summary.export_status.replaceAll("_", " ") : "No export yet"}</p>
              {summary?.qa_blocking ? <p className="mt-2 text-amber-800">Blocking QA issues need review before publish.</p> : null}
            </div>
          </div>
        </aside>

        <section className="min-w-0 flex-1">
          <div className="border-b bg-white/72 px-4 py-3 backdrop-blur lg:hidden">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">{project?.name ?? "Project"}</p>
                <p className="text-xs text-muted-foreground">{pageCount} pages - {panelCount} panels</p>
              </div>
              <StatusChip status={summary?.status_chip ?? project?.status ?? "Draft"} />
            </div>
          </div>
          {children}
        </section>
      </div>
    </div>
  );
}

function SidebarMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="min-w-0 rounded-md border bg-white p-3">
      <p className="text-[11px] font-medium uppercase tracking-normal text-muted-foreground">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold">{value}</p>
    </div>
  );
}
