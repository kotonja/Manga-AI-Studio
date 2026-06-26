"use client";

import Link from "next/link";
import { ArrowLeft, Download, Plus, RefreshCcw, RotateCw, Save, Sparkles, Trash2, Type } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import type { Bubble, BubbleKind, CharacterCard, LetteringGenerateResult, LetteringPage, PageLayout, SFXElement } from "@manga-ai/shared";

import { apiFetch, getApiBaseUrl } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type Selection = { type: "bubble"; id: string } | { type: "sfx"; id: string } | null;
type DragState = {
  type: "bubble" | "sfx";
  id: string;
  mode: "move" | "resize";
  startX: number;
  startY: number;
  x: number;
  y: number;
  width: number;
  height: number;
};

export function LetteringRoomView({ projectId, pageId }: { projectId: string; pageId: string }) {
  const [layout, setLayout] = useState<PageLayout | null>(null);
  const [lettering, setLettering] = useState<LetteringPage | null>(null);
  const [characters, setCharacters] = useState<CharacterCard[]>([]);
  const [selection, setSelection] = useState<Selection>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dragRef = useRef<DragState | null>(null);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextLayout, nextLettering, nextCharacters] = await Promise.all([
        apiFetch<PageLayout>(`/pages/${pageId}/layout`),
        apiFetch<LetteringPage>(`/pages/${pageId}/lettering`),
        apiFetch<CharacterCard[]>(`/projects/${projectId}/characters`).catch(() => [])
      ]);
      setLayout(nextLayout);
      setLettering(nextLettering);
      setCharacters(nextCharacters);
      setSelection((current) => current ?? (nextLettering.bubbles[0] ? { type: "bubble", id: nextLettering.bubbles[0].id } : null));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load lettering room");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [pageId]);

  const selectedBubble = selection?.type === "bubble" ? lettering?.bubbles.find((bubble) => bubble.id === selection.id) ?? null : null;
  const selectedSfx = selection?.type === "sfx" ? lettering?.sfx.find((element) => element.id === selection.id) ?? null : null;
  const stageWidth = layout ? Math.min(820, layout.width) : 820;
  const scale = layout ? stageWidth / layout.width : 1;
  const stageHeight = layout ? layout.height * scale : 1000;
  const svgUrl = `${getApiBaseUrl()}/pages/${pageId}/lettering.svg`;
  const warnings = useMemo(() => {
    const local = lettering?.bubbles.flatMap((bubble) => {
      const warning = readabilityWarning(bubble);
      return warning ? [`${bubbleLabel(bubble)}: ${warning}`] : [];
    }) ?? [];
    return [...(lettering?.warnings ?? []), ...local];
  }, [lettering]);

  useEffect(() => {
    function onPointerMove(event: PointerEvent) {
      const drag = dragRef.current;
      if (!drag || !layout) {
        return;
      }
      const dx = (event.clientX - drag.startX) / scale;
      const dy = (event.clientY - drag.startY) / scale;
      if (drag.type === "bubble") {
        updateBubbleLocal(drag.id, (bubble) => {
          if (drag.mode === "resize") {
            const width = clamp(Math.round(drag.width + dx), 60, layout.width - bubble.x);
            const height = clamp(Math.round(drag.height + dy), 40, layout.height - bubble.y);
            return { ...bubble, width, height, size: { width, height } };
          }
          const x = clamp(Math.round(drag.x + dx), 0, layout.width - bubble.width);
          const y = clamp(Math.round(drag.y + dy), 0, layout.height - bubble.height);
          return { ...bubble, x, y, position: { x, y } };
        });
      } else {
        updateSfxLocal(drag.id, (element) => {
          const width = numberValue(element.size.width, drag.width);
          const height = numberValue(element.size.height, drag.height);
          if (drag.mode === "resize") {
            return {
              ...element,
              size: {
                width: clamp(Math.round(drag.width + dx), 40, layout.width),
                height: clamp(Math.round(drag.height + dy), 30, layout.height)
              }
            };
          }
          return {
            ...element,
            position: {
              x: clamp(Math.round(drag.x + dx), 0, layout.width - width),
              y: clamp(Math.round(drag.y + dy), 0, layout.height - height)
            }
          };
        });
      }
    }
    function onPointerUp() {
      const drag = dragRef.current;
      dragRef.current = null;
      if (!drag || !lettering) {
        return;
      }
      if (drag.type === "bubble") {
        const bubble = lettering.bubbles.find((item) => item.id === drag.id);
        if (bubble) {
          void persistBubble(bubble);
        }
      } else {
        const element = lettering.sfx.find((item) => item.id === drag.id);
        if (element) {
          void persistSfx(element);
        }
      }
    }
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };
  }, [layout, scale, lettering]);

  async function generateLettering() {
    setIsGenerating(true);
    setError(null);
    try {
      const result = await apiFetch<LetteringGenerateResult>(`/pages/${pageId}/lettering/generate`, { method: "POST" });
      setLettering(result);
      setSelection(result.bubbles[0] ? { type: "bubble", id: result.bubbles[0].id } : result.sfx[0] ? { type: "sfx", id: result.sfx[0].id } : null);
    } catch (generateError) {
      setError(generateError instanceof Error ? generateError.message : "Unable to generate lettering");
    } finally {
      setIsGenerating(false);
    }
  }

  async function addSfx() {
    if (!layout) {
      return;
    }
    try {
      const element = await apiFetch<SFXElement>(`/pages/${pageId}/sfx`, {
        method: "POST",
        body: JSON.stringify({
          text: "SFX!",
          meaning: "manual sound effect",
          position: { x: Math.round(layout.width * 0.38), y: Math.round(layout.height * 0.42) },
          size: { width: 320, height: 130 }
        })
      });
      setLettering((current) => (current ? { ...current, sfx: [...current.sfx, element] } : current));
      setSelection({ type: "sfx", id: element.id });
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Unable to add SFX");
    }
  }

  async function persistBubble(bubble: Bubble) {
    try {
      await apiFetch<Bubble>(`/bubbles/${bubble.id}`, {
        method: "PUT",
        body: JSON.stringify({
          kind: bubble.bubble_type,
          bubble_type: bubble.bubble_type,
          speaker_character_id: bubble.speaker_character_id,
          x: bubble.x,
          y: bubble.y,
          width: bubble.width,
          height: bubble.height,
          text: bubble.text,
          language: bubble.language,
          reading_direction: bubble.reading_direction,
          shape: bubble.shape,
          position: { x: bubble.x, y: bubble.y },
          size: { width: bubble.width, height: bubble.height },
          tail_target: bubble.tail_target,
          font_family: bubble.font_family,
          font_size: bubble.font_size,
          font_weight: bubble.font_weight,
          text_align: bubble.text_align,
          vertical_text: bubble.vertical_text,
          z_index: bubble.z_index,
          locked: bubble.locked
        })
      });
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to save bubble");
    }
  }

  async function persistSfx(element: SFXElement) {
    try {
      await apiFetch<SFXElement>(`/sfx/${element.id}`, {
        method: "PUT",
        body: JSON.stringify({
          panel_id: element.panel_id,
          text: element.text,
          meaning: element.meaning,
          style: element.style,
          position: element.position,
          size: element.size,
          rotation: element.rotation,
          warp_style: element.warp_style,
          stroke_width: element.stroke_width,
          fill: element.fill,
          outline: element.outline,
          z_index: element.z_index,
          locked: element.locked
        })
      });
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Unable to save SFX");
    }
  }

  async function deleteSelectedSfx() {
    if (!selectedSfx) {
      return;
    }
    try {
      await fetch(`${getApiBaseUrl()}/sfx/${selectedSfx.id}`, { method: "DELETE" });
      setLettering((current) => (current ? { ...current, sfx: current.sfx.filter((element) => element.id !== selectedSfx.id) } : current));
      setSelection(null);
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Unable to delete SFX");
    }
  }

  function updateBubbleLocal(id: string, updater: (bubble: Bubble) => Bubble) {
    setLettering((current) =>
      current ? { ...current, bubbles: current.bubbles.map((bubble) => (bubble.id === id ? updater(bubble) : bubble)) } : current
    );
  }

  function updateSfxLocal(id: string, updater: (element: SFXElement) => SFXElement) {
    setLettering((current) => (current ? { ...current, sfx: current.sfx.map((element) => (element.id === id ? updater(element) : element)) } : current));
  }

  if (isLoading && (!layout || !lettering)) {
    return <main className="min-h-screen px-4 py-6 text-sm text-muted-foreground">Loading Lettering Room</main>;
  }

  if (!layout || !lettering) {
    return <main className="min-h-screen px-4 py-6 text-sm text-destructive">{error || "Lettering page not found"}</main>;
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
              <h1 className="text-3xl font-semibold tracking-normal">Lettering Room</h1>
              <p className="mt-2 text-sm text-muted-foreground">
                {lettering.bubbles.length} bubbles - {lettering.sfx.length} SFX - vector layer export
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void load()}>
              <RefreshCcw className="h-4 w-4" />
              Load
            </Button>
            <Button variant="outline" onClick={() => void generateLettering()} disabled={isGenerating}>
              <Sparkles className="h-4 w-4" />
              {isGenerating ? "Generating" : "Generate Lettering"}
            </Button>
            <Button variant="outline" onClick={() => void addSfx()}>
              <Plus className="h-4 w-4" />
              SFX
            </Button>
            <Button asChild>
              <a href={svgUrl} download={`page-${pageId}-lettering.svg`}>
                <Download className="h-4 w-4" />
                SVG
              </a>
            </Button>
          </div>
        </header>

        {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div> : null}
        {warnings.length ? (
          <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {warnings.slice(0, 3).map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </div>
        ) : null}

        <section className="grid gap-4 md:grid-cols-4">
          <LetteringMetric label="Bubbles" value={lettering.bubbles.length} />
          <LetteringMetric label="SFX" value={lettering.sfx.length} />
          <LetteringMetric label="Warnings" value={warnings.length} />
          <LetteringMetric label="SVG Layer" value="Ready" />
        </section>

        <div className="grid gap-6 xl:grid-cols-[260px_minmax(0,1fr)_360px]">
          <aside className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Bubbles</CardTitle>
                <CardDescription>Page lettering</CardDescription>
              </CardHeader>
              <CardContent className="flex max-h-[420px] flex-col gap-2 overflow-auto">
                {lettering.bubbles.length === 0 ? (
                  <p className="rounded-md border bg-muted/30 px-3 py-4 text-sm text-muted-foreground">No bubbles yet. Generate lettering or add dialogue in Page Studio.</p>
                ) : null}
                {lettering.bubbles.map((bubble) => (
                  <button
                    type="button"
                    key={bubble.id}
                    onClick={() => setSelection({ type: "bubble", id: bubble.id })}
                    className={`rounded-md border bg-white px-3 py-2 text-left text-sm hover:border-primary/60 ${
                      selection?.type === "bubble" && selection.id === bubble.id ? "border-primary bg-primary/5" : ""
                    }`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="font-medium">{bubbleLabel(bubble)}</span>
                      <Badge>{bubble.bubble_type}</Badge>
                    </span>
                    <span className="mt-1 block truncate text-xs text-muted-foreground">{bubble.text}</span>
                  </button>
                ))}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>SFX</CardTitle>
                <CardDescription>Sound effect layers</CardDescription>
              </CardHeader>
              <CardContent className="flex max-h-[260px] flex-col gap-2 overflow-auto">
                {lettering.sfx.length === 0 ? <p className="rounded-md border bg-muted/30 px-3 py-4 text-sm text-muted-foreground">No SFX yet. Add one for impact panels.</p> : null}
                {lettering.sfx.map((element) => (
                  <button
                    type="button"
                    key={element.id}
                    onClick={() => setSelection({ type: "sfx", id: element.id })}
                    className={`rounded-md border bg-white px-3 py-2 text-left text-sm hover:border-primary/60 ${
                      selection?.type === "sfx" && selection.id === element.id ? "border-primary bg-primary/5" : ""
                    }`}
                  >
                    <span className="font-medium">{element.text}</span>
                    <span className="mt-1 block text-xs text-muted-foreground">{element.style}</span>
                  </button>
                ))}
              </CardContent>
            </Card>
          </aside>

          <section className="min-w-0 overflow-auto rounded-md border bg-[#e9e5dc] p-4">
            <div
              className="relative mx-auto bg-[#fffdf7] shadow-sm"
              style={{ width: stageWidth, height: stageHeight }}
              onPointerDown={() => setSelection(null)}
            >
              <div className="absolute inset-0 border-2 border-foreground" />
              {layout.panels.map((panel) => (
                <div
                  key={panel.id}
                  className="absolute border-2 border-foreground bg-white/40"
                  style={{
                    left: panel.x * scale,
                    top: panel.y * scale,
                    width: panel.width * scale,
                    height: panel.height * scale
                  }}
                />
              ))}
              {lettering.bubbles.map((bubble) => (
                <BubbleLayer
                  key={bubble.id}
                  bubble={bubble}
                  scale={scale}
                  selected={selection?.type === "bubble" && selection.id === bubble.id}
                  onSelect={() => setSelection({ type: "bubble", id: bubble.id })}
                  onDragStart={(event, mode) => {
                    event.stopPropagation();
                    if (bubble.locked) {
                      return;
                    }
                    dragRef.current = { type: "bubble", id: bubble.id, mode, startX: event.clientX, startY: event.clientY, x: bubble.x, y: bubble.y, width: bubble.width, height: bubble.height };
                  }}
                />
              ))}
              {lettering.sfx.map((element) => (
                <SfxLayer
                  key={element.id}
                  element={element}
                  scale={scale}
                  selected={selection?.type === "sfx" && selection.id === element.id}
                  onSelect={() => setSelection({ type: "sfx", id: element.id })}
                  onDragStart={(event, mode) => {
                    event.stopPropagation();
                    if (element.locked) {
                      return;
                    }
                    dragRef.current = {
                      type: "sfx",
                      id: element.id,
                      mode,
                      startX: event.clientX,
                      startY: event.clientY,
                      x: numberValue(element.position.x, 0),
                      y: numberValue(element.position.y, 0),
                      width: numberValue(element.size.width, 260),
                      height: numberValue(element.size.height, 120)
                    };
                  }}
                />
              ))}
            </div>
          </section>

          <aside className="flex flex-col gap-4">
            {selectedBubble ? (
              <BubbleInspector
                bubble={selectedBubble}
                characters={characters}
                onChange={(bubble) => updateBubbleLocal(bubble.id, () => bubble)}
                onSave={(bubble) => void persistBubble(bubble)}
              />
            ) : selectedSfx ? (
              <SfxInspector
                element={selectedSfx}
                onChange={(element) => updateSfxLocal(element.id, () => element)}
                onSave={(element) => void persistSfx(element)}
                onDelete={() => void deleteSelectedSfx()}
              />
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle>Inspector</CardTitle>
                  <CardDescription>No layer selected</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">Select a bubble or SFX layer to edit it.</CardContent>
              </Card>
            )}
          </aside>
        </div>
      </div>
    </main>
  );
}

