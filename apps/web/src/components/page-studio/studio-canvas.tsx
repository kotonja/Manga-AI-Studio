"use client";

import { useEffect, useRef, useState } from "react";
import { Arrow, Group, Image as KonvaImage, Layer, Rect, Stage, Text, Transformer } from "react-konva";
import type { KonvaEventObject } from "konva/lib/Node";

import type { Bubble, PageLayout, PanelLayout } from "@manga-ai/shared";

type StudioCanvasProps = {
  layout: PageLayout;
  selectedPanelId: string | null;
  selectedBubbleId: string | null;
  onSelectPanel: (panelId: string | null) => void;
  onSelectBubble: (bubbleId: string | null, panelId: string) => void;
  onPanelChange: (panel: PanelLayout) => void;
  onBubbleChange: (panelId: string, bubble: Bubble, persist: boolean) => void;
  panelRenderUrls?: Record<string, string>;
  highlightedPanelId?: string | null;
  highlightedBubbleId?: string | null;
  panelLabels?: Record<string, string>;
  lockedPanelIds?: string[];
  zoom?: number;
  showGrid?: boolean;
};

export function StudioCanvas({
  layout,
  selectedPanelId,
  selectedBubbleId,
  onSelectPanel,
  onSelectBubble,
  onPanelChange,
  onBubbleChange,
  panelRenderUrls = {},
  highlightedPanelId = null,
  highlightedBubbleId = null,
  panelLabels = {},
  lockedPanelIds = [],
  zoom = 1,
  showGrid = true
}: StudioCanvasProps) {
  const selectedPanelRef = useRef<any>(null);
  const transformerRef = useRef<any>(null);
  const stageWidth = Math.min(820, layout.width) * zoom;
  const scale = stageWidth / layout.width;
  const stageHeight = layout.height * scale;

  useEffect(() => {
    if (transformerRef.current && selectedPanelRef.current) {
      transformerRef.current.nodes([selectedPanelRef.current]);
      transformerRef.current.getLayer()?.batchDraw();
    }
  }, [selectedPanelId, layout.panels, lockedPanelIds]);

  function updatePanelDrag(panel: PanelLayout, event: KonvaEventObject<DragEvent>) {
    const node = event.target;
    const nextX = clamp(Math.round(node.x()), 0, layout.width - panel.width);
    const nextY = clamp(Math.round(node.y()), 0, layout.height - panel.height);
    onPanelChange({
      ...panel,
      x: nextX,
      y: nextY,
      polygon: rectPolygon(nextX, nextY, panel.width, panel.height)
    });
  }

  function updatePanelTransform(panel: PanelLayout, event: KonvaEventObject<Event>) {
    const node = event.target as any;
    const nextWidth = clamp(Math.round(node.width() * node.scaleX()), 48, layout.width - node.x());
    const nextHeight = clamp(Math.round(node.height() * node.scaleY()), 48, layout.height - node.y());
    const nextX = clamp(Math.round(node.x()), 0, layout.width - nextWidth);
    const nextY = clamp(Math.round(node.y()), 0, layout.height - nextHeight);
    node.scaleX(1);
    node.scaleY(1);
    onPanelChange({
      ...panel,
      x: nextX,
      y: nextY,
      width: nextWidth,
      height: nextHeight,
      polygon: rectPolygon(nextX, nextY, nextWidth, nextHeight)
    });
  }

  return (
    <div className="overflow-auto rounded-md border bg-[#e9e5dc] p-4">
      <Stage
        width={stageWidth}
        height={stageHeight}
        className="mx-auto bg-white shadow-sm"
        onMouseDown={(event) => {
          if (event.target === event.target.getStage()) {
            onSelectPanel(null);
          }
        }}
      >
        <Layer scaleX={scale} scaleY={scale}>
          <Rect x={0} y={0} width={layout.width} height={layout.height} fill="#fffdf7" stroke="#22242a" strokeWidth={4} />
          {showGrid
            ? gridLines(layout.width, layout.height, 120).map((line) => (
                <Rect
                  key={line.key}
                  x={line.x}
                  y={line.y}
                  width={line.width}
                  height={line.height}
                  fill="rgba(15,118,110,0.09)"
                  listening={false}
                />
              ))
            : null}
          <Rect
            x={layout.bleed}
            y={layout.bleed}
            width={layout.width - layout.bleed * 2}
            height={layout.height - layout.bleed * 2}
            stroke="#dc2626"
            strokeWidth={2}
            dash={[18, 12]}
            opacity={0.45}
            visible={layout.qa_overlay_enabled}
          />
          <Rect
            x={layout.safe_margin}
            y={layout.safe_margin}
            width={layout.width - layout.safe_margin * 2}
            height={layout.height - layout.safe_margin * 2}
            stroke="#0f766e"
            strokeWidth={2}
            dash={[10, 10]}
            opacity={0.5}
            visible={layout.qa_overlay_enabled}
          />
          {layout.qa_overlay_enabled ? (
            <Text x={32} y={32} text={`QA - ${layout.reading_direction}`} fontSize={34} fill="#0f766e" opacity={0.65} />
          ) : null}

          {layout.panels
            .slice()
            .sort((first, second) => first.reading_order - second.reading_order)
            .map((panel, index, orderedPanels) => {
              const next = orderedPanels[index + 1];
              if (!next) {
                return null;
              }
              return (
                <Arrow
                  key={`${panel.id}-${next.id}`}
                  points={[
                    panel.x + panel.width / 2,
                    panel.y + panel.height / 2,
                    next.x + next.width / 2,
                    next.y + next.height / 2
                  ]}
                  pointerLength={18}
                  pointerWidth={16}
                  stroke="#0f766e"
                  fill="#0f766e"
                  strokeWidth={4}
                  opacity={0.28}
                  listening={false}
                />
              );
            })}

          {layout.panels.map((panel) => {
            const isSelected = selectedPanelId === panel.id;
            const isHighlighted = highlightedPanelId === panel.id;
            const isLocked = lockedPanelIds.includes(panel.id);
            const label = panelLabels[panel.id];
            const outputUrl = panelRenderUrls[panel.id];
            return (
              <Group key={panel.id}>
                {outputUrl ? <PanelRenderImage panel={panel} url={outputUrl} /> : null}
                <Rect
                  ref={(node) => {
                    if (isSelected && !isLocked) {
                      selectedPanelRef.current = node;
                    }
                  }}
                  x={panel.x}
                  y={panel.y}
                  width={panel.width}
                  height={panel.height}
                  fill={
                    outputUrl
                      ? isSelected
                        ? "rgba(15,118,110,0.08)"
                        : "rgba(255,255,255,0.01)"
                      : isSelected
                        ? "rgba(15,118,110,0.1)"
                        : "rgba(255,255,255,0.72)"
                  }
                  stroke={isSelected ? "#0f766e" : isHighlighted ? "#f59e0b" : isLocked ? "#2563eb" : "#22242a"}
                  strokeWidth={isSelected ? 6 : isHighlighted ? 7 : 4}
                  dash={isLocked ? [16, 10] : undefined}
                  draggable={!isLocked}
                  onClick={() => onSelectPanel(panel.id)}
                  onTap={() => onSelectPanel(panel.id)}
                  onDragEnd={(event) => updatePanelDrag(panel, event)}
                  onTransformEnd={(event) => updatePanelTransform(panel, event)}
                />
                <Text
                  x={panel.x + 12}
                  y={panel.y + 10}
                  text={`${panel.reading_order}`}
                  fontSize={30}
                  fontStyle="bold"
                  fill="#22242a"
                  listening={false}
                />
                {isLocked ? (
                  <Text
                    x={panel.x + panel.width - 78}
                    y={panel.y + 12}
                    width={62}
                    text="LOCK"
                    align="right"
                    fontSize={18}
                    fontStyle="bold"
                    fill="#2563eb"
                    listening={false}
                  />
                ) : null}
                {label ? (
                  <>
                    <Rect
                      x={panel.x + 12}
                      y={panel.y + panel.height - 54}
                      width={Math.min(panel.width - 24, 360)}
                      height={38}
                      fill="rgba(255,253,247,0.88)"
                      stroke="#0f766e"
                      strokeWidth={1}
                      cornerRadius={4}
                      listening={false}
                    />
                    <Text
                      x={panel.x + 24}
                      y={panel.y + panel.height - 44}
                      width={Math.min(panel.width - 48, 336)}
                      text={label}
                      fontSize={18}
                      fill="#0f766e"
                      ellipsis
                      listening={false}
                    />
                  </>
                ) : null}
                {panel.bubbles.map((bubble) => (
                  <Group
                    key={bubble.id}
                    x={bubble.x}
                    y={bubble.y}
                    draggable
                    onClick={() => onSelectBubble(bubble.id, panel.id)}
                    onTap={() => onSelectBubble(bubble.id, panel.id)}
                    onDragEnd={(event) => {
                      const nextBubble = {
                        ...bubble,
                        x: clamp(Math.round(event.target.x()), 0, layout.width - bubble.width),
                        y: clamp(Math.round(event.target.y()), 0, layout.height - bubble.height)
                      };
                      onBubbleChange(panel.id, nextBubble, true);
                    }}
                  >
                    <Rect
                      width={bubble.width}
                      height={bubble.height}
                      fill={bubble.kind === "narration" ? "#fff7d6" : "#ffffff"}
                      stroke={
                        selectedBubbleId === bubble.id
                          ? "#be123c"
                          : highlightedBubbleId === bubble.id
                            ? "#f59e0b"
                            : "#22242a"
                      }
                      strokeWidth={highlightedBubbleId === bubble.id ? 5 : 3}
                      cornerRadius={bubble.kind === "narration" ? 4 : 32}
                    />
                    <Text
                      x={16}
                      y={14}
                      width={bubble.width - 32}
                      text={bubble.text}
                      fontSize={24}
                      fill="#22242a"
                      listening={false}
                    />
                  </Group>
                ))}
              </Group>
            );
          })}
          {selectedPanelId && !lockedPanelIds.includes(selectedPanelId) ? (
            <Transformer
              ref={transformerRef}
              rotateEnabled={false}
              keepRatio={false}
              boundBoxFunc={(oldBox, newBox) => {
                if (newBox.width < 48 || newBox.height < 48) {
                  return oldBox;
                }
                if (newBox.x < 0 || newBox.y < 0 || newBox.x + newBox.width > layout.width || newBox.y + newBox.height > layout.height) {
                  return oldBox;
                }
                return newBox;
              }}
            />
          ) : null}
        </Layer>
      </Stage>
    </div>
  );
}

