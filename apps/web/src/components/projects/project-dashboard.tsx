"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Clapperboard, FolderOpen, Plus, ShieldCheck, Wand2 } from "lucide-react";
import type { DemoPipelineResult, Project } from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { StatusChip } from "@/components/layout/status-chip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type ProjectDraft = {
  name: string;
  description: string;
  style_prompt: string;
};

const emptyDraft: ProjectDraft = {
  name: "",
  description: "",
  style_prompt: ""
};

function projectDescriptionPreview(description: string | null) {
  const value = description?.trim();
  if (!value) {
    return "Untitled series brief";
  }
  return value.length > 280 ? `${value.slice(0, 277)}...` : value;
}

export function ProjectDashboard() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [draft, setDraft] = useState<ProjectDraft>(emptyDraft);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isCreatingDemo, setIsCreatingDemo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadProjects() {
    setIsLoading(true);
    setError(null);
    try {
      setProjects(await apiFetch<Project[]>("/projects"));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load projects");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadProjects();
  }, []);

  async function createProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.name.trim()) {
      setError("Project name is required");
      return;
    }

    setIsCreating(true);
    setError(null);
    try {
      const project = await apiFetch<Project>("/projects", {
        method: "POST",
        body: JSON.stringify({
          name: draft.name.trim(),
          description: draft.description.trim() || null,
          style_prompt: draft.style_prompt.trim() || null
        })
      });
      setProjects((current) => [project, ...current]);
      setDraft(emptyDraft);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Unable to create project");
    } finally {
      setIsCreating(false);
    }
  }

  async function createDemoManga() {
    setIsCreatingDemo(true);
    setError(null);
    try {
      const demo = await apiFetch<DemoPipelineResult>("/demo/create-full-project", {
        method: "POST",
        body: JSON.stringify({})
      });
      setProjects((current) => [demo.project, ...current.filter((project) => project.id !== demo.project.id)]);
      router.push(`/projects/${demo.project.id}`);
    } catch (demoError) {
      setError(demoError instanceof Error ? demoError.message : "Unable to create demo manga");
    } finally {
      setIsCreatingDemo(false);
    }
  }

  return (
    <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="rounded-md border bg-white/86 p-5 shadow-sm backdrop-blur">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-semibold tracking-normal text-foreground">Manga AI Studio</h1>
                <Badge className="bg-primary/10 text-primary">Local development</Badge>
              </div>
              <p className="mt-2 max-w-2xl text-sm text-muted-foreground">A production workspace for story planning, page layout, render direction, lettering, QA, provenance, and export.</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button asChild>
                <Link href="/demo">
                  <Clapperboard className="h-4 w-4" />
                  Founder Demo
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/onboarding">
                  <ShieldCheck className="h-4 w-4" />
                  Alpha Guide
                </Link>
              </Button>
              <Button variant="outline" onClick={() => void createDemoManga()} disabled={isCreatingDemo}>
                <Wand2 className="h-4 w-4" />
                {isCreatingDemo ? "Creating Demo" : "Create Demo Manga"}
              </Button>
            </div>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <DashboardMetric label="Projects" value={projects.length} />
            <DashboardMetric label="Drafts" value={projects.filter((project) => project.status === "draft").length} />
            <DashboardMetric label="Recent" value={projects[0] ? new Date(projects[0].updated_at).toLocaleDateString() : "-"} />
          </div>
        </header>

        {error ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
          <Card>
            <CardHeader>
              <CardTitle>New Project</CardTitle>
              <CardDescription>Draft a manga workspace</CardDescription>
            </CardHeader>
            <CardContent>
              <form className="flex flex-col gap-4" onSubmit={createProject}>
                <label className="flex flex-col gap-2 text-sm font-medium">
                  Name
                  <Input
                    value={draft.name}
                    onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Skyline Ronin"
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm font-medium">
                  Description
                  <Textarea
                    value={draft.description}
                    onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))}
                    placeholder="Serialized sci-fi action manga"
                  />
                </label>
                <label className="flex flex-col gap-2 text-sm font-medium">
                  Style Prompt
                  <Textarea
                    value={draft.style_prompt}
                    onChange={(event) => setDraft((current) => ({ ...current, style_prompt: event.target.value }))}
                    placeholder="High-contrast ink, cinematic speed lines, crisp backgrounds"
                  />
                </label>
                <Button type="submit" disabled={isCreating}>
                  <Plus className="h-4 w-4" />
                  {isCreating ? "Creating" : "Create Project"}
                </Button>
              </form>
            </CardContent>
          </Card>

          <section className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Project Dashboard</h2>
              <Button variant="outline" size="sm" onClick={() => void loadProjects()} disabled={isLoading}>
                Refresh
              </Button>
            </div>

            {isLoading ? (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {[0, 1, 2].map((item) => (
                  <div key={item} className="h-44 animate-pulse rounded-md border bg-white/70" />
                ))}
              </div>
            ) : projects.length === 0 ? (
              <div className="rounded-md border bg-white px-6 py-10 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-md border bg-muted">
                  <FolderOpen className="h-6 w-6 text-muted-foreground" />
                </div>
                <h3 className="mt-4 text-lg font-semibold">No projects yet</h3>
                <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">Create a fresh manga workspace or seed the full demo pipeline to explore the studio.</p>
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  <Button asChild>
                    <Link href="/demo">
                      <Clapperboard className="h-4 w-4" />
                      Founder Demo
                    </Link>
                  </Button>
                  <Button variant="outline" onClick={() => void createDemoManga()} disabled={isCreatingDemo}>
                    <Wand2 className="h-4 w-4" />
                    Create Demo Manga
                  </Button>
                </div>
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {projects.map((project) => (
                  <Card key={project.id} className="transition-colors hover:border-primary/60">
                    <CardHeader>
                      <div className="flex items-start justify-between gap-3">
                        <CardTitle className="leading-snug">{project.name}</CardTitle>
                        <StatusChip status={project.status} />
                      </div>
                      <CardDescription>{projectDescriptionPreview(project.description)}</CardDescription>
                    </CardHeader>
                    <CardContent className="flex items-center justify-between gap-3">
                      <span className="text-xs text-muted-foreground">
                        {new Date(project.updated_at).toLocaleDateString()}
                      </span>
                      <Button asChild size="sm">
                        <Link href={`/projects/${project.id}`}>
                          <FolderOpen className="h-4 w-4" />
                          Open
                        </Link>
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}

function DashboardMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border bg-background/70 px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
    </div>
  );
}