function BubbleLayer({ bubble, scale, selected, onSelect, onDragStart }: { bubble: Bubble; scale: number; selected: boolean; onSelect: () => void; onDragStart: (event: ReactPointerEvent, mode: "move" | "resize") => void }) {
  const warning = readabilityWarning(bubble);
  const borderRadius = bubble.shape === "box" || bubble.bubble_type === "narration" ? 4 : 999;
  return (
    <div
      role="button"
      tabIndex={0}
      onPointerDown={(event) => {
        onSelect();
        onDragStart(event, "move");
      }}
      className={`absolute flex items-center justify-center border-2 bg-white px-2 text-center text-[10px] shadow-sm ${
        selected ? "border-primary ring-2 ring-primary/30" : warning ? "border-amber-500" : "border-foreground"
      }`}
      style={{ left: bubble.x * scale, top: bubble.y * scale, width: bubble.width * scale, height: bubble.height * scale, borderRadius }}
    >
      <span className={bubble.vertical_text ? "[writing-mode:vertical-rl]" : ""}>{bubble.text}</span>
      <span
        onPointerDown={(event) => {
          onSelect();
          onDragStart(event, "resize");
        }}
        className="absolute bottom-0 right-0 h-4 w-4 cursor-se-resize bg-primary"
      />
    </div>
  );
}

