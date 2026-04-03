"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";

export type CommandCenterNodeData = {
  labels: string[];
  properties: Record<string, unknown>;
  label: string;
  sublabel: string;
  color?: string;
};

function primaryKind(
  labels: string[] | undefined
): "Task" | "Method" | "Paper" | "Other" {
  const L = (labels ?? []).map((x) => String(x).toLowerCase());
  if (L.includes("task")) return "Task";
  if (L.includes("method")) return "Method";
  if (L.includes("paper")) return "Paper";
  return "Other";
}

/** 指挥台统一节点：按 Neo4j Label 分支为 Task / Method / Paper / 默认 */
export function CommandCenterNode({ data }: NodeProps) {
  const d = data as CommandCenterNodeData;
  const kind = primaryKind(d.labels);
  const props = d.properties ?? {};

  const arxivId =
    (props.arxiv_id as string) ||
    (String(d.label).match(/\d{4}\.\d{4,5}/)?.[0] ?? "");
  const titleStr =
    (props.title as string) || (kind === "Paper" ? d.label : d.label);

  if (kind === "Task") {
    return (
      <>
        <Handle
          type="target"
          position={Position.Top}
          className="!h-2 !w-2 !border-0 !bg-amber-400/80"
        />
        <div
          className="min-w-[150px] max-w-[220px] rounded-2xl border-2 border-amber-400 bg-amber-950/90 px-4 py-3 shadow-lg drop-shadow-[0_0_15px_rgba(245,158,11,0.45)]"
        >
          <div className="text-[10px] font-semibold uppercase tracking-wider text-amber-400/90">
            Task
          </div>
          <div className="mt-1 break-words text-sm font-bold leading-snug text-amber-100">
            {d.label}
          </div>
        </div>
        <Handle
          type="source"
          position={Position.Bottom}
          className="!h-2 !w-2 !border-0 !bg-amber-400/80"
        />
      </>
    );
  }

  if (kind === "Method") {
    return (
      <>
        <Handle
          type="target"
          position={Position.Top}
          className="!h-2 !w-2 !border-0 !bg-cyan-400/70"
        />
        <div className="min-w-[128px] max-w-[200px] rounded-xl border border-cyan-500 bg-cyan-950/90 px-3 py-2 shadow-md">
          <div className="text-[10px] font-medium uppercase tracking-wide text-cyan-400/90">
            Method
          </div>
          <div className="mt-0.5 break-words text-sm font-semibold leading-snug text-cyan-100">
            {d.label}
          </div>
        </div>
        <Handle
          type="source"
          position={Position.Bottom}
          className="!h-2 !w-2 !border-0 !bg-cyan-400/70"
        />
      </>
    );
  }

  if (kind === "Paper") {
    return (
      <>
        <Handle
          type="target"
          position={Position.Top}
          className="!h-2 !w-2 !border-0 !bg-slate-500"
        />
        <div className="min-w-[140px] max-w-[220px] rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 shadow-md">
          <div className="font-mono text-[10px] font-medium text-slate-400">
            {arxivId || "arXiv"}
          </div>
          <div className="mt-1 line-clamp-2 break-words text-xs font-semibold leading-snug text-slate-100">
            {titleStr}
          </div>
        </div>
        <Handle
          type="source"
          position={Position.Bottom}
          className="!h-2 !w-2 !border-0 !bg-slate-500"
        />
      </>
    );
  }

  return (
    <>
      <Handle
        type="target"
        position={Position.Top}
        className="!h-2 !w-2 !border-0 !bg-slate-500"
      />
      <div
        className="min-w-[120px] max-w-[200px] rounded-lg border border-slate-600 bg-slate-900/95 px-3 py-2 shadow-md"
        style={{
          borderColor: d.color ? `${d.color}99` : undefined,
        }}
      >
        <div className="text-[10px] font-medium uppercase text-slate-500">
          {d.sublabel}
        </div>
        <div className="mt-0.5 break-words text-sm font-medium leading-tight text-slate-200">
          {d.label}
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-2 !w-2 !border-0 !bg-slate-500"
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
        className="!h-2 !w-2 !border-0 !bg-cyan-500/80"
      />
      <div
        className={`max-w-[220px] rounded-xl border px-3 py-2 shadow-md ${
          isRoot
            ? "border-cyan-400 bg-cyan-950/80 shadow-cyan-500/20"
            : "border-slate-600 bg-slate-900/95"
        }`}
      >
        <div className="font-mono text-[10px] text-slate-500">
          G{d.generation}
        </div>
        <div
          className={`text-sm font-semibold leading-snug ${
            isRoot ? "text-cyan-100" : "text-slate-200"
          }`}
        >
          {d.label}
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="!h-2 !w-2 !border-0 !bg-cyan-500/80"
      />
    </>
  );
}

export const commandCenterNodeTypes = { commandCenter: CommandCenterNode };
export const evolutionNodeTypes = { evolution: EvolutionGraphNode };