function rectPolygon(x: number, y: number, width: number, height: number) {
  return [
    { x, y },
    { x: x + width, y },
    { x: x + width, y: y + height },
    { x, y: y + height }
  ];
}

function PanelRenderImage({ panel, url }: { panel: PanelLayout; url: string }) {
  const [image, setImage] = useState<HTMLImageElement | null>(null);

  useEffect(() => {
    let isMounted = true;
    const nextImage = new window.Image();
    nextImage.onload = () => {
      if (isMounted) {
        setImage(nextImage);
      }
    };
    nextImage.onerror = () => {
      if (isMounted) {
        setImage(null);
      }
    };
    nextImage.src = url;
    return () => {
      isMounted = false;
    };
  }, [url]);

  if (image === null) {
    return null;
  }

  return (
    <KonvaImage
      image={image}
      x={panel.x}
      y={panel.y}
      width={panel.width}
      height={panel.height}
      opacity={0.96}
      listening={false}
    />
  );
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function gridLines(width: number, height: number, step: number) {
  const lines: Array<{ key: string; x: number; y: number; width: number; height: number }> = [];
  for (let x = step; x < width; x += step) {
    lines.push({ key: `x-${x}`, x, y: 0, width: 1, height });
  }
  for (let y = step; y < height; y += step) {
    lines.push({ key: `y-${y}`, x: 0, y, width, height: 1 });
  }
  return lines;
}
