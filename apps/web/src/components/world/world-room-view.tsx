"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Boxes, Compass, Map, RefreshCcw, Wand2 } from "lucide-react";
import type { ProjectDetail, StoryBible } from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function WorldRoomView({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [storyBible, setStoryBible] = useState<StoryBible | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadWorld() {
    setIsLoading(true);
    setError(null);
    try {
      const nextProject = await apiFetch<ProjectDetail>(`/projects/${projectId}`);
      setProject(nextProject);
      try {
        setStoryBible(await apiFetch<StoryBible>(`/projects/${projectId}/story/bible`));
      } catch {
        setStoryBible(null);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load World Room");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadWorld();
  }, [projectId]);

  async function generateStoryBible() {
    setIsGenerating(true);
    setError(null);
    try {
      const bible = await apiFetch<StoryBible>(`/projects/${projectId}/story/generate-bible`, {
        method: "POST",
        body: JSON.stringify({
          premise: project?.description || project?.name || null,
          chapter_count: 3
        })
      });
      setStoryBible(bible);
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : "Unable to generate world data");
    } finally {
      setIsGenerating(false);
    }
  }

  if (isLoading && !project) {
    return (
      <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl rounded-md border bg-white px-4 py-8 text-sm text-muted-foreground">Loading World Room</div>
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
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-semibold tracking-normal">World Room</h1>
                <Badge>{project?.name ?? "Project"}</Badge>
              </div>
              <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
                {storyBible?.main_conflict || "Locations, objects, world rules, and continuity constraints for the manga."}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={() => void loadWorld()}>
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </Button>
            <Button onClick={() => void generateStoryBible()} disabled={isGenerating}>
              <Wand2 className="h-4 w-4" />
              {isGenerating ? "Generating" : "Generate World"}
            </Button>
          </div>
        </header>

        {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div> : null}

        {!storyBible ? (
          <Card>
            <CardHeader>
              <CardTitle>No world bible yet</CardTitle>
              <CardDescription>Generate a Story Bible to seed locations, key objects, rules, and continuity.</CardDescription>
            </CardHeader>
            <CardContent>
              <Button onClick={() => void generateStoryBible()} disabled={isGenerating}>
                <Wand2 className="h-4 w-4" />
                Generate Story Bible
              </Button>
            </CardContent>
          </Card>
        ) : (
          <>
            <section className="grid gap-4 lg:grid-cols-3">
              <WorldMetric label="Locations" value={storyBible.locations.length} />
              <WorldMetric label="Key Objects" value={storyBible.key_objects.length} />
              <WorldMetric label="Rules" value={storyBible.world_rules.length + storyBible.continuity_rules.length} />
            </section>

            <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
              <div className="flex flex-col gap-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Map className="h-4 w-4" />
                      Locations
                    </CardTitle>
                    <CardDescription>Scene anchors and environment rules</CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-3 md:grid-cols-2">
                    {storyBible.locations.length === 0 ? (
                      <Empty label="No locations yet" />
                    ) : (
                      storyBible.locations.map((location) => (
                        <div key={location.id ?? location.name} className="rounded-md border bg-white p-4">
                          <div className="flex items-start justify-between gap-3">
                            <h3 className="font-semibold">{location.name}</h3>
                            <Compass className="h-4 w-4 text-muted-foreground" />
                          </div>
                          <p className="mt-2 text-sm text-muted-foreground">{location.description}</p>
                          {location.visual_notes ? <p className="mt-2 text-xs">{location.visual_notes}</p> : null}
                          <div className="mt-3 flex flex-wrap gap-2">
                            {location.rules.map((rule) => <Badge key={rule}>{rule}</Badge>)}
                          </div>
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Boxes className="h-4 w-4" />
                      Key Objects
                    </CardTitle>
                    <CardDescription>Props that must stay visually and narratively consistent</CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-3 md:grid-cols-2">
                    {storyBible.key_objects.length === 0 ? (
                      <Empty label="No key objects yet" />
                    ) : (
                      storyBible.key_objects.map((object) => (
                        <div key={object.id ?? object.name} className="rounded-md border bg-white p-4">
                          <h3 className="font-semibold">{object.name}</h3>
                          <p className="mt-2 text-sm text-muted-foreground">{object.description}</p>
                          <p className="mt-3 text-xs font-medium">{object.significance}</p>
                          {object.visual_notes ? <p className="mt-2 text-xs text-muted-foreground">{object.visual_notes}</p> : null}
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>
              </div>

              <aside className="flex flex-col gap-4">
                <Card>
                  <CardHeader>
                    <CardTitle>World Rules</CardTitle>
                    <CardDescription>Logic the story should not violate</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-2">
                    {storyBible.world_rules.length === 0 ? <Empty label="No world rules" /> : storyBible.world_rules.map((rule) => <Rule key={rule} value={rule} />)}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Continuity Rules</CardTitle>
                    <CardDescription>Persistent production constraints</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-2">
                    {storyBible.continuity_rules.length === 0 ? <Empty label="No continuity rules" /> : storyBible.continuity_rules.map((rule) => <Rule key={rule} value={rule} />)}
                  </CardContent>
                </Card>
              </aside>
            </section>
          </>
        )}
      </div>
    </main>
  );
}

function WorldMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">{label}</p>
      <p className="mt-2 text-3xl font-semibold">{value}</p>
    </div>
  );
}

function Rule({ value }: { value: string }) {
  return <div className="rounded-md border bg-muted/40 px-3 py-2 text-sm">{value}</div>;
}

function Empty({ label }: { label: string }) {
  return <p className="rounded-md border bg-muted/30 px-3 py-4 text-sm text-muted-foreground">{label}</p>;
}
