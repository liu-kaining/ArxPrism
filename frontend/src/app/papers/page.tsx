"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { paperApi, Paper } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Search, ExternalLink, Calendar, User } from "lucide-react";
import { formatDate } from "@/lib/utils";

export default function PapersPage() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const pageSize = 20;

  const searchPapers = async (searchQuery: string, offset: number = 0) => {
    if (!searchQuery.trim()) {
      setPapers([]);
      return;
    }

    setIsLoading(true);
    try {
      const result = await paperApi.searchPapers({
        query: searchQuery,
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
    // 加载默认搜索结果
    if (!query) {
      searchPapers("site reliability engineering", 0);
    }
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">论文列表</h1>
        <p className="text-muted-foreground mt-1">
          搜索和浏览已入库的论文，查看详细信息和知识图谱
        </p>
      </div>

      {/* Search */}
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="搜索论文..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <Button type="submit" disabled={isLoading}>
              搜索
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Results */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      ) : papers.length > 0 ? (
        <>
          <div className="text-sm text-muted-foreground">
            找到 {total} 篇论文
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {papers.map((paper) => (
              <Card key={paper.arxiv_id} className="hover:border-primary/50 transition-colors">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-base line-clamp-2">
                      {paper.title}
                    </CardTitle>
                    <a
                      href={`https://arxiv.org/abs/${paper.arxiv_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0"
                    >
                      <Button variant="ghost" size="icon">
                        <ExternalLink className="w-4 h-4" />
                      </Button>
                    </a>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <User className="w-3 h-3" />
                      {paper.authors.slice(0, 2).join(", ")}
                      {paper.authors.length > 2 && " et al."}
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {formatDate(paper.published_date)}
                    </span>
                  </div>

                  {paper.core_problem && (
                    <div>
                      <span className="text-xs font-medium text-primary">核心问题</span>
                      <p className="text-sm line-clamp-2 mt-1">
                        {paper.core_problem}
                      </p>
                    </div>
                  )}

                  {paper.proposed_method && (
                    <div>
                      <span className="text-xs font-medium text-secondary">提出方法</span>
                      <p className="text-sm font-medium mt-1">
                        {paper.proposed_method}
                      </p>
                    </div>
                  )}

                  <div className="flex flex-wrap gap-2 pt-2">
                    {paper.datasets?.slice(0, 3).map((ds) => (
                      <span
                        key={ds}
                        className="px-2 py-1 text-xs rounded bg-accent"
                      >
                        {ds}
                      </span>
                    ))}
                    {paper.metrics?.slice(0, 2).map((metric) => (
                      <span
                        key={metric}
                        className="px-2 py-1 text-xs rounded bg-primary/10 text-primary"
                      >
                        {metric}
                      </span>
                    ))}
                  </div>

                  <div className="pt-2 border-t">
                    <Link href={`/papers/${paper.arxiv_id}`}>
                      <Button variant="outline" size="sm" className="w-full">
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
            <div className="flex justify-center gap-2">
              <Button
                variant="outline"
                disabled={page === 0}
                onClick={() => {
                  const newPage = page - 1;
                  setPage(newPage);
                  searchPapers(query, newPage * pageSize);
                }}
              >
                上一页
              </Button>
              <span className="flex items-center px-4">
                第 {page + 1} / {Math.ceil(total / pageSize)} 页
              </span>
              <Button
                variant="outline"
                disabled={(page + 1) * pageSize >= total}
                onClick={() => {
                  const newPage = page + 1;
                  setPage(newPage);
                  searchPapers(query, newPage * pageSize);
                }}
              >
                下一页
              </Button>
            </div>
          )}
        </>
      ) : (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              {query ? "未找到相关论文" : "输入关键词搜索论文"}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
