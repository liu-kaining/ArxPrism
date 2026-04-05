"use client";

import { Suspense, useState, useEffect, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { paperApi, graphApi } from "@/lib/api/client";
import type { ApiGraphNode } from "@/lib/graph/paperGraphFlow";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { Search, Filter, Network, RefreshCw } from "lucide-react";
import toast from "react-hot-toast";
import { PaperGraphView } from "@/components/graph/PaperGraphView";
import { NodeDetailPanel } from "@/components/graph/NodeDetailPanel";
import { GRAPH_LABEL_COLORS } from "@/lib/graph/paperGraphFlow";

interface GraphNode {
  id: string;
  labels: string[];
  properties: Record<string, any>;
}

interface GraphRelationship {
  id: string;
  type: string;
  start: string;
  end: string;
  properties: Record<string, any>;
}

function GraphPageContent() {
  const searchParams = useSearchParams();
  const paperId = searchParams.get("paper");

  const [paperArxivId, setPaperArxivId] = useState(paperId || "");
  const [isLoading, setIsLoading] = useState(false);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [relationships, setRelationships] = useState<GraphRelationship[]>([]);
  const [nodeTypeFilter, setNodeTypeFilter] = useState<string>("all");
  const [error, setError] = useState<string | null>(null);

  // Detail panel state
  const [selectedNode, setSelectedNode] = useState<ApiGraphNode | null>(null);
  const [detailPanelOpen, setDetailPanelOpen] = useState(false);

  // Subgraph expansion state
  const [expandingNode, setExpandingNode] = useState<string | null>(null);
  const [expandDepth, setExpandDepth] = useState<number>(2);

  const fetchGraph = async (arxivId: string) => {
    if (!arxivId.trim()) {
      toast.error("请输入 arXiv ID");
      return;
    }

    setIsLoading(true);
    setError(null);
    setSelectedNode(null);
    setDetailPanelOpen(false);

    try {
      const data = await paperApi.getPaperGraph(arxivId);
      setNodes(data.nodes);
      setRelationships(data.relationships);

      if (data.nodes.length === 0) {
        toast.error(`未找到论文 ${arxivId} 的图谱数据`);
      }
    } catch (err) {
      setError(String(err));
      toast.error("获取图谱失败");
    } finally {
      setIsLoading(false);
    }
  };

  // Handle clicking on a node to show details
  const handleNodeClick = (node: ApiGraphNode) => {
    setSelectedNode(node);
    setDetailPanelOpen(true);
  };

  // Handle expanding from a node
  const handleExpandNode = async (nodeId: string) => {
    setExpandingNode(nodeId);
    setIsLoading(true);

    try {
      const subgraph = await graphApi.getSubgraph(nodeId, expandDepth);

      // Merge new nodes
      const existingIds = new Set(nodes.map((n) => n.id));
      const newNodes = subgraph.nodes.filter((n) => !existingIds.has(n.id));
      setNodes((prev) => [...prev, ...newNodes]);

      // Merge new relationships
      const existingRels = new Set(
        relationships.map((r) => `${r.start}-${r.end}-${r.type}`)
      );
      const newRels = subgraph.relationships.filter(
        (r) => !existingRels.has(`${r.start}-${r.end}-${r.type}`)
      );
      setRelationships((prev) => [
        ...prev,
        ...newRels.map((r) => ({
          id: r.id,
          type: r.type,
          start: r.start,
          end: r.end,
          properties: r.properties || {},
        })),
      ]);

      toast.success(`Expanded: +${newNodes.length} nodes, +${newRels.length} edges`);
    } catch (err) {
      toast.error("Failed to expand subgraph");
    } finally {
      setExpandingNode(null);
      setIsLoading(false);
    }
  };

  // Reset to initial paper view
  const resetGraph = () => {
    if (paperId) {
      fetchGraph(paperId);
    }
  };

  useEffect(() => {
    if (paperId) {
      fetchGraph(paperId);
    }
  }, [paperId]);

  const nodeTypes = useMemo(
    () => Array.from(new Set(nodes.flatMap((n) => n.labels || []))),
    [nodes]
  );

  const filteredNodes = useMemo(() => {
    return nodeTypeFilter === "all"
      ? nodes
      : nodes.filter((n) => n.labels?.includes(nodeTypeFilter));
  }, [nodes, nodeTypeFilter]);

  const filteredRelationships = useMemo(() => {
    const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
    return relationships.filter(
      (r) => filteredNodeIds.has(r.start) && filteredNodeIds.has(r.end)
    );
  }, [relationships, filteredNodes]);

  const getNodeColor = (labels: string[] | undefined) => {
    const label = labels?.[0] || "Unknown";
    return GRAPH_LABEL_COLORS[label] || "#95a5a6";
  };

  const getEdgeColor = (edgeType: string): string => {
    const colors: Record<string, string> = {
      PROPOSES: "#06b6d4",      // cyan
      WRITTEN_BY: "#2563eb",    // blue
      ADDRESSES: "#d97706",     // amber
      EVALUATED_ON: "#ca8a04",  // yellow
      APPLIED_TO: "#7c3aed",    // violet
      IMPROVES_UPON: "#ea580c",  // orange
      EVOLVED_FROM: "#c026d3",  // fuchsia
      MEASURES: "#db2777",      // pink
    };
    return colors[edgeType] || "#475569";
  };

  return (
    <div className="warm-page space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-stone-900">知识图谱</h1>
        <p className="mt-1 text-muted-foreground">
          探索论文相关的知识图谱节点和关系
        </p>
      </div>

      {/* Search */}
      <Card className="border-border bg-card shadow-sm">
        <CardContent className="pt-6">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              fetchGraph(paperArxivId);
            }}
            className="flex gap-2"
          >
            <Input
              placeholder="输入 arXiv ID，如: 2506.02009"
              value={paperArxivId}
              onChange={(e) => setPaperArxivId(e.target.value)}
            />
            <Button type="submit" disabled={isLoading}>
              <Search className="w-4 h-4 mr-2" />
              查询
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Results */}
      {isLoading ? (
        <Card className="border-border bg-card shadow-sm">
          <CardContent className="py-12">
            <Skeleton className="h-96 w-full rounded-xl bg-muted" />
          </CardContent>
        </Card>
      ) : nodes.length > 0 ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
          {/* Filters */}
          <Card className="border-border bg-card shadow-sm lg:col-span-1">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Filter className="w-5 h-5" />
                筛选
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Stats */}
              <div className="grid grid-cols-2 gap-2 text-center">
                <div className="p-2 rounded bg-accent">
                  <p className="text-xl font-bold">{filteredNodes.length}</p>
                  <p className="text-xs text-muted-foreground">节点</p>
                </div>
                <div className="p-2 rounded bg-accent">
                  <p className="text-xl font-bold">{filteredRelationships.length}</p>
                  <p className="text-xs text-muted-foreground">关系</p>
                </div>
              </div>

              {/* Node Type Filter */}
              <div className="space-y-2">
                <label className="text-sm font-medium">节点类型</label>
                <Select value={nodeTypeFilter} onValueChange={setNodeTypeFilter}>
                  <SelectTrigger>
                    <SelectValue placeholder="全部类型" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部类型</SelectItem>
                    {nodeTypes.map((type) => (
                      <SelectItem key={type} value={type}>
                        {type}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Node Legend */}
              <div className="space-y-2">
                <label className="text-sm font-medium">节点类型</label>
                <div className="space-y-2">
                  {nodeTypes.map((type) => (
                    <div key={type} className="flex items-center gap-2">
                      <div
                        className="w-4 h-4 rounded"
                        style={{ backgroundColor: getNodeColor([type]) }}
                      />
                      <span className="text-sm">{type}</span>
                      <span className="text-xs text-muted-foreground">
                        ({nodes.filter((n) => n.labels?.includes(type)).length})
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Edge Legend */}
              <div className="space-y-2">
                <label className="text-sm font-medium">关系类型</label>
                <div className="space-y-2">
                  {Array.from(new Set(relationships.map((r) => r.type))).map((type) => (
                    <div key={type} className="flex items-center gap-2">
                      <div
                        className="w-4 h-4 rounded"
                        style={{ backgroundColor: getEdgeColor(type) }}
                      />
                      <span className="text-sm font-mono">{type}</span>
                      <span className="text-xs text-muted-foreground">
                        ({relationships.filter((r) => r.type === type).length})
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Graph Visualization */}
          <Card className="border-border bg-card shadow-sm lg:col-span-3">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <Network className="w-5 h-5" />
                  图谱可视化
                </CardTitle>
                <div className="flex items-center gap-2">
                  {/* Expand Depth Control */}
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-muted-foreground">Depth:</span>
                    <Select value={String(expandDepth)} onValueChange={(v) => setExpandDepth(Number(v))}>
                      <SelectTrigger className="h-7 w-16 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="1">1</SelectItem>
                        <SelectItem value="2">2</SelectItem>
                        <SelectItem value="3">3</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {/* Reset Button */}
                  {paperId && (
                    <Button variant="outline" size="sm" onClick={resetGraph} className="h-7 text-xs">
                      <RefreshCw className="mr-1 h-3 w-3" />
                      Reset
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-sm text-muted-foreground mb-3">
                可拖拽画布、缩放；点击节点查看详情或展开子图。共 {filteredNodes.length} 个节点、
                {filteredRelationships.length} 条关系
              </p>
              <div className={`relative ${detailPanelOpen ? "pr-96" : ""}`}>
                <PaperGraphView
                  graphNodes={filteredNodes}
                  relationships={filteredRelationships}
                  height={600}
                  showMiniMap
                  onNodeClick={handleNodeClick}
                />
                {/* Node Detail Panel */}
                <NodeDetailPanel
                  node={selectedNode}
                  isOpen={detailPanelOpen}
                  onClose={() => setDetailPanelOpen(false)}
                  onExpandNode={handleExpandNode}
                />
              </div>
            </CardContent>
          </Card>
        </div>
      ) : (
        <Card className="border-border bg-card shadow-sm">
          <CardContent className="py-12 text-center">
            <Network className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
              输入 arXiv ID 查询论文的知识图谱
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function GraphPage() {
  return (
    <Suspense
      fallback={
        <div className="warm-page space-y-6">
          <Skeleton className="h-10 w-64 rounded-lg bg-muted" />
          <Skeleton className="h-24 w-full rounded-xl bg-muted" />
          <Skeleton className="h-96 w-full rounded-xl bg-muted" />
        </div>
      }
    >
      <GraphPageContent />
    </Suspense>
  );
}
