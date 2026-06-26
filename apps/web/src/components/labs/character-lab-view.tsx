"use client";

import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Images, RefreshCcw, Save, Sparkles, UserPlus } from "lucide-react";
import type { CharacterCard, CharacterReferenceAsset, CharacterState, GenerateCharacterSheetResult, ProjectDetail } from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LearningFeedbackControls } from "@/components/learning/learning-feedback-controls";
import { Textarea } from "@/components/ui/textarea";

type CharacterDraft = Omit<CharacterCard, "id" | "project_id" | "created_at" | "updated_at">;

const emptyDraft: CharacterDraft = {
  name: "",
  aliases: [],
  age_range: "",
  role: "",
  personality: "",
  face_description: "",
  hair_description: "",
  eye_description: "",
  body_type: "",
  outfit_default: "",
  accessories: [],
  scars_marks: "",
  voice_style: "",
  forbidden_changes: [],
  continuity_rules: [],
  canonical_visual_summary: "",
  silhouette_keywords: [],
  face_anchor_description: "",
  hair_anchor_description: "",
  eye_anchor_description: "",
  body_anchor_description: "",
  outfit_anchor_description: "",
  color_notes_even_for_bw: "",
  recurring_props: [],
  allowed_variations: [],
  forbidden_variations: [],
  current_story_state: "",
  injury_state: "",
  emotional_baseline: "",
  reference_asset_ids: [],
  approved_panel_asset_ids: []
};

