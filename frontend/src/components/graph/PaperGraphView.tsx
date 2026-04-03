"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from "@xyflow/react";
import { cn } from "@/lib/utils";
import {
  buildPaperGraphFlow,
  type ApiGraphNode,
  type ApiGraphRel,
} from "@/lib/graph/paperGraphFlow";
import { commandCenterNodeTypes } from "./graphNodes";

function FitView({ layoutKey }: { layoutKey: string }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      fitView({ padding: 0.12, duration: 280 });
    });
    return () => cancelAnimationFrame(id);
  }, [fitView, layoutKey]);
  return null;
}

type Props = {
  graphNodes: ApiGraphNode[];
  relationships: ApiGraphRel[];
  height: number;
  showMiniMap?: boolean;
  className?: string;
};

function paperGraphDataSignature(
  graphNodes: ApiGraphNode[],
  relationships: ApiGraphRel[],
  height: number
) {
  const nodePart = graphNodes.map((n) => n.id).join("\u0000");
  const relPart = relationships
    .map((r, i) => `${r.start}\u0000${r.end}\u0000${r.type}\u0000${r.id ?? i}`)
    .join("\u0001");
  return `${height}\u0002${nodePart}\u0002${relPart}`;
}

function PaperGraphInner({
  graphNodes,
  relationships,
  height,
  showMiniMap,
}: Props) {
  /** 仅用拓扑签名驱动 layout，避免父组件每次 render 传入新数组引用导致死循环 */
  const dataSignature = useMemo(
    () => paperGraphDataSignature(graphNodes, relationships, height),
    [graphNodes, relationships, height]
  );

  const layout = useMemo(() => {
    return buildPaperGraphFlow(graphNodes, relationships, 900, height);
  }, [dataSignature]);

  const [nodes, setNodes, onNodesChange] = useNodesState(layout.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layout.edges);

  useEffect(() => {
    setNodes(layout.nodes);
    setEdges(layout.edges);
  }, [layout, setNodes, setEdges]);

  const layoutKey = dataSignature;

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodeTypes={commandCenterNodeTypes}
      minZoom={0.12}
      maxZoom={1.5}
      proOptions={{ hideAttribution: true }}
      className="bg-brand-graph-pane"
      style={{ width: "100%", height }}
    >
      <Background gap={14} size={1} />
      <Controls showInteractive={false} position="bottom-right" />
      {showMiniMap ? (
        <MiniMap
          className="!bg-slate-900 !border-slate-700"
          maskColor="rgba(15, 23, 42, 0.75)"
        />
      ) : null}
      <FitView layoutKey={layoutKey} />
    </ReactFlow>
  );
}

export function PaperGraphView({
  graphNodes,
  relationships,
  height,
  showMiniMap = true,
  className,
}: Props) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <div
        className={cn(
          "w-full animate-pulse rounded-lg border border-slate-800 bg-slate-900",
          className
        )}
        style={{ height }}
        aria-hidden
      />
    );
  }

  return (
    <div
      className={cn(
        "w-full overflow-hidden rounded-lg border border-slate-800 bg-slate-950",
        className
      )}
      style={{ height }}
    >
      <ReactFlowProvider>
        <PaperGraphInner
          graphNodes={graphNodes}
          relationships={relationships}
          height={height}
          showMiniMap={showMiniMap}
        />
      </ReactFlowProvider>
    </div>
  );
}
