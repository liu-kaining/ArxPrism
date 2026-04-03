"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
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
  GitBranch,
  Target,
  Wrench,
  Sparkles,
  Download,
  Copy,
  FileText,
  Brain,
} from "lucide-react";
import { cn, formatDate } from "@/lib/utils";
import toast from "react-hot-toast";
import { PaperGraphView } from "@/components/graph/PaperGraphView";
import { EMPTY_GRAPH_RELATIONSHIPS } from "@/lib/graph/paperGraphFlow";

const PaperPdfViewer = dynamic(
  () => import("@/components/papers/PaperPdfViewer"),
  {
    ssr: false,
    loading: () => (
      <div className="min-h-[min(72vh,760px)] rounded-2xl border border-stone-200/90 bg-stone-100/80 animate-pulse" />
    ),
  }
);

interface GraphData {
  nodes: any[];
  relationships: any[];
}

const shell =
  "rounded-2xl border border-stone-200/90 bg-white/95 text-stone-800 shadow-sm";

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
      <div className="warm-page space-y-6">
        <Skeleton className="h-10 w-2/3 rounded-lg bg-muted" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <Skeleton className="min-h-[520px] rounded-2xl bg-muted lg:col-span-8" />
          <Skeleton className="h-96 rounded-2xl bg-muted lg:col-span-4" />
        </div>
      </div>
    );
  }

  if (error || !paper) {
    return (
      <div className="warm-page py-12 text-center">
        <p className="text-destructive">加载失败: {error}</p>
        <Link href="/papers" className="mt-4 inline-block">
          <Button variant="outline">返回论文列表</Button>
        </Link>
      </div>
    );
  }

  const absUrl = `https://arxiv.org/abs/${arxivId}`;
  const pdfUrl = `https://arxiv.org/pdf/${arxivId}.pdf`;
  /** 内嵌阅读器走同源代理，避免 pdf.js Worker 跨域拉 arXiv 时出现 Failed to fetch */
  const pdfViewerUrl = `/arxiv-proxy/pdf/${encodeURIComponent(arxivId)}`;

  const copyText = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`已复制${label}`);
    } catch {
      toast.error("复制失败");
    }
  };

  return (
    <div className="warm-page space-y-5 md:space-y-6">
      {/* 顶栏：标题与元信息（不占左侧 PDF 列） */}
      <div className="mb-5 flex items-start gap-3">
        <Link href="/papers">
          <Button
            variant="outline"
            size="icon"
            className="shrink-0 rounded-xl border-stone-300 bg-white/90 text-stone-800 hover:bg-amber-50"
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div className="min-w-0 flex-1 space-y-2">
          <h1 className="text-xl font-semibold leading-snug text-stone-900 md:text-2xl">
            {paper.title}
          </h1>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-stone-600">
            <span className="flex min-w-0 items-center gap-1.5">
              <User className="h-4 w-4 shrink-0 text-amber-800/70" />
              <span className="truncate">
                {paper.authors?.length
                  ? paper.authors.join(", ")
                  : "作者未从图谱抽取"}
              </span>
            </span>
            <span className="flex items-center gap-1.5">
              <Calendar className="h-4 w-4 text-amber-800/70" />
              {formatDate(paper.published_date)}
            </span>
            <span className="rounded-md border border-amber-200/80 bg-amber-50/90 px-2 py-0.5 font-mono text-xs text-amber-950">
              arXiv:{arxivId}
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-12">
        {/* 左：PDF 独占大列 */}
        <div className="lg:col-span-8 lg:sticky lg:top-4 lg:self-start">
          <PaperPdfViewer
            fileUrl={pdfViewerUrl}
            fallbackPdfHref={pdfUrl}
            className="min-h-[min(78vh,820px)] lg:min-h-[calc(100vh-7.5rem)]"
          />
        </div>

        {/* 右：高度随内容，不强行 min-h 撑满视口（避免说明条下大块空白）；过长时内部滚动 */}
        <div className="lg:col-span-4 lg:sticky lg:top-4 lg:self-start">
          <div className="space-y-4 lg:max-h-[calc(100vh-5rem)] lg:overflow-y-auto lg:rounded-2xl lg:border lg:border-stone-200/80 lg:bg-gradient-to-b lg:from-[#faf7f2] lg:to-[#efe9df] lg:p-4 lg:pr-5 lg:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.55)]">
            <Card className={shell}>
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-semibold text-stone-900">
                原文地址与 PDF
              </CardTitle>
              <p className="text-xs text-stone-500">
                左侧为内嵌阅读器；也可在官方站点打开或下载核对。
              </p>
            </CardHeader>
            <CardContent className="space-y-3 pt-0">
              <div className="flex flex-wrap gap-2">
                <a
                  href={absUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex"
                >
                  <Button
                    size="sm"
                    className="rounded-lg bg-amber-800 text-amber-50 hover:bg-amber-900"
                  >
                    <ExternalLink className="mr-1.5 h-4 w-4" />
                    arXiv 页面
                  </Button>
                </a>
                <a
                  href={pdfUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex"
                >
                  <Button
                    size="sm"
                    variant="outline"
                    className="rounded-lg border-stone-300 bg-white text-stone-800 hover:bg-amber-50"
                  >
                    <Download className="mr-1.5 h-4 w-4" />
                    下载 PDF
                  </Button>
                </a>
              </div>
              <div className="mt-3 space-y-2 rounded-lg border border-stone-200/80 bg-stone-50/80 p-3">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
                  <span className="w-24 shrink-0 text-xs font-medium text-stone-500">
                    Abs
                  </span>
                  <code className="flex-1 break-all text-xs text-stone-800">
                    {absUrl}
                  </code>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="shrink-0 border-stone-300 bg-white"
                    onClick={() => copyText(absUrl, "Abs 链接")}
                  >
                    <Copy className="mr-1 h-3.5 w-3.5" />
                    复制
                  </Button>
                </div>
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
                  <span className="w-24 shrink-0 text-xs font-medium text-stone-500">
                    PDF
                  </span>
                  <code className="flex-1 break-all text-xs text-stone-800">
                    {pdfUrl}
                  </code>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="shrink-0 border-stone-300 bg-white"
                    onClick={() => copyText(pdfUrl, "PDF 链接")}
                  >
                    <Copy className="mr-1 h-3.5 w-3.5" />
                    复制
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className={shell}>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base font-semibold text-stone-900">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-100 text-amber-900">
                  <Sparkles className="h-4 w-4" />
                </span>
                知识图谱
              </CardTitle>
            </CardHeader>
            <CardContent>
              {graphData && graphData.nodes?.length > 0 ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    <div className="rounded-xl border border-stone-200/90 bg-amber-50/50 py-3 text-center">
                      <p className="text-xl font-bold text-stone-900">
                        {graphData.nodes.length}
                      </p>
                      <p className="text-xs text-stone-600">节点</p>
                    </div>
                    <div className="rounded-xl border border-stone-200/90 bg-amber-50/50 py-3 text-center">
                      <p className="text-xl font-bold text-stone-900">
                        {graphData.relationships?.length || 0}
                      </p>
                      <p className="text-xs text-stone-600">关系</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {Array.from(
                      new Set(
                        graphData.nodes.map((n) => n.labels?.[0] || "Unknown")
                      )
                    ).map((label) => (
                      <span
                        key={label}
                        className="rounded-full border border-amber-200/80 bg-amber-50/90 px-2.5 py-0.5 text-xs text-amber-950"
                      >
                        {label}
                      </span>
                    ))}
                  </div>
                  <div className="overflow-hidden rounded-xl border border-stone-200 bg-[#f4efe6]">
                    <PaperGraphView
                      graphNodes={graphData.nodes}
                      relationships={
                        graphData.relationships ?? EMPTY_GRAPH_RELATIONSHIPS
                      }
                      height={260}
                      showMiniMap={false}
                      className="border-0 shadow-none"
                    />
                  </div>
                  <Link href={`/graph?paper=${arxivId}`} className="block">
                    <Button className="w-full rounded-xl bg-amber-800 text-amber-50 hover:bg-amber-900">
                      展开交互式图谱
                      <ExternalLink className="ml-2 h-4 w-4" />
                    </Button>
                  </Link>
                </div>
              ) : (
                <div className="py-8 text-center text-sm text-stone-500">
                  暂无图谱数据
                </div>
              )}
            </CardContent>
          </Card>

          {paper.summary?.trim() ? (
            <Card className={shell}>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base font-semibold text-stone-900">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-100 text-violet-900">
                    <FileText className="h-4 w-4" />
                  </span>
                  arXiv 摘要
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-sm leading-relaxed text-stone-600 whitespace-pre-wrap">
                  {paper.summary.trim()}
                </p>
              </CardContent>
            </Card>
          ) : null}

          {paper.reasoning_process?.trim() ? (
            <div
              className={cn(
                shell,
                "border-stone-700/25 bg-stone-900/[0.45] text-stone-100 shadow-md backdrop-blur-md"
              )}
            >
              <div className="border-b border-white/10 px-5 py-3">
                <h3 className="flex items-center gap-2 text-sm font-semibold tracking-tight text-stone-50">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-500/20 text-violet-200 ring-1 ring-violet-400/30">
                    <Brain className="h-4 w-4" />
                  </span>
                  AI Reading Notes / 萃取推理过程
                </h3>
                <p className="mt-1 pl-11 text-[11px] text-stone-400">
                  模型在阅读全文时的思维链摘要，便于对照 PDF 核验
                </p>
              </div>
              <div className="border-l-4 border-violet-500/90 px-5 py-4 pl-6">
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-stone-200/95">
                  {paper.reasoning_process.trim()}
                </p>
              </div>
            </div>
          ) : null}

          {paper.core_problem ? (
            <Card className={shell}>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base font-semibold text-stone-900">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-orange-100 text-orange-900">
                    <Target className="h-4 w-4" />
                  </span>
                  核心问题
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-sm leading-relaxed text-stone-800">
                  {paper.core_problem}
                </p>
              </CardContent>
            </Card>
          ) : null}

          {paper.proposed_method ? (
            <Card className={shell}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="flex items-center gap-2 text-base font-semibold text-stone-900">
                    <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-100 text-amber-950">
                      <Wrench className="h-4 w-4" />
                    </span>
                    提出的方法
                  </CardTitle>
                  <Link
                    href={`/evolution?method=${encodeURIComponent(paper.proposed_method)}`}
                  >
                    <Button
                      variant="outline"
                      size="sm"
                      className="shrink-0 rounded-lg border-stone-300 bg-white text-xs hover:bg-amber-50"
                    >
                      <GitBranch className="mr-1 h-3.5 w-3.5" />
                      进化树
                    </Button>
                  </Link>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="text-base font-semibold text-amber-950">
                  {paper.proposed_method}
                </p>
              </CardContent>
            </Card>
          ) : null}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-1">
            <Card className={shell}>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base font-semibold text-stone-900">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-lime-100 text-lime-900">
                    <Lightbulb className="h-4 w-4" />
                  </span>
                  创新点
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                {(paper.innovations ?? []).length > 0 ? (
                  <ul className="space-y-2">
                    {(paper.innovations ?? []).map((item, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-stone-700">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-lime-600" />
                        {item}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-stone-500">暂无数据</p>
                )}
              </CardContent>
            </Card>

            <Card className={shell}>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base font-semibold text-stone-900">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-orange-100 text-orange-900">
                    <AlertTriangle className="h-4 w-4" />
                  </span>
                  局限性
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                {(paper.limitations ?? []).length > 0 ? (
                  <ul className="space-y-2">
                    {(paper.limitations ?? []).map((item, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-stone-700">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-orange-600" />
                        {item}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-stone-500">暂无数据</p>
                )}
              </CardContent>
            </Card>
          </div>

          <Card className={shell}>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base font-semibold text-stone-900">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-100 text-purple-900">
                  <Sparkles className="h-4 w-4" />
                </span>
                对比实验（立体）
              </CardTitle>
              <p className="text-xs text-stone-500">
                基线 · 数据集 · 指标变化（来自图谱 IMPROVES_UPON 边与萃取 comparisons）
              </p>
            </CardHeader>
            <CardContent className="pt-0">
              {(paper.experiment_comparisons ?? []).length > 0 ? (
                <div className="overflow-x-auto rounded-xl border border-stone-200/90">
                  <table className="w-full border-collapse text-left text-sm">
                    <thead>
                      <tr className="border-b border-stone-200 bg-stone-100/90 text-[11px] font-semibold uppercase tracking-wide text-stone-600">
                        <th className="px-3 py-2.5">Baseline Method</th>
                        <th className="px-3 py-2.5">Dataset</th>
                        <th className="px-3 py-2.5">Metrics Improvement</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(paper.experiment_comparisons ?? []).map((row, i) => (
                        <tr
                          key={`${row.baseline}-${i}`}
                          className="border-b border-stone-100 last:border-0"
                        >
                          <td className="px-3 py-2.5 font-medium text-stone-900">
                            {row.baseline || "—"}
                          </td>
                          <td className="px-3 py-2.5 text-stone-700">
                            {row.dataset?.trim() || "—"}
                          </td>
                          <td className="px-3 py-2.5 font-mono text-xs text-violet-900">
                            {row.metrics_improvement?.trim() || "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="rounded-lg border border-dashed border-stone-200 bg-stone-50/80 px-3 py-4 text-center text-sm text-stone-500">
                  无结构化对比数据
                </p>
              )}
            </CardContent>
          </Card>

            <p className="rounded-xl border border-amber-200/60 bg-amber-50/90 px-3 py-2 text-xs leading-relaxed text-stone-600 lg:border-amber-200/80">
              上文结构化内容为{" "}
              <span className="font-medium text-amber-950">大模型萃取结果</span>
              ，可能与原文表述不完全一致；请以左侧 PDF 与 arXiv 原文为准进行核对。
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
