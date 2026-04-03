"use client";

import { Suspense, useState, useEffect } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { paperApi, Paper, type LibraryStats } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  Search,
  ExternalLink,
  Calendar,
  User,
  FileText,
  Sparkles,
  Users,
  Link2,
  Layers,
  Network,
} from "lucide-react";
import { formatDate } from "@/lib/utils";

function paperTaskLabel(paper: Paper): string | null {
  const t = paper.task_name?.trim();
  if (t) return t;
  const fromList = paper.tasks?.find((x) => String(x).trim());
  return fromList ? String(fromList).trim() : null;
}

function PapersPageInner() {
  const searchParams = useSearchParams();
  const taskTopic = searchParams.get("topic") ?? "";

  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [papers, setPapers] = useState<Paper[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [stats, setStats] = useState<LibraryStats | null>(null);
  const pageSize = 10;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setIsLoading(true);
      try {
        const result = await paperApi.searchPapers({
          query: appliedQuery,
          taskTopic: taskTopic || undefined,
          limit: pageSize,
          offset: page * pageSize,
        });
        if (!cancelled) {
          setPapers(result.papers);
          setTotal(result.total);
        }
      } catch (error) {
        console.error("Search failed:", error);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [appliedQuery, page, taskTopic]);

  useEffect(() => {
    let cancelled = false;
    paperApi
      .getLibraryStats()
      .then((s) => {
        if (!cancelled) setStats(s);
      })
      .catch((e) => console.error("Library stats failed:", e));
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
    setAppliedQuery(query.trim());
  };

  const emptyHint =
    appliedQuery.trim() || taskTopic
      ? "未找到相关论文"
      : "图库中暂无论文";

  return (
    <div className="warm-page space-y-4">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-amber-300/80 bg-amber-100 shadow-sm">
          <FileText className="h-6 w-6 text-amber-800" />
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-stone-900">
            论文列表
          </h1>
          <p className="mt-1 text-sm text-stone-600">
            搜索和浏览已入库的论文，查看详细信息和知识图谱
          </p>
        </div>
      </div>

      {/* Search */}
      <Card className="border-border bg-card shadow-sm transition-shadow hover:shadow-md">
        <CardContent className="pt-6">
          <form onSubmit={handleSearch} className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 transform text-muted-foreground" />
              <Input
                placeholder="搜索标题、摘要问题、方法名… 留空则显示全部已入库论文"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="h-12 rounded-xl pl-12"
              />
            </div>
            <Button type="submit" disabled={isLoading} className="h-12 rounded-xl px-6">
              {isLoading ? (
                <span className="animate-pulse">搜索中...</span>
              ) : (
                <>
                  <Search className="w-4 h-4 mr-2" />
                  搜索
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* 图库统计（全库，与当前搜索关键词无关） */}
      {stats ? (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          {[
            {
              label: "入库论文",
              value: stats.paper_count,
              icon: FileText,
              hint: "图库内 Paper 节点总数",
            },
            {
              label: "作者（去重）",
              value: stats.author_count,
              icon: Users,
              hint: "Author 节点数",
            },
            {
              label: "已挂作者",
              value: stats.papers_with_authors,
              icon: Layers,
              hint: "至少有一条 WRITTEN_BY 的论文",
            },
            {
              label: "署名关系",
              value: stats.author_paper_links,
              icon: Link2,
              hint: "论文—作者边条数",
            },
          ].map(({ label, value, icon: Icon, hint }) => (
            <Card
              key={label}
              className="border-border bg-card shadow-sm"
              title={hint}
            >
              <CardContent className="flex items-center gap-3 pt-5 pb-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-amber-300/70 bg-amber-50">
                  <Icon className="h-5 w-5 text-amber-800" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-medium text-muted-foreground">
                    {label}
                  </p>
                  <p className="text-2xl font-bold tabular-nums text-stone-900">
                    {value.toLocaleString()}
                  </p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}

      {stats && stats.by_topic.length > 0 ? (
        <Card className="border-border bg-card shadow-sm">
          <CardHeader className="pb-2 pt-4">
            <CardTitle className="text-base font-semibold text-stone-900">
              按萃取主题（Task）
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              点击一行可在下方列表中只显示该主题的论文；「图谱」打开该主题下一篇代表论文在{" "}
              <Link href="/graph" className="font-medium text-amber-800 underline-offset-2 hover:underline">
                知识图谱
              </Link>{" "}
              中的子图（含 Task、方法等节点）。技术{" "}
              <Link
                href="/evolution"
                className="font-medium text-amber-800 underline-offset-2 hover:underline"
              >
                进化树
              </Link>{" "}
              按<strong>方法名</strong>检索，可从论文详情里的「提出方法」再跳转。
            </p>
          </CardHeader>
          <CardContent className="pb-4 pt-0">
            <ul className="max-h-52 space-y-1 overflow-y-auto pr-1 text-sm">
              {stats.by_topic.map((row) => {
                const max = stats.by_topic[0]?.paper_count || 1;
                const pct = Math.round((row.paper_count / max) * 100);
                const sampleId = row.sample_arxiv_id
                  ? String(row.sample_arxiv_id).trim()
                  : "";
                return (
                  <li
                    key={row.topic}
                    className="flex items-stretch gap-1 rounded-lg border border-transparent hover:border-amber-200/90 hover:bg-amber-50/60"
                  >
                    <Link
                      href={`/papers?topic=${encodeURIComponent(row.topic)}`}
                      onClick={() => setPage(0)}
                      className="flex min-w-0 flex-1 items-center gap-3 px-2 py-2 text-left transition-colors"
                    >
                      <span
                        className="min-w-0 flex-1 truncate text-stone-800"
                        title={row.topic}
                      >
                        {row.topic}
                      </span>
                      <span className="shrink-0 tabular-nums font-medium text-stone-700">
                        {row.paper_count}
                      </span>
                      <div className="hidden h-2 w-20 shrink-0 overflow-hidden rounded-full bg-muted sm:block">
                        <div
                          className="h-full rounded-full bg-amber-500/80"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </Link>
                    {sampleId ? (
                      <Link
                        href={`/graph?paper=${encodeURIComponent(sampleId)}`}
                        className="inline-flex shrink-0 items-center gap-1 rounded-md border border-amber-200/80 bg-amber-50/90 px-2.5 py-2 text-xs font-medium text-amber-900 hover:bg-amber-100"
                        title={`在知识图谱中查看 ${sampleId}`}
                      >
                        <Network className="h-3.5 w-3.5" />
                        图谱
                      </Link>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {/* Results */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 stagger-children md:grid-cols-2">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton
              key={i}
              className="h-48 w-full rounded-xl border border-border bg-muted"
            />
          ))}
        </div>
      ) : papers.length > 0 ? (
        <>
          <div className="flex flex-wrap items-center gap-x-2 gap-y-2 text-sm text-muted-foreground">
            <Sparkles className="h-4 w-4 shrink-0 text-amber-600" />
            <span>
              本次结果{" "}
              <span className="font-semibold text-foreground">{total}</span>{" "}
              篇
            </span>
            {stats ? (
              <span className="text-muted-foreground/80">
                （图库共 {stats.paper_count.toLocaleString()} 篇）
              </span>
            ) : null}
            {taskTopic ? (
              <span className="inline-flex items-center gap-2 rounded-full border border-amber-300/70 bg-amber-50 px-3 py-1 text-xs text-amber-950">
                <span className="max-w-[min(100%,14rem)] truncate font-medium">
                  主题：{taskTopic}
                </span>
                <Link
                  href="/papers"
                  onClick={() => setPage(0)}
                  className="shrink-0 text-amber-800 underline-offset-2 hover:underline"
                >
                  清除
                </Link>
              </span>
            ) : null}
          </div>

          <div className="grid grid-cols-1 gap-4 stagger-children md:grid-cols-2">
            {papers.map((paper) => {
              const task = paperTaskLabel(paper);
              return (
                <Card
                  key={paper.arxiv_id}
                  className="group overflow-hidden border-border bg-card text-card-foreground shadow-sm transition-shadow duration-200 hover:shadow-md"
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        {task ? (
                          <div className="mb-2">
                            <span
                              className="inline-flex max-w-full truncate rounded-md border border-amber-500/20 bg-amber-500/10 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-amber-500"
                              title={task}
                            >
                              {task}
                            </span>
                          </div>
                        ) : null}
                        <CardTitle className="line-clamp-2 text-base font-semibold leading-tight transition-colors group-hover:text-primary">
                          {paper.title}
                        </CardTitle>
                      </div>
                      <a
                        href={`https://arxiv.org/abs/${paper.arxiv_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="shrink-0"
                      >
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-muted-foreground opacity-0 transition-opacity hover:text-primary group-hover:opacity-100"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </Button>
                      </a>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1.5">
                        <User className="h-3.5 w-3.5 shrink-0" />
                        {paper.authors.length > 0
                          ? `${paper.authors.slice(0, 2).join(", ")}${
                              paper.authors.length > 2 ? " et al." : ""
                            }`
                          : "—"}
                      </span>
                      <span className="flex items-center gap-1.5">
                        <Calendar className="h-3.5 w-3.5 shrink-0" />
                        {formatDate(paper.published_date)}
                      </span>
                    </div>

                    {paper.core_problem ? (
                      <p className="line-clamp-3 text-sm italic leading-relaxed text-muted-foreground">
                        {paper.core_problem}
                      </p>
                    ) : null}

                    {paper.proposed_method ? (
                      <div className="rounded-lg border border-cyan-200/80 bg-cyan-50/90 p-3">
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-cyan-800">
                          提出方法
                        </span>
                        <p className="mt-1 text-sm font-medium text-cyan-950">
                          {paper.proposed_method}
                        </p>
                      </div>
                    ) : null}

                    <div className="flex flex-wrap gap-2 pt-1">
                      {paper.datasets?.slice(0, 3).map((ds) => (
                        <span
                          key={ds}
                          className="rounded-full border border-border bg-muted/80 px-2.5 py-1 font-mono text-[11px] text-muted-foreground"
                        >
                          {ds}
                        </span>
                      ))}
                      {paper.metrics?.slice(0, 2).map((metric) => (
                        <span
                          key={metric}
                          className="rounded-full border border-amber-300/80 bg-amber-50 px-2.5 py-1 font-mono text-[11px] font-medium text-amber-900"
                        >
                          {metric}
                        </span>
                      ))}
                    </div>

                    <div className="border-t border-border pt-3">
                      <Link href={`/papers/${paper.arxiv_id}`}>
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full rounded-lg"
                        >
                          查看详情和图谱
                          <ExternalLink className="ml-2 h-4 w-4" />
                        </Button>
                      </Link>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Pagination */}
          {total > pageSize ? (
            <div className="flex justify-center gap-3">
              <Button
                variant="outline"
                disabled={page === 0 || isLoading}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                className="rounded-xl"
              >
                上一页
              </Button>
              <span className="flex items-center rounded-xl border border-border bg-muted/60 px-4 py-2 text-sm text-foreground">
                第 <span className="mx-1 font-semibold">{page + 1}</span> /{" "}
                <span className="mx-1">
                  {Math.ceil(total / pageSize)}
                </span>{" "}
                页
              </span>
              <Button
                variant="outline"
                disabled={
                  isLoading || (page + 1) * pageSize >= total
                }
                onClick={() => setPage((p) => p + 1)}
                className="rounded-xl"
              >
                下一页
              </Button>
            </div>
          ) : null}
        </>
      ) : (
        <Card className="border-border bg-card shadow-sm">
          <CardContent className="py-16 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full border border-border bg-muted">
              <FileText className="h-8 w-8 text-muted-foreground" />
            </div>
            <p className="text-lg text-foreground">{emptyHint}</p>
            <p className="mt-2 text-sm text-muted-foreground">
              {taskTopic
                ? "可点击上方其他主题，或清除主题筛选后重试"
                : "可先运行采集任务写入 Neo4j，或换关键词再搜"}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function PapersPageFallback() {
  return (
    <div className="warm-page space-y-4">
      <Skeleton className="h-16 w-full max-w-md rounded-xl" />
      <Skeleton className="h-24 w-full rounded-xl" />
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-48 rounded-xl" />
        ))}
      </div>
    </div>
  );
}

export default function PapersPage() {
  return (
    <Suspense fallback={<PapersPageFallback />}>
      <PapersPageInner />
    </Suspense>
  );
}
