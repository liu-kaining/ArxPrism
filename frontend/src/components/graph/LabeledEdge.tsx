"use client";

import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from "@xyflow/react";

export type LabeledEdgePayload = {
  edgeType: string;
};

// Edge colors by relationship type
const EDGE_COLORS: Record<string, string> = {
  PROPOSES: "#06b6d4",      // cyan
  WRITTEN_BY: "#3b82f6",    // blue
  ADDRESSES: "#f59e0b",     // amber
  EVALUATED_ON: "#eab308",  // yellow
  APPLIED_TO: "#a855f7",    // purple
  IMPROVES_UPON: "#f97316", // orange
  EVOLVED_FROM: "#a855f7",  // purple
  MEASURES: "#ec4899",      // pink
  DEFAULT: "#78716c",        // stone
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
            backgroundColor: "rgba(15, 15, 15, 0.9)",
            color: color,
            border: `1px solid ${color}50`,
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
