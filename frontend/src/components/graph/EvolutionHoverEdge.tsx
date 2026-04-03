"use client";

import { useCallback, useState } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from "@xyflow/react";

export type EvolutionEdgePayload = {
  relationshipType?: string;
  metrics?: string[];
  datasets?: string[];
};

function formatEdgeTooltip(d: EvolutionEdgePayload | undefined): string {
  const rel = d?.relationshipType?.trim() || "IMPROVES_UPON";
  const metrics = d?.metrics?.filter(Boolean) ?? [];
  const datasets = d?.datasets?.filter(Boolean) ?? [];
  const parts: string[] = [rel];
  if (metrics.length) {
    parts.push(`🚀 ${metrics.slice(0, 3).join(" · ")}`);
  }
  if (datasets.length) {
    parts.push(`💽 ${datasets.slice(0, 2).join(" · ")}`);
  }
  return parts.join(" | ");
}

export function EvolutionHoverEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  markerEnd,
  data,
}: EdgeProps) {
  const [hover, setHover] = useState(false);
  const d = data as EvolutionEdgePayload | undefined;

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const onEnter = useCallback(() => setHover(true), []);
  const onLeave = useCallback(() => setHover(false), []);

  const stroke = hover ? "#b45309" : "#78716c";
  const strokeWidth = hover ? 2.25 : 1.5;

  return (
    <>
      <g
        onMouseEnter={onEnter}
        onMouseLeave={onLeave}
        style={{ cursor: "pointer" }}
      >
        <path
          d={edgePath}
          fill="none"
          stroke="transparent"
          strokeWidth={24}
          className="react-flow__edge-interaction"
        />
        <BaseEdge
          id={id}
          path={edgePath}
          markerEnd={markerEnd}
          style={{
            ...style,
            stroke,
            strokeWidth,
            transition: "stroke 0.15s ease, stroke-width 0.15s ease",
          }}
        />
      </g>
      <EdgeLabelRenderer>
        {hover ? (
          <div
            className="nodrag nopan pointer-events-none max-w-[280px] rounded-md border border-amber-200/90 bg-white/95 px-2.5 py-1.5 font-mono text-[11px] leading-snug text-stone-800 shadow-lg shadow-amber-900/10"
            style={{
              position: "absolute",
              transform: `translate(-50%, -100%) translate(${labelX}px,${labelY - 8}px)`,
            }}
          >
            {formatEdgeTooltip(d)}
          </div>
        ) : null}
      </EdgeLabelRenderer>
    </>
  );
}

export const evolutionEdgeTypes = {
  evolutionHover: EvolutionHoverEdge,
};
