"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { paperApi, Paper } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Search, ExternalLink, Calendar, User, FileText, Sparkles } from "lucide-react";
import { formatDate } from "@/lib/utils";

function paperTaskLabel(paper: Paper): string | null {
  const t = paper.task_name?.trim();
  if (t) return t;
  const fromList = paper.tasks?.find((x) => String(x).trim());
  return fromList ? String(fromList).trim() : null;
}

export default function PapersPage() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const pageSize = 20;

  /** 空关键词 = 展示库内全部论文（与 GET /api/v1/papers?query= 一致） */
  const searchPapers = async (searchQuery: string, offset: number = 0) => {
    setIsLoading(true);
    try {
      const result = await paperApi.searchPapers({
        query: searchQuery.trim(),
        limit: pageSize,
        offset,
      });
      setPapers(result.papers);
      setTotal(result.total);
    } catch (error) {
      console.error("Search failed:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
    searchPapers(query, 0);
  };

  useEffect(() => {
    searchPapers("", 0);
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-cyan-500/30 bg-cyan-950/50 shadow-[0_0_20px_-6px_rgba(34,211,238,0.35)]">
          <FileText className="h-6 w-6 text-cyan-400" />
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-50">
            论文列表
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            搜索和浏览已入库的论文，查看详细信息和知识图谱
          </p>
        </div>
      </div>

      {/* Search */}
      <Card className="border border-slate-800 bg-slate-900/90 shadow-none transition-colors hover:border-slate-700">
        <CardContent className="pt-6">
          <form onSubmit={handleSearch} className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 transform text-slate-500" />
              <Input
                placeholder="搜索标题、摘要问题、方法名… 留空则显示全部已入库论文"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="h-12 rounded-xl border-slate-700 bg-slate-950/80 pl-12 text-slate-100 placeholder:text-slate-500"
              />
            </div>
            <Button type="submit" disabled={isLoading} className="h-12 px-6 rounded-xl">
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

      {/* Results */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 stagger-children md:grid-cols-2">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton
              key={i}
              className="h-48 w-full rounded-xl border border-slate-800 bg-slate-900"
            />
          ))}
        </div>
      ) : papers.length > 0 ? (
        <>
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <Sparkles className="h-4 w-4 text-amber-500/80" />
            找到{" "}
            <span className="font-semibold text-slate-100">{total}</span>{" "}
            篇论文
          </div>

          <div className="grid grid-cols-1 gap-4 stagger-children md:grid-cols-2">
            {papers.map((paper) => {
              const task = paperTaskLabel(paper);
              return (
                <Card
                  key={paper.arxiv_id}
                  className="group overflow-hidden border border-slate-800 bg-slate-900 text-slate-50 shadow-none transition-colors duration-200 hover:border-slate-700"
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
                        <CardTitle className="text-base font-semibold leading-tight text-slate-100 line-clamp-2 transition-colors group-hover:text-cyan-400">
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
                          className="text-slate-400 opacity-0 transition-opacity hover:text-cyan-400 group-hover:opacity-100"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </Button>
                      </a>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
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
                      <p className="line-clamp-3 text-sm italic leading-relaxed text-slate-400">
                        {paper.core_problem}
                      </p>
                    ) : null}

                    {paper.proposed_method ? (
                      <div className="rounded-lg border border-cyan-500/20 bg-cyan-950/30 p-3">
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-cyan-500/90">
                          提出方法
                        </span>
                        <p className="mt-1 text-sm font-medium text-cyan-200">
                          {paper.proposed_method}
                        </p>
                      </div>
                    ) : null}

                    <div className="flex flex-wrap gap-2 pt-1">
                      {paper.datasets?.slice(0, 3).map((ds) => (
                        <span
                          key={ds}
                          className="rounded-full border border-slate-700 bg-slate-950/60 px-2.5 py-1 font-mono text-[11px] text-slate-400"
                        >
                          {ds}
                        </span>
                      ))}
                      {paper.metrics?.slice(0, 2).map((metric) => (
                        <span
                          key={metric}
                          className="rounded-full border border-amber-500/25 bg-amber-500/5 px-2.5 py-1 font-mono text-[11px] font-medium text-amber-400/90"
                        >
                          {metric}
                        </span>
                      ))}
                    </div>

                    <div className="border-t border-slate-800 pt-3">
                      <Link href={`/papers/${paper.arxiv_id}`}>
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full rounded-lg border-slate-600 bg-slate-950/50 text-slate-200 transition-colors hover:border-cyan-500/40 hover:bg-slate-900 hover:text-cyan-300"
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
          {total > pageSize && (
            <div className="flex justify-center gap-3">
              <Button
                variant="outline"
                disabled={page === 0}
                onClick={() => {
                  const newPage = page - 1;
                  setPage(newPage);
                  searchPapers(query, newPage * pageSize);
                }}
                className="rounded-xl border-slate-700 bg-slate-900 text-slate-200 hover:border-slate-600 hover:bg-slate-800"
              >
                上一页
              </Button>
              <span className="flex items-center rounded-xl border border-slate-800 bg-slate-900 px-4 py-2 text-sm text-slate-300">
                第 <span className="mx-1 font-semibold">{page + 1}</span> /{" "}
                <span className="mx-1">
                  {Math.ceil(total / pageSize)}
                </span>{" "}
                页
              </span>
              <Button
                variant="outline"
                disabled={(page + 1) * pageSize >= total}
                onClick={() => {
                  const newPage = page + 1;
                  setPage(newPage);
                  searchPapers(query, newPage * pageSize);
                }}
                className="rounded-xl border-slate-700 bg-slate-900 text-slate-200 hover:border-slate-600 hover:bg-slate-800"
              >
                下一页
              </Button>
            </div>
          )}
        </>
      ) : (
        <Card className="border border-slate-800 bg-slate-900 shadow-none">
          <CardContent className="py-16 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full border border-slate-700 bg-slate-950">
              <FileText className="h-8 w-8 text-slate-600" />
            </div>
            <p className="text-lg text-slate-300">
              {query.trim() ? "未找到相关论文" : "图库中暂无论文"}
            </p>
            <p className="mt-2 text-sm text-slate-500">
              可先运行采集任务写入 Neo4j，或换关键词再搜
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
