"use client";

import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowLeft, Brush, Check, ImageIcon, RefreshCcw, Save, Sparkles } from "lucide-react";
import type {
  ProjectDetail,
  StyleBibleLab,
  StyleDNAOption,
  StyleDNAOptionsResult,
  StyleGuardResult,
  StylePreviewResult,
  StyleSampleAsset
} from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type StyleDraft = Omit<StyleBibleLab, "id" | "project_id" | "story_bible_id" | "created_at" | "updated_at">;

const emptyDraft: StyleDraft = {
  name: "",
  style_name: "",
  style_intent: "",
  line_weight: "",
  line_variation: "",
  line_texture: "",
  face_shape_language: "",
  eye_design_language: "",
  nose_mouth_simplification: "",
  anatomy_proportions: "",
  hair_rendering: "",
  clothing_fold_style: "",
  background_density: "",
  architecture_detail: "",
  shadow_strategy: "",
  screentone_strategy: "",
  hatching_strategy: "",
  black_fill_ratio: "",
  speedline_style: "",
  impact_frame_style: "",
  panel_border_style: "",
  gutter_style: "",
  sfx_shape_language: "",
  bubble_style: "",
  emotional_visual_rules: [],
  positive_prompt_fragments: [],
  negative_prompt_fragments: [],
  forbidden_artist_references: [],
  forbidden_franchise_references: [],
  linework: "",
  screentone: "",
  hatching: "",
  black_white_balance: "",
  face_language: "",
  anatomy_style: "",
  background_detail: "",
  panel_rhythm: "",
  sfx_style: "",
  typography_notes: "",
  forbidden_references: [],
  prompt_style_positive: "",
  prompt_style_negative: ""
};

