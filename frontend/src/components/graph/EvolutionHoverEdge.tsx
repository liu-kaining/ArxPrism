"use client";

import { useCallback, useState } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from "@xyflow/react";

function safeTrim(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "string") return v.trim();
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  return "";
}

export type EvolutionEdgePayload = {
  relationshipType?: string;
  metrics?: string[];
  datasets?: string[];
  reason?: string;
  discovered_at?: string;
  /** 实验对比边遗留属性（IMPROVES_UPON） */
  dataset?: string;
  metrics_improvement?: string;
};

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

  const rel = safeTrim(d?.relationshipType) || "EVOLVED_FROM";
  const reason = safeTrim(d?.reason);
  const at = safeTrim(d?.discovered_at);
  const dsEdge = safeTrim(d?.dataset);
  const metEdge = safeTrim(d?.metrics_improvement);
  const metrics = Array.isArray(d?.metrics) ? d.metrics.filter(Boolean) : [];
  const datasets = Array.isArray(d?.datasets)
    ? d.datasets.filter(Boolean)
    : [];

  // Determine edge color based on relationship type (bright colors)
  const edgeColor = rel === "EVOLVED_FROM"
    ? "#c026d3" // fuchsia for EVOLVED_FROM
    : rel === "IMPROVES_UPON"
      ? "#ea580c" // orange for IMPROVES_UPON
      : "#06b6d4"; // cyan for other relationships

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
            stroke: hover ? edgeColor : "#78716c",
            strokeWidth,
            transition: "stroke 0.15s ease, stroke-width 0.15s ease",
          }}
        />
      </g>
      <EdgeLabelRenderer>
        {/* Always-visible edge label */}
        <div
          className="nodrag nopan pointer-events-none rounded px-1.5 py-0.5 text-[9px] font-mono font-medium"
          style={{
            position: "absolute",
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            backgroundColor: "rgba(15, 15, 15, 0.85)",
            color: edgeColor,
            border: `1px solid ${edgeColor}40`,
          }}
        >
          {rel}
        </div>
        {/* Enhanced hover tooltip with more info */}
        {hover ? (
          <div
            className="nodrag nopan pointer-events-none max-w-[min(92vw,340px)] rounded-lg border border-amber-300/90 bg-stone-950/95 px-3 py-2 text-left shadow-xl shadow-amber-900/25 ring-1 ring-violet-500/20"
            style={{
              position: "absolute",
              transform: `translate(-50%, -100%) translate(${labelX}px,${labelY - 10}px)`,
            }}
          >
            {reason || at ? (
              <>
                <div className="flex items-center gap-2">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-amber-300">
                    [Evolution Reason]
                  </div>
                  <div className="font-mono text-[9px] text-stone-500">
                    {rel}
                  </div>
                </div>
                <p className="mt-1 text-[12px] font-medium leading-snug text-stone-100">
                  {reason || "—"}
                </p>
                {at ? (
                  <p className="mt-2 border-t border-stone-700 pt-2 font-mono text-[10px] text-violet-300/95">
                    discovered_at: {at}
                  </p>
                ) : null}
              </>
            ) : dsEdge || metEdge ? (
              <>
                <div className="flex items-center gap-2">
                  <div className="font-mono text-[10px] text-orange-400">{rel}</div>
                  {dsEdge ? (
                    <span className="rounded bg-orange-900/60 px-1 py-0.5 font-mono text-[9px] text-orange-200">
                      {dsEdge}
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-[11px] text-stone-200">
                  {metEdge || "—"}
                </p>
              </>
            ) : (
              <>
                <div className="font-mono text-[10px] text-amber-200/90">
                  {rel}
                </div>
                {metrics.length ? (
                  <p className="mt-1 text-[11px] text-stone-200">
                    {metrics.slice(0, 3).join(" · ")}
                  </p>
                ) : null}
                {datasets.length ? (
                  <p className="mt-1 text-[10px] text-stone-400">
                    {datasets.slice(0, 2).join(" · ")}
                  </p>
                ) : null}
              </>
            )}
          </div>
        ) : null}
      </EdgeLabelRenderer>
    </>
  );
}

export const evolutionEdgeTypes = {
  evolutionHover: EvolutionHoverEdge,
};
