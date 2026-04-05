"use client";

import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from "@xyflow/react";

export type LabeledEdgePayload = {
  edgeType: string;
};

// Edge colors by relationship type (bright colors)
const EDGE_COLORS: Record<string, string> = {
  PROPOSES: "#06b6d4",      // cyan
  WRITTEN_BY: "#2563eb",    // blue
  ADDRESSES: "#d97706",     // amber
  EVALUATED_ON: "#ca8a04",  // yellow
  APPLIED_TO: "#7c3aed",    // violet
  IMPROVES_UPON: "#ea580c",  // orange
  EVOLVED_FROM: "#c026d3",  // fuchsia
  MEASURES: "#db2777",      // pink
  DEFAULT: "#475569",       // slate
};

function getEdgeColor(edgeType: string): string {
  return EDGE_COLORS[edgeType] || EDGE_COLORS.DEFAULT;
}

export function LabeledEdge({
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
  const d = data as LabeledEdgePayload | undefined;
  const edgeType = d?.edgeType || "RELATED";
  const color = getEdgeColor(edgeType);

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke: color,
          strokeWidth: 1.5,
        }}
      />
      <EdgeLabelRenderer>
        <div
          className="nodrag nopan pointer-events-none rounded px-1.5 py-0.5 text-[9px] font-mono font-semibold"
          style={{
            position: "absolute",
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            backgroundColor: "rgba(255, 255, 255, 0.95)",
            color: color,
            border: `1.5px solid ${color}`,
            boxShadow: `0 1px 4px rgba(0,0,0,0.15)`,
            whiteSpace: "nowrap",
          }}
        >
          {edgeType}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

export const labeledEdgeTypes = {
  labeled: LabeledEdge,
};
