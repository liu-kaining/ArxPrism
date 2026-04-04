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

  const rel = d?.relationshipType?.trim() || "EVOLVED_FROM";
  const reason = d?.reason?.trim() ?? "";
  const at = d?.discovered_at?.trim() ?? "";
  const dsEdge = d?.dataset?.trim() ?? "";
  const metEdge = d?.metrics_improvement?.trim() ?? "";
  const metrics = d?.metrics?.filter(Boolean) ?? [];
  const datasets = d?.datasets?.filter(Boolean) ?? [];

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
            className="nodrag nopan pointer-events-none max-w-[min(92vw,320px)] rounded-lg border border-amber-300/90 bg-stone-950/95 px-3 py-2 text-left shadow-xl shadow-amber-900/25 ring-1 ring-violet-500/20"
            style={{
              position: "absolute",
              transform: `translate(-50%, -100%) translate(${labelX}px,${labelY - 10}px)`,
            }}
          >
            {reason || at ? (
              <>
                <div className="text-[10px] font-bold uppercase tracking-wider text-amber-300">
                  [Evolution Reason]
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
                <div className="font-mono text-[10px] text-stone-400">{rel}</div>
                <p className="mt-1 text-[11px] text-stone-200">
                  {dsEdge ? `[${dsEdge}] ` : ""}
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
