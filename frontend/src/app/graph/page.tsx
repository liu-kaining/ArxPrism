"use client";

import { Suspense, useState, useEffect, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { paperApi } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { Search, Filter, Network } from "lucide-react";
import toast from "react-hot-toast";
import { PaperGraphView } from "@/components/graph/PaperGraphView";
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

  const fetchGraph = async (arxivId: string) => {
    if (!arxivId.trim()) {
      toast.error("请输入 arXiv ID");
      return;
    }

    setIsLoading(true);
    setError(null);

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

              {/* Legend */}
              <div className="space-y-2">
                <label className="text-sm font-medium">图例</label>
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
            </CardContent>
          </Card>

          {/* Graph Visualization */}
          <Card className="border-border bg-card shadow-sm lg:col-span-3">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Network className="w-5 h-5" />
                图谱可视化
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-sm text-muted-foreground mb-3">
                可拖拽画布、缩放；共 {filteredNodes.length} 个节点、
                {filteredRelationships.length} 条关系
              </p>
              <PaperGraphView
                graphNodes={filteredNodes}
                relationships={filteredRelationships}
                height={520}
                showMiniMap
              />
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