export function CharacterLabView({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [characters, setCharacters] = useState<CharacterCard[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<CharacterDraft>(emptyDraft);
  const [referenceFilename, setReferenceFilename] = useState("reference.png");
  const [references, setReferences] = useState<CharacterReferenceAsset[]>([]);
  const [characterStates, setCharacterStates] = useState<CharacterState[]>([]);
  const [sheetResult, setSheetResult] = useState<GenerateCharacterSheetResult | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadLab() {
    setError(null);
    try {
      const [nextProject, nextCharacters] = await Promise.all([
        apiFetch<ProjectDetail>(`/projects/${projectId}`),
        apiFetch<CharacterCard[]>(`/projects/${projectId}/characters`)
      ]);
      setProject(nextProject);
      setCharacters(nextCharacters);
      const selected = selectedId ? nextCharacters.find((card) => card.id === selectedId) : nextCharacters[0];
      if (selected) {
        selectCharacter(selected);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load Character Lab");
    }
  }

  useEffect(() => {
    void loadLab();
  }, [projectId]);

  const selectedCharacter = useMemo(() => {
    return characters.find((character) => character.id === selectedId) ?? null;
  }, [characters, selectedId]);

  function selectCharacter(character: CharacterCard) {
    setSelectedId(character.id);
    setDraft(toDraft(character));
    setReferences([]);
    setCharacterStates([]);
    setSheetResult(null);
    void loadCharacterDetails(character.id);
  }

  function startNew() {
    setSelectedId(null);
    setDraft({ ...emptyDraft, name: "New Character" });
    setReferences([]);
    setCharacterStates([]);
    setSheetResult(null);
  }

  async function loadCharacterDetails(characterId: string) {
    try {
      const [nextReferences, nextStates] = await Promise.all([
        apiFetch<CharacterReferenceAsset[]>(`/characters/${characterId}/reference-assets`),
        apiFetch<CharacterState[]>(`/characters/${characterId}/states`)
      ]);
      setReferences(nextReferences);
      setCharacterStates(nextStates);
    } catch (detailsError) {
      setError(detailsError instanceof Error ? detailsError.message : "Unable to load character continuity details");
    }
  }

  async function saveCharacter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.name.trim()) {
      setError("Character name is required");
      return;
    }
    setIsBusy(true);
    setError(null);
    try {
      const saved = selectedId
        ? await apiFetch<CharacterCard>(`/characters/${selectedId}`, {
            method: "PUT",
            body: JSON.stringify(draft)
          })
        : await apiFetch<CharacterCard>(`/projects/${projectId}/characters`, {
            method: "POST",
            body: JSON.stringify(draft)
          });
      setCharacters((current) => {
        const exists = current.some((character) => character.id === saved.id);
        return exists ? current.map((character) => (character.id === saved.id ? saved : character)) : [...current, saved];
      });
      selectCharacter(saved);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to save character");
    } finally {
      setIsBusy(false);
    }
  }

  async function addReferenceMetadata() {
    if (!selectedCharacter) {
      setError("Save or select a character first");
      return;
    }
    setError(null);
    const asset = await apiFetch<CharacterReferenceAsset>(`/characters/${selectedCharacter.id}/reference-assets`, {
      method: "POST",
      body: JSON.stringify({
        filename: referenceFilename,
        content_type: "image/png",
        size_bytes: 0,
        metadata_json: { source: "metadata-only" }
      })
    });
    setReferences((current) => [...current, asset]);
  }

  async function generateCharacterSheet() {
    if (!selectedCharacter) {
      setError("Save or select a character first");
      return;
    }
    setIsBusy(true);
    setError(null);
    try {
      const result = await apiFetch<GenerateCharacterSheetResult>(`/characters/${selectedCharacter.id}/generate-character-sheet`, {
        method: "POST"
      });
      setSheetResult(result);
      setReferences((current) => [...current, ...result.assets]);
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : "Unable to generate character sheet");
    } finally {
      setIsBusy(false);
    }
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
                <h1 className="text-3xl font-semibold tracking-normal">Character Lab</h1>
                <Badge>{project?.name || "Project"}</Badge>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">Character continuity cards and reference metadata</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void loadLab()}>
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </Button>
            <Button onClick={startNew}>
              <UserPlus className="h-4 w-4" />
              New Character
            </Button>
          </div>
        </header>

        {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div> : null}

        <section className="grid gap-4 md:grid-cols-3">
          <LabMetric label="Characters" value={characters.length} />
          <LabMetric label="References" value={references.length} />
          <LabMetric label="Continuity States" value={characterStates.length} />
        </section>

        <Card>
          <CardHeader>
            <CardTitle>Character Cards</CardTitle>
            <CardDescription>Cast grid for fast visual scanning</CardDescription>
          </CardHeader>
          <CardContent>
            {characters.length === 0 ? (
              <div className="rounded-md border bg-muted/30 px-4 py-8 text-center text-sm text-muted-foreground">No characters yet. Create the first card to establish identity anchors.</div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {characters.map((character) => (
                  <button
                    key={character.id}
                    type="button"
                    onClick={() => selectCharacter(character)}
                    className={`rounded-md border bg-white p-4 text-left transition-colors hover:border-primary/60 ${
                      selectedId === character.id ? "border-primary bg-primary/5" : ""
                    }`}
                  >
                    <div className="flex aspect-[4/3] items-center justify-center rounded-md border bg-[linear-gradient(135deg,#fffdf7,#eee7db)] text-3xl font-semibold">
                      {character.name.slice(0, 1).toUpperCase()}
                    </div>
                    <h3 className="mt-3 truncate font-semibold">{character.name}</h3>
                    <p className="mt-1 text-xs text-muted-foreground">{character.role || "Role not set"}</p>
                    <div className="mt-3 flex flex-wrap gap-1">
                      {character.silhouette_keywords.slice(0, 3).map((keyword) => <Badge key={keyword}>{keyword}</Badge>)}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)_340px]">
          <aside className="flex flex-col gap-3">
            {characters.length === 0 ? (
              <div className="rounded-md border bg-white px-4 py-6 text-sm text-muted-foreground">No character cards</div>
            ) : (
              characters.map((character) => (
                <button
                  type="button"
                  key={character.id}
                  onClick={() => selectCharacter(character)}
                  className={`rounded-md border bg-white px-3 py-3 text-left text-sm transition-colors hover:border-primary/60 ${
                    selectedId === character.id ? "border-primary bg-primary/5" : ""
                  }`}
                >
                  <span className="block font-medium">{character.name}</span>
                  <span className="text-xs text-muted-foreground">{character.role || "Unassigned role"}</span>
                </button>
              ))
            )}
          </aside>

          <Card>
            <CardHeader>
              <CardTitle>{selectedId ? "Edit Character Card" : "Create Character Card"}</CardTitle>
              <CardDescription>Continuity rules for generation prompts</CardDescription>
            </CardHeader>
            <CardContent>
              {selectedCharacter ? (
                <div className="mb-4">
                  <LearningFeedbackControls projectId={projectId} targetType="character" targetId={selectedCharacter.id} compact />
                </div>
              ) : null}
              <form className="grid gap-4 md:grid-cols-2" onSubmit={saveCharacter}>
                <TextField label="Name" value={draft.name} onChange={(name) => setDraft((current) => ({ ...current, name }))} />
                <TextField label="Role" value={draft.role} onChange={(role) => setDraft((current) => ({ ...current, role }))} />
                <TextField label="Age Range" value={draft.age_range} onChange={(age_range) => setDraft((current) => ({ ...current, age_range }))} />
                <TextField label="Voice Style" value={draft.voice_style} onChange={(voice_style) => setDraft((current) => ({ ...current, voice_style }))} />
                <ListField label="Aliases" value={draft.aliases} onChange={(aliases) => setDraft((current) => ({ ...current, aliases }))} />
                <ListField label="Accessories" value={draft.accessories} onChange={(accessories) => setDraft((current) => ({ ...current, accessories }))} />
                <LongField label="Personality" value={draft.personality} onChange={(personality) => setDraft((current) => ({ ...current, personality }))} />
                <LongField label="Face" value={draft.face_description} onChange={(face_description) => setDraft((current) => ({ ...current, face_description }))} />
                <LongField label="Hair" value={draft.hair_description} onChange={(hair_description) => setDraft((current) => ({ ...current, hair_description }))} />
                <LongField label="Eyes" value={draft.eye_description} onChange={(eye_description) => setDraft((current) => ({ ...current, eye_description }))} />
                <LongField label="Body Type" value={draft.body_type} onChange={(body_type) => setDraft((current) => ({ ...current, body_type }))} />
                <LongField label="Default Outfit" value={draft.outfit_default} onChange={(outfit_default) => setDraft((current) => ({ ...current, outfit_default }))} />
                <LongField label="Scars / Marks" value={draft.scars_marks} onChange={(scars_marks) => setDraft((current) => ({ ...current, scars_marks }))} />
                <div className="md:col-span-2 border-t pt-4">
                  <h3 className="text-sm font-semibold">Canonical Profile</h3>
                  <p className="mt-1 text-xs text-muted-foreground">Identity anchors used by panel prompts and consistency QA</p>
                </div>
                <LongField
                  label="Canonical Visual Summary"
                  value={draft.canonical_visual_summary}
                  onChange={(canonical_visual_summary) => setDraft((current) => ({ ...current, canonical_visual_summary }))}
                />
                <ListField
                  label="Silhouette Keywords"
                  value={draft.silhouette_keywords}
                  onChange={(silhouette_keywords) => setDraft((current) => ({ ...current, silhouette_keywords }))}
                />
                <LongField
                  label="Face Anchor"
                  value={draft.face_anchor_description}
                  onChange={(face_anchor_description) => setDraft((current) => ({ ...current, face_anchor_description }))}
                />
                <LongField
                  label="Hair Anchor"
                  value={draft.hair_anchor_description}
                  onChange={(hair_anchor_description) => setDraft((current) => ({ ...current, hair_anchor_description }))}
                />
                <LongField
                  label="Eye Anchor"
                  value={draft.eye_anchor_description}
                  onChange={(eye_anchor_description) => setDraft((current) => ({ ...current, eye_anchor_description }))}
                />
                <LongField
                  label="Body Anchor"
                  value={draft.body_anchor_description}
                  onChange={(body_anchor_description) => setDraft((current) => ({ ...current, body_anchor_description }))}
                />
                <LongField
                  label="Outfit Anchor"
                  value={draft.outfit_anchor_description}
                  onChange={(outfit_anchor_description) => setDraft((current) => ({ ...current, outfit_anchor_description }))}
                />
                <LongField
                  label="Color Notes Even For BW"
                  value={draft.color_notes_even_for_bw}
                  onChange={(color_notes_even_for_bw) => setDraft((current) => ({ ...current, color_notes_even_for_bw }))}
                />
                <ListField
                  label="Recurring Props"
                  value={draft.recurring_props}
                  onChange={(recurring_props) => setDraft((current) => ({ ...current, recurring_props }))}
                />
                <ListField
                  label="Allowed Variations"
                  value={draft.allowed_variations}
                  onChange={(allowed_variations) => setDraft((current) => ({ ...current, allowed_variations }))}
                />
                <ListField
                  label="Forbidden Variations"
                  value={draft.forbidden_variations}
                  onChange={(forbidden_variations) => setDraft((current) => ({ ...current, forbidden_variations }))}
                />
                <LongField
                  label="Current Story State"
                  value={draft.current_story_state}
                  onChange={(current_story_state) => setDraft((current) => ({ ...current, current_story_state }))}
                />
                <LongField label="Injury State" value={draft.injury_state} onChange={(injury_state) => setDraft((current) => ({ ...current, injury_state }))} />
                <LongField
                  label="Emotional Baseline"
                  value={draft.emotional_baseline}
                  onChange={(emotional_baseline) => setDraft((current) => ({ ...current, emotional_baseline }))}
                />
                <ListField label="Forbidden Changes" value={draft.forbidden_changes} onChange={(forbidden_changes) => setDraft((current) => ({ ...current, forbidden_changes }))} />
                <ListField label="Continuity Rules" value={draft.continuity_rules} onChange={(continuity_rules) => setDraft((current) => ({ ...current, continuity_rules }))} />
                <ListField
                  label="Reference Asset IDs"
                  value={draft.reference_asset_ids}
                  onChange={(reference_asset_ids) => setDraft((current) => ({ ...current, reference_asset_ids }))}
                />
                <ListField
                  label="Approved Panel Asset IDs"
                  value={draft.approved_panel_asset_ids}
                  onChange={(approved_panel_asset_ids) => setDraft((current) => ({ ...current, approved_panel_asset_ids }))}
                />
                <div className="md:col-span-2">
                  <Button type="submit" disabled={isBusy}>
                    <Save className="h-4 w-4" />
                    Save Character
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          <aside className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Images className="h-4 w-4" />
                  References
                </CardTitle>
                <CardDescription>Metadata only</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <Input value={referenceFilename} onChange={(event) => setReferenceFilename(event.target.value)} />
                <Button variant="outline" onClick={() => void addReferenceMetadata()} disabled={!selectedCharacter}>
                  Register Reference
                </Button>
                <Button onClick={() => void generateCharacterSheet()} disabled={!selectedCharacter || isBusy}>
                  <Sparkles className="h-4 w-4" />
                  Generate Character Sheet
                </Button>
                {sheetResult ? <Badge>{sheetResult.job.status} mock sheet</Badge> : null}
                {selectedCharacter ? (
                  <Button variant="ghost" onClick={() => void loadCharacterDetails(selectedCharacter.id)}>
                    <RefreshCcw className="h-4 w-4" />
                    Refresh Details
                  </Button>
                ) : null}
                <div className="grid max-h-[360px] grid-cols-2 gap-2 overflow-auto">
                  {references.map((asset) => (
                    <div key={asset.id} className="rounded-md border bg-white p-3">
                      <div className="mb-2 flex aspect-square items-center justify-center rounded-md border bg-muted text-xs text-muted-foreground">
                        REF
                      </div>
                      <p className="truncate text-sm font-medium">{asset.filename}</p>
                      <p className="truncate text-xs text-muted-foreground">{asset.storage_key}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Continuity</CardTitle>
                <CardDescription>Active states and locked constraints</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <div>
                  <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">Forbidden changes</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {draft.forbidden_changes.concat(draft.forbidden_variations).length === 0 ? (
                      <span className="text-sm text-muted-foreground">None yet</span>
                    ) : (
                      draft.forbidden_changes.concat(draft.forbidden_variations).map((item) => <Badge key={item}>{item}</Badge>)
                    )}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">Approved panels</p>
                  <div className="mt-2 grid max-h-32 grid-cols-2 gap-2 overflow-auto text-xs text-muted-foreground">
                    {draft.approved_panel_asset_ids.length === 0 ? <span>No approved panel assets</span> : draft.approved_panel_asset_ids.map((id) => (
                      <span key={id} className="rounded-md border bg-white p-2">
                        <span className="block aspect-square rounded-sm bg-muted" />
                        <span className="mt-1 block truncate">{id}</span>
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex max-h-[360px] flex-col gap-2 overflow-auto border-l pl-3">
                  {characterStates.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No chapter/scene states saved yet.</p>
                  ) : (
                    characterStates.map((state) => (
                      <div key={state.id} className="relative rounded-md border bg-white p-3 text-sm before:absolute before:-left-[19px] before:top-4 before:h-3 before:w-3 before:rounded-full before:border before:bg-primary">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">State {state.id.slice(0, 8)}</span>
                          <Badge>{state.page_id ? "page" : "scene"}</Badge>
                        </div>
                        <p className="mt-2 text-xs text-muted-foreground">Chapter {state.chapter_id.slice(0, 8)} - Scene {state.scene_id.slice(0, 8)}</p>
                        <p className="mt-2"><span className="font-medium">Outfit:</span> {state.outfit_state || "Not set"}</p>
                        <p><span className="font-medium">Injury:</span> {state.injury_state || "None"}</p>
                        <p><span className="font-medium">Emotion:</span> {state.emotional_state || "Not set"}</p>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </aside>
        </div>
      </div>
    </main>
  );
}

function toDraft(character: CharacterCard): CharacterDraft {
  const { id, project_id, created_at, updated_at, ...draft } = character;
  return draft;
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="flex flex-col gap-2 text-sm font-medium">
      {label}
      <Input value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function LongField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
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

function LabMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  );
}
