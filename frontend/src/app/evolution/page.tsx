"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import {
  evolutionApi,
  type EvolutionMethodEntry,
  type EvolutionTreeLink,
} from "@/lib/api/client";
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
  const [indexLoading, setIndexLoading] = useState(true);
  const [withEvolution, setWithEvolution] = useState<EvolutionMethodEntry[]>(
    []
  );
  const [otherMethods, setOtherMethods] = useState<EvolutionMethodEntry[]>(
    []
  );

  const searchEvolution = async (method: string, displayLabel?: string) => {
    const key = method.trim();
    if (!key) {
      toast.error("请输入方法名称");
      return;
    }

    setIsLoading(true);
    setError(null);
    if (displayLabel) {
      setMethodName(displayLabel);
    }

    try {
      const data = await evolutionApi.getEvolutionTree(key);
      setNodes(data.nodes);
      setLinks(data.links);

      if (data.nodes.length === 0) {
        toast.error(`未找到方法 "${displayLabel || key}" 的进化树`);
      }
    } catch (err) {
      setError(String(err));
      toast.error("获取进化树失败");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setIndexLoading(true);
      try {
        const idx = await evolutionApi.listEvolutionMethods();
        if (!cancelled) {
          setWithEvolution(idx.with_evolution);
          setOtherMethods(idx.other_methods);
        }
      } catch {
        if (!cancelled) {
          setWithEvolution([]);
          setOtherMethods([]);
        }
      } finally {
        if (!cancelled) setIndexLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (initialMethod) {
      searchEvolution(initialMethod);
    }
  }, [initialMethod]);

  return (
    <div className="warm-page space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-stone-900">
          技术进化树
        </h1>
        <p className="mt-1 text-sm text-stone-600">
          以某一方法为中心，展示 Neo4j 中{" "}
          <span className="font-mono text-amber-800">IMPROVES_UPON</span>{" "}
          谱系。下图库无法把多棵互不连通的树「一次画在一张图」上，请从下方列表点选或搜索。
        </p>
      </div>

      {/* Method index — 解决「不知道查啥」 */}
      <Card className="border-border bg-card shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-base text-card-foreground">
            库里的方法（可点选）
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            「有谱系」表示至少有一条 IMPROVES_UPON；萃取里写出 baselines_beaten
            后才会出现边。
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {indexLoading ? (
            <div className="flex flex-wrap gap-2">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton
                  key={i}
                  className="h-8 w-24 rounded-full border border-border bg-muted"
                />
              ))}
            </div>
          ) : (
            <>
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-amber-800">
                  有谱系（推荐）
                </p>
                {withEvolution.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    暂无。请先跑论文萃取流水线，且 LLM 需在结果中给出
                    baselines_beaten，才会写入 IMPROVES_UPON。
                  </p>
                ) : (
                  <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto pr-1">
                    {withEvolution.map((m) => (
                      <button
                        key={m.name_key}
                        type="button"
                        disabled={isLoading}
                        onClick={() =>
                          searchEvolution(m.name_key, m.label)
                        }
                        className="rounded-full border border-amber-300/90 bg-amber-50 px-3 py-1.5 text-left text-xs font-medium text-amber-950 transition-colors hover:bg-amber-100 disabled:opacity-50"
                        title={`查询键: ${m.name_key} · ${m.edge_count ?? 0} 条相关边`}
                      >
                        {m.label}
                        <span className="ml-1 font-mono text-[10px] text-amber-700">
                          ({m.edge_count})
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  仅有方法节点（无 IMPROVES_UPON 边）
                </p>
                {otherMethods.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    无。若刚清空过图库，请先重新入库论文。
                  </p>
                ) : (
                  <div className="flex max-h-32 flex-wrap gap-2 overflow-y-auto pr-1">
                    {otherMethods.map((m) => (
                      <button
                        key={m.name_key}
                        type="button"
                        disabled={isLoading}
                        onClick={() =>
                          searchEvolution(m.name_key, m.label)
                        }
                        className="rounded-full border border-border bg-muted/80 px-3 py-1.5 text-xs text-foreground transition-colors hover:bg-muted disabled:opacity-50"
                        title={`查询键: ${m.name_key}`}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Search */}
      <Card className="border-border bg-card shadow-sm">
        <CardContent className="pt-6">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              searchEvolution(methodName);
            }}
            className="flex gap-2"
          >
            <div className="relative flex-1">
              <GitBranch className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 transform text-muted-foreground" />
              <Input
                placeholder="或手动输入：与图中 Method.name（归一化键）一致更易命中，也可试展示名"
                value={methodName}
                onChange={(e) => setMethodName(e.target.value)}
                className="pl-10"
              />
            </div>
            <Button type="submit" disabled={isLoading}>
              <Search className="mr-2 h-4 w-4" />
              查询
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Results */}
      {isLoading ? (
        <Card className="border-border bg-card shadow-sm">
          <CardContent className="py-12">
            <div className="flex justify-center">
              <Skeleton className="h-64 w-64 rounded-full border border-border bg-muted" />
            </div>
          </CardContent>
        </Card>
      ) : nodes.length > 0 ? (
        <Card className="border-border bg-card shadow-sm">
          <CardHeader>
            <CardTitle className="text-card-foreground">
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
        <Card className="border-border bg-card shadow-sm">
          <CardContent className="py-12 text-center">
            <GitBranch className="mx-auto mb-4 h-16 w-16 text-muted-foreground" />
            <p className="text-muted-foreground">
              从上方列表点选一个方法，或输入名称后查询。
            </p>
            {error ? (
              <p className="mt-2 font-mono text-xs text-destructive">{error}</p>
            ) : null}
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
        <div className="warm-page space-y-6">
          <Skeleton className="h-10 w-72 rounded-lg bg-muted" />
          <Skeleton className="h-32 w-full rounded-xl bg-muted" />
          <Skeleton className="h-64 w-full rounded-xl bg-muted" />
        </div>
      }
    >
      <EvolutionPageContent />
    </Suspense>
  );
}