function SfxLayer({ element, scale, selected, onSelect, onDragStart }: { element: SFXElement; scale: number; selected: boolean; onSelect: () => void; onDragStart: (event: ReactPointerEvent, mode: "move" | "resize") => void }) {
  const x = numberValue(element.position.x, 0);
  const y = numberValue(element.position.y, 0);
  const width = numberValue(element.size.width, 260);
  const height = numberValue(element.size.height, 120);
  return (
    <div
      role="button"
      tabIndex={0}
      onPointerDown={(event) => {
        onSelect();
        onDragStart(event, "move");
      }}
      className={`absolute flex items-center justify-center text-center text-xl font-black ${selected ? "ring-2 ring-primary" : ""}`}
      style={{
        left: x * scale,
        top: y * scale,
        width: width * scale,
        height: height * scale,
        color: element.fill,
        WebkitTextStroke: `${Math.max(1, element.stroke_width * scale)}px ${element.outline}`,
        transform: `rotate(${element.rotation}deg)`
      }}
    >
      {element.text}
      <span
        onPointerDown={(event) => {
          onSelect();
          onDragStart(event, "resize");
        }}
        className="absolute bottom-0 right-0 h-4 w-4 cursor-se-resize bg-primary"
      />
    </div>
  );
}

function BubbleInspector({ bubble, characters, onChange, onSave }: { bubble: Bubble; characters: CharacterCard[]; onChange: (bubble: Bubble) => void; onSave: (bubble: Bubble) => void }) {
  const warning = readabilityWarning(bubble);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Bubble</CardTitle>
        <CardDescription>{warning || bubble.bubble_type}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Textarea value={bubble.text} onChange={(event) => onChange({ ...bubble, text: event.target.value })} />
        <label className="flex flex-col gap-2 text-sm font-medium">
          Type
          <select value={bubble.bubble_type} onChange={(event) => onChange({ ...bubble, bubble_type: event.target.value as BubbleKind, kind: event.target.value })} className="h-10 rounded-md border bg-white px-3 text-sm">
            {BUBBLE_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-2 text-sm font-medium">
          Speaker
          <select value={bubble.speaker_character_id ?? ""} onChange={(event) => onChange({ ...bubble, speaker_character_id: event.target.value || null })} className="h-10 rounded-md border bg-white px-3 text-sm">
            <option value="">None</option>
            {characters.map((character) => <option key={character.id} value={character.id}>{character.name}</option>)}
          </select>
        </label>
        <div className="grid grid-cols-2 gap-3">
          <NumberField label="X" value={bubble.x} onChange={(x) => onChange({ ...bubble, x, position: { x, y: bubble.y } })} />
          <NumberField label="Y" value={bubble.y} onChange={(y) => onChange({ ...bubble, y, position: { x: bubble.x, y } })} />
          <NumberField label="Width" value={bubble.width} onChange={(width) => onChange({ ...bubble, width, size: { width, height: bubble.height } })} />
          <NumberField label="Height" value={bubble.height} onChange={(height) => onChange({ ...bubble, height, size: { width: bubble.width, height } })} />
          <NumberField label="Font" value={bubble.font_size} onChange={(font_size) => onChange({ ...bubble, font_size })} />
          <NumberField label="Z" value={bubble.z_index} onChange={(z_index) => onChange({ ...bubble, z_index })} />
        </div>
        <label className="flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" checked={bubble.vertical_text} onChange={(event) => onChange({ ...bubble, vertical_text: event.target.checked })} />
          Vertical text
        </label>
        <label className="flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" checked={bubble.locked} onChange={(event) => onChange({ ...bubble, locked: event.target.checked })} />
          Locked
        </label>
        <Button onClick={() => onSave(bubble)}>
          <Save className="h-4 w-4" />
          Save Bubble
        </Button>
      </CardContent>
    </Card>
  );
}

