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
        <div className="min-w-[150px] max-w-[220px] rounded-2xl border-2 border-amber-500 bg-amber-50 px-4 py-3 shadow-md ring-1 ring-amber-200/80">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-amber-800">
            Task
          </div>
          <div className="mt-1 break-words text-sm font-bold leading-snug text-amber-950">
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
        <div className="min-w-[128px] max-w-[200px] rounded-xl border border-cyan-600 bg-cyan-50 px-3 py-2 shadow-md ring-1 ring-cyan-200/70">
          <div className="text-[10px] font-medium uppercase tracking-wide text-cyan-800">
            Method
          </div>
          <div className="mt-0.5 break-words text-sm font-semibold leading-snug text-cyan-950">
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
          className="!h-2 !w-2 !border-0 !bg-stone-400"
        />
        <div className="min-w-[140px] max-w-[220px] rounded-lg border border-stone-300 bg-white px-3 py-2 shadow-md ring-1 ring-stone-200/80">
          <div className="font-mono text-[10px] font-medium text-stone-500">
            {arxivId || "arXiv"}
          </div>
          <div className="mt-1 line-clamp-2 break-words text-xs font-semibold leading-snug text-stone-900">
            {titleStr}
          </div>
        </div>
        <Handle
          type="source"
          position={Position.Bottom}
          className="!h-2 !w-2 !border-0 !bg-stone-400"
        />
      </>
    );
  }

  return (
    <>
      <Handle
        type="target"
        position={Position.Top}
        className="!h-2 !w-2 !border-0 !bg-stone-400"
      />
      <div
        className="min-w-[120px] max-w-[200px] rounded-lg border border-stone-300 bg-white px-3 py-2 shadow-md ring-1 ring-stone-200/80"
        style={{
          borderColor: d.color ? `${d.color}99` : undefined,
        }}
      >
        <div className="text-[10px] font-medium uppercase text-stone-500">
          {d.sublabel}
        </div>
        <div className="mt-0.5 break-words text-sm font-medium leading-tight text-stone-900">
          {d.label}
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-2 !w-2 !border-0 !bg-stone-400"
      />
    </>
  );
}

export type EvolutionNodeData = {
  label: string;
  generation: number;
  core_architecture?: string;
};

function showCoreArchitecture(raw: string | undefined): string | null {
  const s = (raw ?? "").trim();
  if (!s || s.toUpperCase() === "NOT_MENTIONED") return null;
  return s;
}

function safeGenerationLabel(v: unknown): number {
  const n = typeof v === "number" && !Number.isNaN(v) ? v : Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : 0;
}

export function EvolutionGraphNode({ data }: NodeProps) {
  const d = (data ?? {}) as EvolutionNodeData;
  const gen = safeGenerationLabel(d.generation);
  const isRoot = gen === 0;
  const arch = showCoreArchitecture(d.core_architecture);
  return (
    <>
      <Handle
        type="target"
        position={Position.Bottom}
        className="!h-2 !w-2 !border-0 !bg-violet-500/80"
      />
      <div
        className={`max-w-[220px] rounded-xl border px-3 py-2 shadow-md ring-1 ${
          isRoot
            ? "border-cyan-600 bg-cyan-50 shadow-cyan-900/10 ring-cyan-200/80"
            : "border-stone-300 bg-white ring-stone-200/80"
        }`}
      >
        <div className="font-mono text-[10px] text-stone-500">
          G{gen}
        </div>
        <div
          className={`text-sm font-semibold leading-snug ${
            isRoot ? "text-cyan-950" : "text-stone-900"
          }`}
        >
          {d.label ?? ""}
        </div>
        {arch ? (
          <div className="mt-1 font-mono text-[10px] font-medium tracking-tight text-violet-600/95">
            [Arch: {arch}]
          </div>
        ) : null}
      </div>
      <Handle
        type="source"
        position={Position.Top}
        className="!h-2 !w-2 !border-0 !bg-violet-500/80"
      />
    </>
  );
}

export const commandCenterNodeTypes = { commandCenter: CommandCenterNode };
export const evolutionNodeTypes = { evolution: EvolutionGraphNode };
