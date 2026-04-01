"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { paperApi } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { Search, Filter, Network } from "lucide-react";
import toast from "react-hot-toast";

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

export default function GraphPage() {
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

  // Get unique node types
  const nodeTypes = Array.from(new Set(nodes.flatMap((n) => n.labels || [])));

  // Filter nodes
  const filteredNodes =
    nodeTypeFilter === "all"
      ? nodes
      : nodes.filter((n) => n.labels?.includes(nodeTypeFilter));

  // Get filtered relationships (only those between filtered nodes)
  const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
  const filteredRelationships = relationships.filter(
    (r) => filteredNodeIds.has(r.start) && filteredNodeIds.has(r.end)
  );

  const getNodeColor = (labels: string[] | undefined) => {
    const label = labels?.[0] || "Unknown";
    const colors: Record<string, string> = {
      Paper: "#ff6b6b",
      Method: "#4ecdc4",
      Author: "#45b7d1",
      Dataset: "#f7b731",
      Metric: "#a55eea",
      Innovation: "#778ca3",
      Limitation: "#778ca3",
    };
    return colors[label] || "#95a5a6";
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">知识图谱</h1>
        <p className="text-muted-foreground mt-1">
          探索论文相关的知识图谱节点和关系
        </p>
      </div>

      {/* Search */}
      <Card>
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
        <Card>
          <CardContent className="py-12">
            <Skeleton className="h-96 w-full" />
          </CardContent>
        </Card>
      ) : nodes.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Filters */}
          <Card className="lg:col-span-1">
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
          <Card className="lg:col-span-3">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Network className="w-5 h-5" />
                图谱可视化
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Placeholder for React Flow */}
              <div className="border rounded-lg min-h-[500px] bg-muted/50 flex items-center justify-center">
                <div className="text-center">
                  <p className="text-muted-foreground mb-4">
                    交互式图谱 (开发中)
                  </p>
                  <p className="text-sm text-muted-foreground mb-8">
                    显示 {filteredNodes.length} 个节点，{filteredRelationships.length} 条关系
                  </p>

                  {/* Simple node list */}
                  <div className="max-w-md mx-auto text-left">
                    {filteredNodes.slice(0, 10).map((node) => (
                      <div
                        key={node.id}
                        className="flex items-center gap-2 py-1"
                      >
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: getNodeColor(node.labels) }}
                        />
                        <span className="text-sm truncate flex-1">
                          {node.properties.original_name ||
                            node.properties.title ||
                            node.id}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {node.labels?.[0]}
                        </span>
                      </div>
                    ))}
                    {filteredNodes.length > 10 && (
                      <p className="text-xs text-muted-foreground text-center mt-2">
                        还有 {filteredNodes.length - 10} 个节点...
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : (
        <Card>
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