function SfxInspector({ element, onChange, onSave, onDelete }: { element: SFXElement; onChange: (element: SFXElement) => void; onSave: (element: SFXElement) => void; onDelete: () => void }) {
  const x = numberValue(element.position.x, 0);
  const y = numberValue(element.position.y, 0);
  const width = numberValue(element.size.width, 260);
  const height = numberValue(element.size.height, 120);
  return (
    <Card>
      <CardHeader>
        <CardTitle>SFX</CardTitle>
        <CardDescription>{element.style}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Input value={element.text} onChange={(event) => onChange({ ...element, text: event.target.value })} />
        <Textarea value={element.meaning} onChange={(event) => onChange({ ...element, meaning: event.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <NumberField label="X" value={x} onChange={(nextX) => onChange({ ...element, position: { ...element.position, x: nextX } })} />
          <NumberField label="Y" value={y} onChange={(nextY) => onChange({ ...element, position: { ...element.position, y: nextY } })} />
          <NumberField label="Width" value={width} onChange={(nextWidth) => onChange({ ...element, size: { ...element.size, width: nextWidth } })} />
          <NumberField label="Height" value={height} onChange={(nextHeight) => onChange({ ...element, size: { ...element.size, height: nextHeight } })} />
          <NumberField label="Rotate" value={element.rotation} onChange={(rotation) => onChange({ ...element, rotation })} />
          <NumberField label="Stroke" value={element.stroke_width} onChange={(stroke_width) => onChange({ ...element, stroke_width })} />
        </div>
        <label className="flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" checked={element.locked} onChange={(event) => onChange({ ...element, locked: event.target.checked })} />
          Locked
        </label>
        <div className="grid grid-cols-2 gap-2">
          <Button onClick={() => onSave(element)}>
            <Save className="h-4 w-4" />
            Save
          </Button>
          <Button variant="outline" onClick={onDelete}>
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>
        <Button variant="outline" onClick={() => onChange({ ...element, rotation: element.rotation + 8 })}>
          <RotateCw className="h-4 w-4" />
          Rotate
        </Button>
      </CardContent>
    </Card>
  );
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="flex flex-col gap-2 text-sm font-medium">
      {label}
      <Input type="number" value={Number.isFinite(value) ? value : 0} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

function readabilityWarning(bubble: Bubble) {
  const capacity = Math.max(12, Math.floor((bubble.width * bubble.height) / Math.max(1, bubble.font_size * bubble.font_size * 0.78)));
  if (bubble.text.length > capacity) {
    return "Text may be too long for this bubble.";
  }
  return null;
}

function bubbleLabel(bubble: Bubble) {
  return `${bubble.bubble_type} ${bubble.id.slice(0, 4)}`;
}

function numberValue(value: unknown, fallback: number) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function LetteringMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  );
}

const BUBBLE_TYPES: BubbleKind[] = ["speech", "thought", "narration", "shout", "whisper", "radio", "monster", "offscreen"];
