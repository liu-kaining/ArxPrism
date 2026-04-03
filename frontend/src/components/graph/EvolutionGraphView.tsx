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
  buildEvolutionFlow,
  type EvolutionApiLink,
  type EvolutionApiNode,
} from "@/lib/graph/evolutionFlow";
import { evolutionNodeTypes } from "./graphNodes";
import { evolutionEdgeTypes } from "./EvolutionHoverEdge";

function FitView({ layoutKey }: { layoutKey: string }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      fitView({ padding: 0.15, duration: 280 });
    });
    return () => cancelAnimationFrame(id);
  }, [fitView, layoutKey]);
  return null;
}

type Props = {
  nodes: EvolutionApiNode[];
  links: EvolutionApiLink[];
  height: number;
  showMiniMap?: boolean;
  className?: string;
};

function evolutionDataSignature(
  nodes: EvolutionApiNode[],
  links: EvolutionApiLink[],
  height: number
) {
  const nodePart = nodes
    .map((n) => `${n.id}\u0000${n.generation}\u0000${n.name}`)
    .join("\u0001");
  const linkPart = links
    .map((l, i) => {
      const m = (l.metrics ?? []).join("\u0004");
      const ds = (l.datasets ?? []).join("\u0004");
      return `${l.source}\u0000${l.target}\u0000${i}\u0000${l.relationshipType ?? ""}\u0000${m}\u0000${ds}`;
    })
    .join("\u0002");
  return `${height}\u0003${nodePart}\u0003${linkPart}`;
}

function EvolutionGraphInner({
  nodes,
  links,
  height,
  showMiniMap,
}: Props) {
  const dataSignature = useMemo(
    () => evolutionDataSignature(nodes, links, height),
    [nodes, links, height]
  );

  const layout = useMemo(
    () => buildEvolutionFlow(nodes, links, 1000, height),
    [dataSignature]
  );

  const [rfNodes, setRfNodes, onNodesChange] = useNodesState(layout.nodes);
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState(layout.edges);

  useEffect(() => {
    setRfNodes(layout.nodes);
    setRfEdges(layout.edges);
  }, [layout, setRfNodes, setRfEdges]);

  const layoutKey = dataSignature;

  const innerWidth = Math.max(layout.contentWidth, 640);

  return (
    <div
      className="overflow-x-auto"
      style={{ width: "100%", height }}
    >
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={evolutionNodeTypes}
        edgeTypes={evolutionEdgeTypes}
        minZoom={0.1}
        maxZoom={1.4}
        proOptions={{ hideAttribution: true }}
        className="bg-transparent"
        style={{ width: innerWidth, height }}
      >
        <Background gap={16} size={1} />
        <Controls showInteractive={false} position="bottom-right" />
        {showMiniMap ? (
          <MiniMap
            className="!border-amber-200/90 !bg-white/95"
            maskColor="rgba(245, 240, 232, 0.75)"
          />
        ) : null}
        <FitView layoutKey={layoutKey} />
      </ReactFlow>
    </div>
  );
}

export function EvolutionGraphView({
  nodes,
  links,
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
          "w-full animate-pulse rounded-lg border border-amber-200/80 bg-stone-100",
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
        "w-full overflow-hidden rounded-lg border border-amber-200/80 bg-[#ebe6dd]",
        className
      )}
      style={{ height }}
    >
      <ReactFlowProvider>
        <EvolutionGraphInner
          nodes={nodes}
          links={links}
          height={height}
          showMiniMap={showMiniMap}
        />
      </ReactFlowProvider>
    </div>
  );
}
