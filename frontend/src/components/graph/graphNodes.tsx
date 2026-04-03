"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";

export type PaperGraphNodeData = {
  label: string;
  sublabel: string;
  color: string;
};

export function PaperGraphNode({ data }: NodeProps) {
  const d = data as PaperGraphNodeData;
  return (
    <>
      <Handle
        type="target"
        position={Position.Top}
        className="!h-2 !w-2 !border-0 !bg-muted-foreground"
      />
      <div
        className="min-w-[120px] max-w-[200px] rounded-lg border-2 bg-card px-3 py-2 shadow-md"
        style={{ borderColor: d.color }}
      >
        <div className="text-xs font-medium text-muted-foreground">
          {d.sublabel}
        </div>
        <div className="break-words text-sm font-semibold leading-tight">
          {d.label}
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-2 !w-2 !border-0 !bg-muted-foreground"
      />
    </>
  );
}

export type EvolutionNodeData = {
  label: string;
  generation: number;
};

export function EvolutionGraphNode({ data }: NodeProps) {
  const d = data as EvolutionNodeData;
  const isRoot = d.generation === 0;
  return (
    <>
      <Handle
        type="target"
        position={Position.Left}
        className="!h-2 !w-2 !border-0 !bg-muted-foreground"
      />
      <div
        className={`max-w-[220px] rounded-xl border-2 px-3 py-2 shadow-md ${
          isRoot
            ? "border-primary bg-primary/10"
            : "border-border bg-card"
        }`}
      >
        <div className="text-xs text-muted-foreground">G{d.generation}</div>
        <div className="text-sm font-semibold leading-snug">{d.label}</div>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="!h-2 !w-2 !border-0 !bg-muted-foreground"
      />
    </>
  );
}

export const paperGraphNodeTypes = { paperGraph: PaperGraphNode };
export const evolutionNodeTypes = { evolution: EvolutionGraphNode };
