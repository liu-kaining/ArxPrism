"use client";

import { useState, useEffect } from "react";
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
  Target,
  Wrench,
  Sparkles,
  Download,
  Copy,
  FileText,
} from "lucide-react";
import { formatDate } from "@/lib/utils";
import toast from "react-hot-toast";
import { PaperGraphView } from "@/components/graph/PaperGraphView";
import { EMPTY_GRAPH_RELATIONSHIPS } from "@/lib/graph/paperGraphFlow";

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

  const absUrl = `https://arxiv.org/abs/${arxivId}`;
  const pdfUrl = `https://arxiv.org/pdf/${arxivId}.pdf`;

  const copyText = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`已复制${label}`);
    } catch {
      toast.error("复制失败");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Link href="/papers">
          <Button variant="ghost" size="icon" className="rounded-xl">
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div className="flex-1 min-w-0 space-y-4">
          <h1 className="text-3xl font-bold leading-tight">{paper.title}</h1>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5 min-w-0">
              <User className="w-4 h-4 shrink-0" />
              <span className="truncate">
                {paper.authors?.length
                  ? paper.authors.join(", ")
                  : "作者未从图谱抽取"}
              </span>
            </span>
            <span className="flex items-center gap-1.5 shrink-0">
              <Calendar className="w-4 h-4" />
              {formatDate(paper.published_date)}
            </span>
            <span className="rounded-md bg-muted px-2 py-0.5 font-mono text-xs text-foreground">
              arXiv:{arxivId}
            </span>
          </div>

          {/* 高亮：官方页面 + PDF，避免与灰色元信息混在一起看不清 */}
          <Card className="border-2 border-sky-500/40 bg-gradient-to-br from-sky-500/[0.12] via-background to-background shadow-md">
            <CardContent className="pt-5 pb-5">
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                <div>
                  <p className="text-base font-semibold text-sky-900 dark:text-sky-100">
                    原文地址与 PDF
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    在 arXiv 打开论文页，或直接下载官方 PDF（新标签页）
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 mt-3 sm:mt-0">
                  <a
                    href={absUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex"
                  >
                    <Button
                      size="lg"
                      className="rounded-xl gap-2 font-semibold shadow-sm"
                    >
                      <ExternalLink className="w-5 h-5" />
                      打开 arXiv 页面
                    </Button>
                  </a>
                  <a
                    href={pdfUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex"
                  >
                    <Button
                      size="lg"
                      variant="secondary"
                      className="rounded-xl gap-2 font-semibold border-2 border-sky-500/40 shadow-sm"
                    >
                      <Download className="w-5 h-5" />
                      下载 PDF
                    </Button>
                  </a>
                </div>
              </div>
              <div className="mt-4 space-y-2 rounded-lg border bg-muted/40 p-3">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
                  <span className="text-xs font-medium text-muted-foreground shrink-0 w-28">
                    Abs 链接
                  </span>
                  <code className="flex-1 break-all text-xs sm:text-sm text-foreground">
                    {absUrl}
                  </code>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="shrink-0 gap-1"
                    onClick={() => copyText(absUrl, "Abs 链接")}
                  >
                    <Copy className="w-3.5 h-3.5" />
                    复制
                  </Button>
                </div>
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
                  <span className="text-xs font-medium text-muted-foreground shrink-0 w-28">
                    PDF 直链
                  </span>
                  <code className="flex-1 break-all text-xs sm:text-sm text-foreground">
                    {pdfUrl}
                  </code>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="shrink-0 gap-1"
                    onClick={() => copyText(pdfUrl, "PDF 链接")}
                  >
                    <Copy className="w-3.5 h-3.5" />
                    复制
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 stagger-children">
        {/* Left Column: Paper Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* arXiv 摘要（入库时写入 Neo4j，非全文；全文请用上方 PDF） */}
          {paper.summary?.trim() ? (
            <Card className="border-0 shadow-lg overflow-hidden">
              <CardHeader className="pb-3 bg-gradient-to-r from-violet-500/10 to-transparent">
                <CardTitle className="flex items-center gap-3 text-lg">
                  <div className="w-10 h-10 rounded-xl bg-violet-500/15 flex items-center justify-center">
                    <FileText className="w-5 h-5 text-violet-600 dark:text-violet-400" />
                  </div>
                  arXiv 摘要
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-base leading-relaxed text-muted-foreground whitespace-pre-wrap">
                  {paper.summary.trim()}
                </p>
              </CardContent>
            </Card>
          ) : null}

          {/* Core Problem */}
          {paper.core_problem && (
            <Card className="border-0 shadow-lg overflow-hidden">
              <CardHeader className="pb-3 bg-gradient-to-r from-primary/5 to-transparent">
                <CardTitle className="flex items-center gap-3 text-lg">
                  <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                    <Target className="w-5 h-5 text-primary" />
                  </div>
                  核心问题
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-lg leading-relaxed">{paper.core_problem}</p>
              </CardContent>
            </Card>
          )}

          {/* Proposed Method */}
          {paper.proposed_method && (
            <Card className="border-0 shadow-lg overflow-hidden">
              <CardHeader className="pb-3 bg-gradient-to-r from-primary/5 to-transparent">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-3 text-lg">
                    <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                      <Wrench className="w-5 h-5 text-primary" />
                    </div>
                    提出的方法
                  </CardTitle>
                  {paper.proposed_method && (
                    <Link href={`/evolution?method=${encodeURIComponent(paper.proposed_method)}`}>
                      <Button variant="outline" size="sm" className="rounded-lg">
                        <GitBranch className="w-4 h-4 mr-1" />
                        查看进化树
                      </Button>
                    </Link>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-lg font-semibold text-gradient">
                  {paper.proposed_method}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Innovations & Limitations */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Innovations */}
            <Card className="border-0 shadow-lg overflow-hidden">
              <CardHeader className="pb-3 bg-gradient-to-r from-green-500/5 to-transparent">
                <CardTitle className="flex items-center gap-3 text-lg">
                  <div className="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center">
                    <Lightbulb className="w-5 h-5 text-green-500" />
                  </div>
                  创新点
                </CardTitle>
              </CardHeader>
              <CardContent>
                {(paper.innovations ?? []).length > 0 ? (
                  <ul className="space-y-3">
                    {(paper.innovations ?? []).map((item, i) => (
                      <li key={i} className="flex items-start gap-3">
                        <div className="w-2 h-2 rounded-full bg-green-500 mt-2 shrink-0" />
                        <span className="text-sm leading-relaxed">{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-muted-foreground">暂无数据</p>
                )}
              </CardContent>
            </Card>

            {/* Limitations */}
            <Card className="border-0 shadow-lg overflow-hidden">
              <CardHeader className="pb-3 bg-gradient-to-r from-orange-500/5 to-transparent">
                <CardTitle className="flex items-center gap-3 text-lg">
                  <div className="w-10 h-10 rounded-xl bg-orange-500/10 flex items-center justify-center">
                    <AlertTriangle className="w-5 h-5 text-orange-500" />
                  </div>
                  局限性
                </CardTitle>
              </CardHeader>
              <CardContent>
                {(paper.limitations ?? []).length > 0 ? (
                  <ul className="space-y-3">
                    {(paper.limitations ?? []).map((item, i) => (
                      <li key={i} className="flex items-start gap-3">
                        <div className="w-2 h-2 rounded-full bg-orange-500 mt-2 shrink-0" />
                        <span className="text-sm leading-relaxed">{item}</span>
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
          <Card className="border-0 shadow-lg overflow-hidden">
            <CardHeader className="pb-3 bg-gradient-to-r from-purple-500/5 to-transparent">
              <CardTitle className="flex items-center gap-3 text-lg">
                <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center">
                  <Beaker className="w-5 h-5 text-purple-500" />
                </div>
                实验数据
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* Baselines */}
              {(paper.baselines ?? []).length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-muted-foreground" />
                    击败的基线方法
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {(paper.baselines ?? []).map((baseline) => (
                      <span
                        key={baseline}
                        className="px-3 py-1.5 rounded-full bg-secondary text-sm"
                      >
                        {baseline}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Datasets */}
              {(paper.datasets ?? []).length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                    <Database className="w-4 h-4 text-muted-foreground" />
                    使用的数据集
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {(paper.datasets ?? []).map((dataset) => (
                      <span
                        key={dataset}
                        className="px-3 py-1.5 rounded-full bg-accent text-sm"
                      >
                        {dataset}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Metrics */}
              {(paper.metrics ?? []).length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-3">评估指标</h4>
                  <div className="flex flex-wrap gap-2">
                    {(paper.metrics ?? []).map((metric) => (
                      <span
                        key={metric}
                        className="px-3 py-1.5 rounded-full bg-primary/10 text-primary text-sm font-semibold"
                      >
                        {metric}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {!(paper.baselines ?? []).length &&
                !(paper.datasets ?? []).length &&
                !(paper.metrics ?? []).length && (
                <p className="text-muted-foreground">暂无实验数据</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Knowledge Graph */}
        <div className="lg:col-span-1">
          <Card className="border-0 shadow-lg sticky top-20 overflow-hidden">
            <CardHeader className="pb-3 bg-gradient-to-r from-primary/5 to-transparent">
              <CardTitle className="flex items-center gap-3 text-lg">
                <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                  <Sparkles className="w-5 h-5 text-primary" />
                </div>
                知识图谱
              </CardTitle>
            </CardHeader>
            <CardContent>
              {graphData && graphData.nodes?.length > 0 ? (
                <div className="space-y-4">
                  {/* Stats */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-4 rounded-xl bg-gradient-to-br from-primary/10 to-primary/5 text-center">
                      <p className="text-2xl font-bold">{graphData.nodes.length}</p>
                      <p className="text-xs text-muted-foreground">节点</p>
                    </div>
                    <div className="p-4 rounded-xl bg-gradient-to-br from-primary/10 to-primary/5 text-center">
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
                          className="px-2.5 py-1 text-xs rounded-full bg-primary/10"
                        >
                          {label}
                        </span>
                      ))}
                    </div>
                  </div>

                  <PaperGraphView
                    graphNodes={graphData.nodes}
                    relationships={
                      graphData.relationships ?? EMPTY_GRAPH_RELATIONSHIPS
                    }
                    height={300}
                    showMiniMap={false}
                    className="border-0 shadow-none"
                  />

                  <Link href={`/graph?paper=${arxivId}`} className="block">
                    <Button className="w-full rounded-xl">
                      展开交互式图谱
                      <ExternalLink className="w-4 h-4 ml-2" />
                    </Button>
                  </Link>
                </div>
              ) : (
                <div className="text-center py-12">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-muted flex items-center justify-center">
                    <Sparkles className="w-8 h-8 text-muted-foreground" />
                  </div>
                  <p className="text-muted-foreground">暂无图谱数据</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
