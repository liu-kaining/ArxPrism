"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { paperApi, Paper } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  ArrowLeft,
  ExternalLink,
  Calendar,
  User,
  Lightbulb,
  AlertTriangle,
  Beaker,
  Database,
  TrendingUp,
  GitBranch,
} from "lucide-react";
import { formatDate, cn } from "@/lib/utils";
import toast from "react-hot-toast";

interface GraphData {
  nodes: any[];
  relationships: any[];
}

export default function PaperDetailPage() {
  const params = useParams();
  const arxivId = params.arxivId as string;

  const [paper, setPaper] = useState<Paper | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const [paperDetail, graph] = await Promise.all([
          paperApi.getPaperDetail(arxivId),
          paperApi.getPaperGraph(arxivId),
        ]);
        setPaper(paperDetail.paper);
        setGraphData(graph);
      } catch (err) {
        setError(String(err));
        toast.error("加载论文详情失败");
      } finally {
        setIsLoading(false);
      }
    };

    if (arxivId) {
      fetchData();
    }
  }, [arxivId]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-64" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (error || !paper) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive">加载失败: {error}</p>
        <Link href="/papers" className="mt-4 inline-block">
          <Button variant="outline">返回论文列表</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Link href="/papers">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-3xl font-bold leading-tight">{paper.title}</h1>
          <div className="flex items-center gap-4 mt-3 text-muted-foreground">
            <span className="flex items-center gap-1">
              <User className="w-4 h-4" />
              {paper.authors?.join(", ")}
            </span>
            <span className="flex items-center gap-1">
              <Calendar className="w-4 h-4" />
              {formatDate(paper.published_date)}
            </span>
            <a
              href={`https://arxiv.org/abs/${arxivId}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button variant="ghost" size="sm">
                <ExternalLink className="w-4 h-4 mr-1" />
                arXiv
              </Button>
            </a>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Paper Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Core Problem */}
          {paper.core_problem && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span className="text-2xl">🎯</span> 核心问题
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-lg leading-relaxed">{paper.core_problem}</p>
              </CardContent>
            </Card>
          )}

          {/* Proposed Method */}
          {paper.proposed_method && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <span className="text-2xl">🔧</span> 提出的方法
                  </CardTitle>
                  {paper.proposed_method && (
                    <Link href={`/evolution?method=${encodeURIComponent(paper.proposed_method)}`}>
                      <Button variant="outline" size="sm">
                        <GitBranch className="w-4 h-4 mr-1" />
                        查看进化树
                      </Button>
                    </Link>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-lg font-medium text-primary">
                  {paper.proposed_method}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Innovations & Limitations */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Innovations */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Lightbulb className="w-5 h-5 text-yellow-500" />
                  创新点
                </CardTitle>
              </CardHeader>
              <CardContent>
                {paper.innovations?.length > 0 ? (
                  <ul className="space-y-2">
                    {paper.innovations.map((item, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-green-500 mt-1">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-muted-foreground">暂无数据</p>
                )}
              </CardContent>
            </Card>

            {/* Limitations */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-orange-500" />
                  局限性
                </CardTitle>
              </CardHeader>
              <CardContent>
                {paper.limitations?.length > 0 ? (
                  <ul className="space-y-2">
                    {paper.limitations.map((item, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-orange-500 mt-1">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-muted-foreground">暂无数据</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Experiment Data */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Beaker className="w-5 h-5 text-purple-500" />
                实验数据
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Baselines */}
              {paper.baselines?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4" />
                    击败的基线方法
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {paper.baselines.map((baseline) => (
                      <span
                        key={baseline}
                        className="px-3 py-1 rounded-full bg-secondary text-sm"
                      >
                        {baseline}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Datasets */}
              {paper.datasets?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                    <Database className="w-4 h-4" />
                    使用的数据集
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {paper.datasets.map((dataset) => (
                      <span
                        key={dataset}
                        className="px-3 py-1 rounded-full bg-accent text-sm"
                      >
                        {dataset}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Metrics */}
              {paper.metrics?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-2">评估指标</h4>
                  <div className="flex flex-wrap gap-2">
                    {paper.metrics.map((metric) => (
                      <span
                        key={metric}
                        className="px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium"
                      >
                        {metric}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {!paper.baselines?.length && !paper.datasets?.length && !paper.metrics?.length && (
                <p className="text-muted-foreground">暂无实验数据</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Knowledge Graph */}
        <div className="lg:col-span-1">
          <Card className="sticky top-20">
            <CardHeader>
              <CardTitle>🔗 知识图谱</CardTitle>
            </CardHeader>
            <CardContent>
              {graphData && graphData.nodes?.length > 0 ? (
                <div className="space-y-4">
                  {/* Stats */}
                  <div className="grid grid-cols-2 gap-4 text-center">
                    <div className="p-3 rounded-lg bg-accent">
                      <p className="text-2xl font-bold">{graphData.nodes.length}</p>
                      <p className="text-xs text-muted-foreground">节点</p>
                    </div>
                    <div className="p-3 rounded-lg bg-accent">
                      <p className="text-2xl font-bold">
                        {graphData.relationships?.length || 0}
                      </p>
                      <p className="text-xs text-muted-foreground">关系</p>
                    </div>
                  </div>

                  {/* Node Types */}
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium">节点类型</h4>
                    <div className="flex flex-wrap gap-2">
                      {Array.from(
                        new Set(graphData.nodes.map((n) => n.labels?.[0] || "Unknown"))
                      ).map((label) => (
                        <span
                          key={label}
                          className="px-2 py-1 text-xs rounded bg-primary/10"
                        >
                          {label}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Graph Placeholder */}
                  <div className="aspect-square bg-muted rounded-lg flex items-center justify-center">
                    <p className="text-muted-foreground text-sm">
                      图谱预览 (开发中)
                    </p>
                  </div>

                  <Link href={`/graph?paper=${arxivId}`} className="block">
                    <Button className="w-full">
                      展开交互式图谱
                      <ExternalLink className="w-4 h-4 ml-2" />
                    </Button>
                  </Link>
                </div>
              ) : (
                <p className="text-muted-foreground text-center py-8">
                  暂无图谱数据
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
