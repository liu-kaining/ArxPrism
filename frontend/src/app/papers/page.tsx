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
        <div className="w-12 h-12 rounded-xl bg-gradient-primary flex items-center justify-center">
          <FileText className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-3xl font-bold">论文列表</h1>
          <p className="text-muted-foreground mt-1">
            搜索和浏览已入库的论文，查看详细信息和知识图谱
          </p>
        </div>
      </div>

      {/* Search */}
      <Card className="border-0 shadow-lg card-hover">
        <CardContent className="pt-6">
          <form onSubmit={handleSearch} className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <Input
                placeholder="搜索标题、摘要问题、方法名… 留空则显示全部已入库论文"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-12 h-12 rounded-xl"
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
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 stagger-children">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-48 w-full rounded-xl" />
          ))}
        </div>
      ) : papers.length > 0 ? (
        <>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Sparkles className="w-4 h-4" />
            找到 <span className="font-semibold text-foreground">{total}</span> 篇论文
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 stagger-children">
            {papers.map((paper) => (
              <Card
                key={paper.arxiv_id}
                className="group border-0 shadow-lg card-hover overflow-hidden"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <CardTitle className="text-base line-clamp-2 leading-tight group-hover:text-primary transition-colors">
                      {paper.title}
                    </CardTitle>
                    <a
                      href={`https://arxiv.org/abs/${paper.arxiv_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0"
                    >
                      <Button variant="ghost" size="icon" className="opacity-0 group-hover:opacity-100 transition-opacity">
                        <ExternalLink className="w-4 h-4" />
                      </Button>
                    </a>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <span className="flex items-center gap-1.5">
                      <User className="w-3.5 h-3.5" />
                      {paper.authors.length > 0
                        ? `${paper.authors.slice(0, 2).join(", ")}${
                            paper.authors.length > 2 ? " et al." : ""
                          }`
                        : "—"}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5" />
                      {formatDate(paper.published_date)}
                    </span>
                  </div>

                  {paper.core_problem && (
                    <div className="p-3 rounded-lg bg-muted/50">
                      <span className="text-xs font-medium text-primary">核心问题</span>
                      <p className="text-sm line-clamp-2 mt-1">
                        {paper.core_problem}
                      </p>
                    </div>
                  )}

                  {paper.proposed_method && (
                    <div className="p-3 rounded-lg bg-primary/5 border border-primary/10">
                      <span className="text-xs font-medium text-primary">提出方法</span>
                      <p className="text-sm font-medium mt-1 text-primary">
                        {paper.proposed_method}
                      </p>
                    </div>
                  )}

                  <div className="flex flex-wrap gap-2 pt-2">
                    {paper.datasets?.slice(0, 3).map((ds) => (
                      <span
                        key={ds}
                        className="px-2.5 py-1 text-xs rounded-full bg-secondary"
                      >
                        {ds}
                      </span>
                    ))}
                    {paper.metrics?.slice(0, 2).map((metric) => (
                      <span
                        key={metric}
                        className="px-2.5 py-1 text-xs rounded-full bg-primary/10 text-primary font-medium"
                      >
                        {metric}
                      </span>
                    ))}
                  </div>

                  <div className="pt-3 border-t">
                    <Link href={`/papers/${paper.arxiv_id}`}>
                      <Button variant="outline" size="sm" className="w-full rounded-lg group-hover:border-primary/50 transition-colors">
                        查看详情和图谱
                        <ExternalLink className="w-4 h-4 ml-2" />
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            ))}
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
                className="rounded-xl"
              >
                上一页
              </Button>
              <span className="flex items-center px-4 py-2 rounded-xl bg-muted">
                第 <span className="font-semibold mx-1">{page + 1}</span> / <span className="mx-1">{Math.ceil(total / pageSize)}</span> 页
              </span>
              <Button
                variant="outline"
                disabled={(page + 1) * pageSize >= total}
                onClick={() => {
                  const newPage = page + 1;
                  setPage(newPage);
                  searchPapers(query, newPage * pageSize);
                }}
                className="rounded-xl"
              >
                下一页
              </Button>
            </div>
          )}
        </>
      ) : (
        <Card className="border-0 shadow-lg">
          <CardContent className="py-16 text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-muted flex items-center justify-center">
              <FileText className="w-8 h-8 text-muted-foreground" />
            </div>
            <p className="text-muted-foreground text-lg">
              {query.trim() ? "未找到相关论文" : "图库中暂无论文"}
            </p>
            <p className="text-sm text-muted-foreground/70 mt-2">
              可先运行采集任务写入 Neo4j，或换关键词再搜
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