export function StyleLabView({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [styles, setStyles] = useState<StyleBibleLab[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<StyleDraft>(emptyDraft);
  const [sampleFilename, setSampleFilename] = useState("style-sample.png");
  const [samples, setSamples] = useState<StyleSampleAsset[]>([]);
  const [dnaOptions, setDnaOptions] = useState<StyleDNAOption[]>([]);
  const [generatorDraft, setGeneratorDraft] = useState({
    genre: "supernatural samurai drama",
    tone: "melancholy, tense, protective",
    audience: "teen",
    visual_keywords: "rain\nruined city\nghost light\nswordsman silhouettes",
    avoid_keywords: "artist names\nfranchise references\npainterly color",
    sample_story_summary: "A lonely swordsman protects a ghost child in a ruined city."
  });
  const [safety, setSafety] = useState<StyleGuardResult | null>(null);
  const [preview, setPreview] = useState<StylePreviewResult | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadLab() {
    setError(null);
    try {
      const [nextProject, nextStyles] = await Promise.all([
        apiFetch<ProjectDetail>(`/projects/${projectId}`),
        apiFetch<StyleBibleLab[]>(`/projects/${projectId}/style-bibles`)
      ]);
      setProject(nextProject);
      setStyles(nextStyles);
      const selected =
        (selectedId && nextStyles.find((style) => style.id === selectedId)) ||
        nextStyles.find((style) => style.id === nextProject.active_style_bible_id) ||
        nextStyles[0];
      if (selected) {
        selectStyle(selected);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load Style Lab");
    }
  }

  useEffect(() => {
    void loadLab();
  }, [projectId]);

  useEffect(() => {
    if (!draft.name.trim()) {
      setSafety(null);
      return;
    }
    const timer = window.setTimeout(() => {
      void checkSafety(false);
    }, 500);
    return () => window.clearTimeout(timer);
  }, [draft]);

  const selectedStyle = useMemo(() => styles.find((style) => style.id === selectedId) ?? null, [styles, selectedId]);

  function selectStyle(style: StyleBibleLab) {
    setSelectedId(style.id);
    setDraft(toDraft(style));
    setSamples([]);
    setPreview(null);
  }

  function startNew() {
    setSelectedId(null);
    setDraft({ ...emptyDraft, name: "New Style Bible" });
    setSamples([]);
    setPreview(null);
  }

  async function checkSafety(showErrors: boolean) {
    if (!draft.name.trim()) {
      return null;
    }
    try {
      const result = await apiFetch<StyleGuardResult>("/style/guard", {
        method: "POST",
        body: JSON.stringify(draft)
      });
      setSafety(result);
      return result;
    } catch (guardError) {
      if (showErrors) {
        setError(guardError instanceof Error ? guardError.message : "Unable to check style safety");
      }
      return null;
    }
  }

  async function saveStyle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.name.trim()) {
      setError("Style bible name is required");
      return;
    }
    setIsBusy(true);
    setError(null);
    try {
      await checkSafety(false);
      const saved = selectedId
        ? await apiFetch<StyleBibleLab>(`/style-bibles/${selectedId}`, {
            method: "PUT",
            body: JSON.stringify(draft)
          })
        : await apiFetch<StyleBibleLab>(`/projects/${projectId}/style-bibles`, {
            method: "POST",
            body: JSON.stringify(draft)
          });
      setStyles((current) => {
        const exists = current.some((style) => style.id === saved.id);
        return exists ? current.map((style) => (style.id === saved.id ? saved : style)) : [saved, ...current];
      });
      selectStyle(saved);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to save style bible");
    } finally {
      setIsBusy(false);
    }
  }

  async function generateStyleOptions() {
    setIsGenerating(true);
    setError(null);
    try {
      const result = await apiFetch<StyleDNAOptionsResult>(`/projects/${projectId}/style/generate-dna`, {
        method: "POST",
        body: JSON.stringify({
          genre: generatorDraft.genre,
          tone: generatorDraft.tone,
          audience: generatorDraft.audience,
          visual_keywords: lines(generatorDraft.visual_keywords),
          avoid_keywords: lines(generatorDraft.avoid_keywords),
          sample_story_summary: generatorDraft.sample_story_summary
        })
      });
      setDnaOptions(result.options);
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : "Unable to generate style options");
    } finally {
      setIsGenerating(false);
    }
  }

  function useStyleOption(option: StyleDNAOption) {
    setDraft(optionToDraft(option));
    setSelectedId(null);
    setPreview(null);
  }

  async function setActiveStyle() {
    if (!selectedStyle) {
      return;
    }
    setError(null);
    const active = await apiFetch<StyleBibleLab>(`/projects/${projectId}/active-style`, {
      method: "PUT",
      body: JSON.stringify({ style_bible_id: selectedStyle.id })
    });
    setProject((current) => (current ? { ...current, active_style_bible_id: active.id } : current));
  }

  async function generatePreview() {
    if (!selectedStyle) {
      setError("Save or select a style bible first");
      return;
    }
    setIsPreviewing(true);
    setError(null);
    try {
      const result = await apiFetch<StylePreviewResult>(`/style-bibles/${selectedStyle.id}/mock-preview-panel`, {
        method: "POST",
        body: JSON.stringify({})
      });
      setPreview(result);
    } catch (previewError) {
      setError(previewError instanceof Error ? previewError.message : "Unable to generate preview");
    } finally {
      setIsPreviewing(false);
    }
  }

  async function addSampleMetadata() {
    if (!selectedStyle) {
      setError("Save or select a style bible first");
      return;
    }
    setError(null);
    const asset = await apiFetch<StyleSampleAsset>(`/style-bibles/${selectedStyle.id}/sample-assets`, {
      method: "POST",
      body: JSON.stringify({
        filename: sampleFilename,
        content_type: "image/png",
        size_bytes: 0,
        metadata_json: { source: "metadata-only" }
      })
    });
    setSamples((current) => [...current, asset]);
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
                <h1 className="text-3xl font-semibold tracking-normal">Style Lab</h1>
                <Badge>{project?.name || "Project"}</Badge>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">Original style DNA, safety guard, and reusable manga style rules</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void loadLab()}>
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </Button>
            <Button onClick={startNew}>
              <Brush className="h-4 w-4" />
              New Style
            </Button>
          </div>
        </header>

        {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div> : null}
        {safety && safety.severity !== "safe" ? <SafetyPanel safety={safety} /> : null}

        <section className="grid gap-4 md:grid-cols-4">
          <StyleMetric label="Saved Styles" value={styles.length} />
          <StyleMetric label="Generated Options" value={dnaOptions.length} />
          <StyleMetric label="Active Style" value={project?.active_style_bible_id ? "Selected" : "None"} />
          <StyleMetric label="Safety" value={safety?.severity ?? "unchecked"} />
        </section>

        <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)_360px]">
          <aside className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Style Options</CardTitle>
                <CardDescription>Generate and compare originals</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <TextField label="Genre" value={generatorDraft.genre} onChange={(genre) => setGeneratorDraft((current) => ({ ...current, genre }))} compact />
                <TextField label="Tone" value={generatorDraft.tone} onChange={(tone) => setGeneratorDraft((current) => ({ ...current, tone }))} compact />
                <TextField label="Audience" value={generatorDraft.audience} onChange={(audience) => setGeneratorDraft((current) => ({ ...current, audience }))} compact />
                <ListTextField
                  label="Visual Keywords"
                  value={generatorDraft.visual_keywords}
                  onChange={(visual_keywords) => setGeneratorDraft((current) => ({ ...current, visual_keywords }))}
                />
                <ListTextField
                  label="Avoid Keywords"
                  value={generatorDraft.avoid_keywords}
                  onChange={(avoid_keywords) => setGeneratorDraft((current) => ({ ...current, avoid_keywords }))}
                />
                <LongTextField
                  label="Story Summary"
                  value={generatorDraft.sample_story_summary}
                  onChange={(sample_story_summary) => setGeneratorDraft((current) => ({ ...current, sample_story_summary }))}
                />
                <Button onClick={() => void generateStyleOptions()} disabled={isGenerating}>
                  <Sparkles className="h-4 w-4" />
                  {isGenerating ? "Generating" : "Generate Style Options"}
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Saved</CardTitle>
                <CardDescription>{styles.length} style bibles</CardDescription>
              </CardHeader>
              <CardContent className="flex max-h-[420px] flex-col gap-2 overflow-auto">
                {styles.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No style bibles</p>
                ) : (
                  styles.map((style) => (
                    <button
                      type="button"
                      key={style.id}
                      onClick={() => selectStyle(style)}
                      className={`rounded-md border bg-white px-3 py-3 text-left text-sm transition-colors hover:border-primary/60 ${
                        selectedId === style.id ? "border-primary bg-primary/5" : ""
                      }`}
                    >
                      <span className="block font-medium">{style.style_name || style.name}</span>
                      <span className="text-xs text-muted-foreground">
                        {project?.active_style_bible_id === style.id ? "Active" : "Available"}
                      </span>
                    </button>
                  ))
                )}
              </CardContent>
            </Card>
          </aside>

          <section className="flex min-w-0 flex-col gap-6">
            {dnaOptions.length > 0 ? (
              <div className="grid gap-4 xl:grid-cols-3">
                {dnaOptions.map((option) => (
                  <StyleOptionCard key={option.style_name} option={option} onUse={() => useStyleOption(option)} />
                ))}
              </div>
            ) : null}

            <Card>
              <CardHeader>
                <CardTitle>{selectedId ? "Edit Style DNA" : "Create Style DNA"}</CardTitle>
                <CardDescription>Original visual grammar for render prompts</CardDescription>
              </CardHeader>
              <CardContent>
                <form className="grid gap-4 md:grid-cols-2" onSubmit={saveStyle}>
                  <TextField label="Saved Name" value={draft.name} onChange={(name) => setDraft((current) => ({ ...current, name }))} />
                  <TextField label="Style Name" value={draft.style_name} onChange={(style_name) => setDraft((current) => ({ ...current, style_name }))} />
                  <LongField label="Style Intent" value={draft.style_intent} onChange={(style_intent) => setDraft((current) => ({ ...current, style_intent }))} wide />

                  <SectionLabel label="Line And Shape" />
                  <LongField label="Line Weight" value={draft.line_weight} onChange={(line_weight) => setDraft((current) => ({ ...current, line_weight }))} />
                  <LongField label="Line Variation" value={draft.line_variation} onChange={(line_variation) => setDraft((current) => ({ ...current, line_variation }))} />
                  <LongField label="Line Texture" value={draft.line_texture} onChange={(line_texture) => setDraft((current) => ({ ...current, line_texture }))} />
                  <LongField label="Face Shape Language" value={draft.face_shape_language} onChange={(face_shape_language) => setDraft((current) => ({ ...current, face_shape_language }))} />
                  <LongField label="Eye Design Language" value={draft.eye_design_language} onChange={(eye_design_language) => setDraft((current) => ({ ...current, eye_design_language }))} />
                  <LongField
                    label="Nose / Mouth Simplification"
                    value={draft.nose_mouth_simplification}
                    onChange={(nose_mouth_simplification) => setDraft((current) => ({ ...current, nose_mouth_simplification }))}
                  />
                  <LongField label="Anatomy Proportions" value={draft.anatomy_proportions} onChange={(anatomy_proportions) => setDraft((current) => ({ ...current, anatomy_proportions }))} />
                  <LongField label="Hair Rendering" value={draft.hair_rendering} onChange={(hair_rendering) => setDraft((current) => ({ ...current, hair_rendering }))} />
                  <LongField label="Clothing Fold Style" value={draft.clothing_fold_style} onChange={(clothing_fold_style) => setDraft((current) => ({ ...current, clothing_fold_style }))} />

                  <SectionLabel label="Page Texture" />
                  <LongField label="Background Density" value={draft.background_density} onChange={(background_density) => setDraft((current) => ({ ...current, background_density }))} />
                  <LongField label="Architecture Detail" value={draft.architecture_detail} onChange={(architecture_detail) => setDraft((current) => ({ ...current, architecture_detail }))} />
                  <LongField label="Shadow Strategy" value={draft.shadow_strategy} onChange={(shadow_strategy) => setDraft((current) => ({ ...current, shadow_strategy }))} />
                  <LongField label="Screentone Strategy" value={draft.screentone_strategy} onChange={(screentone_strategy) => setDraft((current) => ({ ...current, screentone_strategy }))} />
                  <LongField label="Hatching Strategy" value={draft.hatching_strategy} onChange={(hatching_strategy) => setDraft((current) => ({ ...current, hatching_strategy }))} />
                  <LongField label="Black Fill Ratio" value={draft.black_fill_ratio} onChange={(black_fill_ratio) => setDraft((current) => ({ ...current, black_fill_ratio }))} />

                  <SectionLabel label="Motion And Lettering" />
                  <LongField label="Speedline Style" value={draft.speedline_style} onChange={(speedline_style) => setDraft((current) => ({ ...current, speedline_style }))} />
                  <LongField label="Impact Frame Style" value={draft.impact_frame_style} onChange={(impact_frame_style) => setDraft((current) => ({ ...current, impact_frame_style }))} />
                  <LongField label="Panel Border Style" value={draft.panel_border_style} onChange={(panel_border_style) => setDraft((current) => ({ ...current, panel_border_style }))} />
                  <LongField label="Gutter Style" value={draft.gutter_style} onChange={(gutter_style) => setDraft((current) => ({ ...current, gutter_style }))} />
                  <LongField label="SFX Shape Language" value={draft.sfx_shape_language} onChange={(sfx_shape_language) => setDraft((current) => ({ ...current, sfx_shape_language }))} />
                  <LongField label="Bubble Style" value={draft.bubble_style} onChange={(bubble_style) => setDraft((current) => ({ ...current, bubble_style }))} />
                  <LongField label="Typography Notes" value={draft.typography_notes} onChange={(typography_notes) => setDraft((current) => ({ ...current, typography_notes }))} />

                  <SectionLabel label="Prompt Fragments And Safety" />
                  <ListField
                    label="Emotional Visual Rules"
                    value={draft.emotional_visual_rules}
                    onChange={(emotional_visual_rules) => setDraft((current) => ({ ...current, emotional_visual_rules }))}
                  />
                  <ListField
                    label="Positive Prompt Fragments"
                    value={draft.positive_prompt_fragments}
                    onChange={(positive_prompt_fragments) => setDraft((current) => ({ ...current, positive_prompt_fragments }))}
                  />
                  <ListField
                    label="Negative Prompt Fragments"
                    value={draft.negative_prompt_fragments}
                    onChange={(negative_prompt_fragments) => setDraft((current) => ({ ...current, negative_prompt_fragments }))}
                  />
                  <ListField
                    label="Forbidden Artist References"
                    value={draft.forbidden_artist_references}
                    onChange={(forbidden_artist_references) => setDraft((current) => ({ ...current, forbidden_artist_references }))}
                  />
                  <ListField
                    label="Forbidden Franchise References"
                    value={draft.forbidden_franchise_references}
                    onChange={(forbidden_franchise_references) => setDraft((current) => ({ ...current, forbidden_franchise_references }))}
                  />

                  <SectionLabel label="Legacy Compatibility" />
                  <LongField label="Linework" value={draft.linework} onChange={(linework) => setDraft((current) => ({ ...current, linework }))} />
                  <LongField label="Screentone" value={draft.screentone} onChange={(screentone) => setDraft((current) => ({ ...current, screentone }))} />
                  <LongField label="Hatching" value={draft.hatching} onChange={(hatching) => setDraft((current) => ({ ...current, hatching }))} />
                  <LongField label="Black / White Balance" value={draft.black_white_balance} onChange={(black_white_balance) => setDraft((current) => ({ ...current, black_white_balance }))} />
                  <LongField label="Face Language" value={draft.face_language} onChange={(face_language) => setDraft((current) => ({ ...current, face_language }))} />
                  <LongField label="Anatomy Style" value={draft.anatomy_style} onChange={(anatomy_style) => setDraft((current) => ({ ...current, anatomy_style }))} />
                  <LongField label="Background Detail" value={draft.background_detail} onChange={(background_detail) => setDraft((current) => ({ ...current, background_detail }))} />
                  <LongField label="Panel Rhythm" value={draft.panel_rhythm} onChange={(panel_rhythm) => setDraft((current) => ({ ...current, panel_rhythm }))} />
                  <LongField label="SFX Style" value={draft.sfx_style} onChange={(sfx_style) => setDraft((current) => ({ ...current, sfx_style }))} />
                  <ListField label="Forbidden References" value={draft.forbidden_references} onChange={(forbidden_references) => setDraft((current) => ({ ...current, forbidden_references }))} />
                  <LongField label="Positive Prompt Style" value={draft.prompt_style_positive} onChange={(prompt_style_positive) => setDraft((current) => ({ ...current, prompt_style_positive }))} />
                  <LongField label="Negative Prompt Style" value={draft.prompt_style_negative} onChange={(prompt_style_negative) => setDraft((current) => ({ ...current, prompt_style_negative }))} />

                  <div className="flex flex-wrap gap-2 md:col-span-2">
                    <Button type="submit" disabled={isBusy || safety?.severity === "blocked"}>
                      <Save className="h-4 w-4" />
                      {isBusy ? "Saving" : "Save Style"}
                    </Button>
                    <Button type="button" variant="outline" onClick={() => void setActiveStyle()} disabled={!selectedStyle}>
                      <Check className="h-4 w-4" />
                      Set Active
                    </Button>
                    <Button type="button" variant="outline" onClick={() => void checkSafety(true)}>
                      <AlertTriangle className="h-4 w-4" />
                      Check Safety
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </section>

          <aside className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Preview</CardTitle>
                <CardDescription>{selectedStyle ? selectedStyle.style_name || selectedStyle.name : "Save a style first"}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <Button onClick={() => void generatePreview()} disabled={!selectedStyle || isPreviewing}>
                  <ImageIcon className="h-4 w-4" />
                  {isPreviewing ? "Generating" : "Generate Mock Preview"}
                </Button>
                {preview?.public_url ? (
                  <>
                    <img src={preview.public_url} alt="Mock style preview panel" className="rounded-md border bg-white object-contain" />
                    <p className="text-xs text-muted-foreground">{preview.preview_prompt}</p>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">Preview creates a deterministic placeholder panel using the saved StyleDNA.</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Safety</CardTitle>
                <CardDescription>{safety ? safety.severity : "Not checked"}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {safety ? (
                  <>
                    <Badge className={safety.severity === "blocked" ? "border-destructive/40 text-destructive" : ""}>
                      {safety.severity}
                    </Badge>
                    {safety.issues.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No style imitation risks detected.</p>
                    ) : (
                      safety.issues.map((issue) => (
                        <div key={`${issue.code}-${issue.field}-${issue.matched_text}`} className="rounded-md border bg-white p-3 text-sm">
                          <p className="font-medium">{issue.code.replaceAll("_", " ")}</p>
                          <p className="mt-1 text-xs text-muted-foreground">{issue.message}</p>
                          {issue.field ? <p className="mt-1 text-xs text-muted-foreground">{issue.field}</p> : null}
                        </div>
                      ))
                    )}
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">Style safety is checked automatically while editing.</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Samples</CardTitle>
                <CardDescription>Metadata only</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <Input value={sampleFilename} onChange={(event) => setSampleFilename(event.target.value)} />
                <Button variant="outline" onClick={() => void addSampleMetadata()} disabled={!selectedStyle}>
                  Register Sample
                </Button>
                <div className="flex max-h-[280px] flex-col gap-2 overflow-auto">
                  {samples.map((asset) => (
                    <div key={asset.id} className="rounded-md border bg-white p-3">
                      <p className="truncate text-sm font-medium">{asset.filename}</p>
                      <p className="truncate text-xs text-muted-foreground">{asset.storage_key}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </aside>
        </div>
      </div>
    </main>
  );
}

function optionToDraft(option: StyleDNAOption): StyleDraft {
  return {
    ...emptyDraft,
    name: option.style_name,
    style_name: option.style_name,
    style_intent: option.style_intent,
    line_weight: option.line_weight,
    line_variation: option.line_variation,
    line_texture: option.line_texture,
    face_shape_language: option.face_shape_language,
    eye_design_language: option.eye_design_language,
    nose_mouth_simplification: option.nose_mouth_simplification,
    anatomy_proportions: option.anatomy_proportions,
    hair_rendering: option.hair_rendering,
    clothing_fold_style: option.clothing_fold_style,
    background_density: option.background_density,
    architecture_detail: option.architecture_detail,
    shadow_strategy: option.shadow_strategy,
    screentone_strategy: option.screentone_strategy,
    hatching_strategy: option.hatching_strategy,
    black_fill_ratio: option.black_fill_ratio,
    speedline_style: option.speedline_style,
    impact_frame_style: option.impact_frame_style,
    panel_border_style: option.panel_border_style,
    gutter_style: option.gutter_style,
    sfx_shape_language: option.sfx_shape_language,
    bubble_style: option.bubble_style,
    typography_notes: option.typography_notes,
    emotional_visual_rules: option.emotional_visual_rules,
    positive_prompt_fragments: option.positive_prompt_fragments,
    negative_prompt_fragments: option.negative_prompt_fragments,
    forbidden_artist_references: option.forbidden_artist_references,
    forbidden_franchise_references: option.forbidden_franchise_references,
    linework: [option.line_weight, option.line_variation, option.line_texture].filter(Boolean).join(" "),
    screentone: option.screentone_strategy,
    hatching: option.hatching_strategy,
    black_white_balance: [option.shadow_strategy, option.black_fill_ratio].filter(Boolean).join(" "),
    face_language: [option.face_shape_language, option.eye_design_language, option.nose_mouth_simplification].filter(Boolean).join(" "),
    anatomy_style: option.anatomy_proportions,
    background_detail: [option.background_density, option.architecture_detail].filter(Boolean).join(" "),
    panel_rhythm: [option.speedline_style, option.impact_frame_style, option.panel_border_style, option.gutter_style].filter(Boolean).join(" "),
    sfx_style: option.sfx_shape_language,
    forbidden_references: [...option.forbidden_artist_references, ...option.forbidden_franchise_references],
    prompt_style_positive: option.positive_prompt_fragments.join(", "),
    prompt_style_negative: option.negative_prompt_fragments.join(", ")
  };
}

function toDraft(style: StyleBibleLab): StyleDraft {
  const { id, project_id, story_bible_id, created_at, updated_at, ...draft } = style;
  return draft;
}

function StyleOptionCard({ option, onUse }: { option: StyleDNAOption; onUse: () => void }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{option.style_name}</CardTitle>
        <CardDescription>{option.black_fill_ratio || "Original StyleDNA"}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        <p className="text-muted-foreground">{option.style_intent}</p>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <MiniSpec label="Line" value={option.line_weight} />
          <MiniSpec label="Eyes" value={option.eye_design_language} />
          <MiniSpec label="Tone" value={option.screentone_strategy} />
          <MiniSpec label="Panels" value={option.gutter_style} />
        </div>
        <p className="rounded-md bg-muted/40 p-2 text-xs text-muted-foreground">{option.preview_prompt}</p>
        <Button variant="outline" onClick={onUse}>
          Use As Draft
        </Button>
      </CardContent>
    </Card>
  );
}

function MiniSpec({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-white px-2 py-2">
      <span className="block font-medium">{label}</span>
      <span className="line-clamp-3 text-muted-foreground">{value || "Not set"}</span>
    </div>
  );
}

function SafetyPanel({ safety }: { safety: StyleGuardResult }) {
  return (
    <div className={`rounded-md border px-4 py-3 text-sm ${safety.severity === "blocked" ? "border-destructive/30 bg-destructive/10 text-destructive" : "border-amber-300 bg-amber-50 text-amber-900"}`}>
      <div className="flex items-center gap-2 font-medium">
        <AlertTriangle className="h-4 w-4" />
        Style safety {safety.severity}
      </div>
      <p className="mt-1">{safety.issues[0]?.message || "Review originality warnings before saving."}</p>
    </div>
  );
}

function StyleMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">{label}</p>
      <p className="mt-2 truncate text-xl font-semibold">{value}</p>
    </div>
  );
}

function SectionLabel({ label }: { label: string }) {
  return (
    <div className="border-t pt-4 md:col-span-2">
      <h3 className="text-sm font-semibold">{label}</h3>
    </div>
  );
}

function TextField({ label, value, onChange, compact = false }: { label: string; value: string; onChange: (value: string) => void; compact?: boolean }) {
  return (
    <label className={`flex flex-col gap-2 text-sm font-medium ${compact ? "" : "md:col-span-2"}`}>
      {label}
      <Input value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function LongField({ label, value, onChange, wide = false }: { label: string; value: string; onChange: (value: string) => void; wide?: boolean }) {
  return (
    <label className={`flex flex-col gap-2 text-sm font-medium ${wide ? "md:col-span-2" : ""}`}>
      {label}
      <Textarea value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function LongTextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="flex flex-col gap-2 text-sm font-medium">
      {label}
      <Textarea value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function ListTextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="flex flex-col gap-2 text-sm font-medium">
      {label}
      <Textarea value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function ListField({ label, value, onChange }: { label: string; value: string[]; onChange: (value: string[]) => void }) {
  return (
    <label className="flex flex-col gap-2 text-sm font-medium">
      {label}
      <Textarea value={value.join("\n")} onChange={(event) => onChange(lines(event.target.value))} />
    </label>
  );
}

function lines(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}
