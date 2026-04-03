"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { evolutionApi, type EvolutionTreeLink } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Search, GitBranch } from "lucide-react";
import toast from "react-hot-toast";
import { EvolutionGraphView } from "@/components/graph/EvolutionGraphView";

interface EvolutionNode {
  id: string;
  name: string;
  generation: number;
}

function EvolutionPageContent() {
  const searchParams = useSearchParams();
  const initialMethod = searchParams.get("method") || "";

  const [methodName, setMethodName] = useState(initialMethod);
  const [isLoading, setIsLoading] = useState(false);
  const [nodes, setNodes] = useState<EvolutionNode[]>([]);
  const [links, setLinks] = useState<EvolutionTreeLink[]>([]);
  const [error, setError] = useState<string | null>(null);

  const searchEvolution = async (method: string) => {
    if (!method.trim()) {
      toast.error("请输入方法名称");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const data = await evolutionApi.getEvolutionTree(method);
      setNodes(data.nodes);
      setLinks(data.links);

      if (data.nodes.length === 0) {
        toast.error(`未找到方法 "${method}" 的进化树`);
      }
    } catch (err) {
      setError(String(err));
      toast.error("获取进化树失败");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (initialMethod) {
      searchEvolution(initialMethod);
    }
  }, [initialMethod]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">技术进化树</h1>
        <p className="text-muted-foreground mt-1">
          查看方法之间的 IMPROVES_UPON 技术谱系关系
        </p>
      </div>

      {/* Search */}
      <Card>
        <CardContent className="pt-6">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              searchEvolution(methodName);
            }}
            className="flex gap-2"
          >
            <div className="relative flex-1">
              <GitBranch className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="输入方法名称，如: RAFT, WAFT, FlowFormer"
                value={methodName}
                onChange={(e) => setMethodName(e.target.value)}
                className="pl-10"
              />
            </div>
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
            <div className="flex justify-center">
              <Skeleton className="h-64 w-64 rounded-full" />
            </div>
          </CardContent>
        </Card>
      ) : nodes.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>
              {methodName} 的进化树 ({nodes.length} 个方法)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Stats */}
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="p-4 rounded-lg bg-primary/10 text-center">
                <p className="text-2xl font-bold text-primary">
                  {nodes.filter((n) => n.generation === 0).length}
                </p>
                <p className="text-sm text-muted-foreground">目标方法</p>
              </div>
              <div className="p-4 rounded-lg bg-secondary text-center">
                <p className="text-2xl font-bold">
                  {nodes.filter((n) => n.generation < 0).length}
                </p>
                <p className="text-sm text-muted-foreground">祖先节点</p>
              </div>
              <div className="p-4 rounded-lg bg-accent text-center">
                <p className="text-2xl font-bold">
                  {nodes.filter((n) => n.generation > 0).length}
                </p>
                <p className="text-sm text-muted-foreground">后代节点</p>
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">
                按代数分列：左侧为祖先，中间为目标方法，右侧为改进该方法的后继；可横向滚动宽图。
              </p>
              <EvolutionGraphView
                nodes={nodes}
                links={links}
                height={440}
                showMiniMap
              />
            </div>

            {/* Node List */}
            <div className="mt-6">
              <h4 className="font-medium mb-3">方法列表</h4>
              <div className="flex flex-wrap gap-2">
                {nodes.map((node) => (
                  <span
                    key={node.id}
                    className={`px-3 py-1 rounded-full text-sm ${
                      node.generation === 0
                        ? "bg-primary text-primary-foreground"
                        : node.generation < 0
                        ? "bg-secondary text-secondary-foreground"
                        : "bg-accent"
                    }`}
                  >
                    {node.name}
                  </span>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-12 text-center">
            <GitBranch className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
              输入方法名称查询其技术进化树
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function EvolutionPage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-6">
          <Skeleton className="h-10 w-72" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full rounded-xl" />
        </div>
      }
    >
      <EvolutionPageContent />
    </Suspense>
  );
}
