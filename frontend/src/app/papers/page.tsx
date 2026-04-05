"use client";

import { Suspense, useState, useEffect, useRef } from "react";
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
  Type,
  Loader2,
} from "lucide-react";
import { cn, formatDate } from "@/lib/utils";

function paperTaskLabel(paper: Paper): string | null {
  const t = paper.task_name?.trim();
  if (t) return t;
  const fromList = paper.tasks?.find((x) => String(x).trim());
  return fromList ? String(fromList).trim() : null;
}

function TopicDistributionCard({
  stats,
  onPickTopic,
  isRefreshing,
}: {
  stats: LibraryStats;
  onPickTopic: () => void;
  isRefreshing?: boolean;
}) {
  const scope = stats.by_topic_scope ?? "global";
  const maxCount = stats.by_topic[0]?.paper_count ?? 0;
  const showBars = maxCount > 1;
  const allSingleton =
    stats.by_topic.length > 0 &&
    stats.by_topic.every((r) => r.paper_count === 1);

  return (
    <Card
      className={cn(
        "relative overflow-hidden border-border bg-card shadow-sm transition-opacity",
        isRefreshing && "opacity-70"
      )}
    >
      {isRefreshing ? (
        <div className="absolute right-3 top-3 z-[2] flex items-center gap-1.5 rounded-full border border-amber-200/90 bg-amber-50/95 px-2.5 py-1 text-[11px] font-semibold text-amber-950 shadow-sm">
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
          更新中
        </div>
      ) : null}
      <CardHeader className="space-y-2 border-b border-border/70 bg-gradient-to-r from-stone-50/90 to-amber-50/40 pb-3 pt-4">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-base font-semibold text-stone-900">
            萃取主题（Task）分布
          </CardTitle>
          <span
            className={cn(
              "rounded-full px-2.5 py-0.5 text-[11px] font-semibold tracking-wide",
              scope === "filtered"
                ? "bg-sky-100 text-sky-900 ring-1 ring-sky-200/90"
                : "bg-stone-100 text-stone-700 ring-1 ring-stone-200/80"
            )}
          >
            {scope === "filtered" ? "当前列表命中" : "全库"}
          </span>
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          点击<strong>主题名</strong>可在下方列表中叠加该 Task 筛选；表末图标打开该主题下任意一篇代表论文的{" "}
          <Link
            href="/graph"
            className="font-medium text-amber-800 underline-offset-2 hover:underline"
          >
            知识图谱
          </Link>
          。进化树按{" "}
          <Link
            href="/evolution"
            className="font-medium text-amber-800 underline-offset-2 hover:underline"
          >
            方法名
          </Link>{" "}
          查询。
        </p>
        <p className="text-xs leading-relaxed text-stone-600">
          Task 标签多为模型按篇写成的长句，字面不同就会分成不同行，因此常出现「每行 1
          篇」——与关键词是否搜到相关论文<strong>不是一回事</strong>。
          {scope === "filtered" ? (
            <>
              {" "}
              你已带关键词/主题筛选时，本表与<strong>下方列表使用同一套命中条件</strong>。
            </>
          ) : (
            <>
              {" "}
              使用搜索后，本表会切换为<strong>仅命中论文</strong>内的分布。
            </>
          )}
        </p>
        {allSingleton ? (
          <p className="rounded-lg border border-amber-200/80 bg-amber-50/90 px-3 py-2 text-[11px] leading-snug text-amber-950">
            当前各行篇数均为 1：说明这些论文的 Task 文案在图里互不重复。若流水线把多篇论文 MERGE
            到同一 Task 节点，这里会自动合并成大于 1 的计数。
          </p>
        ) : null}
      </CardHeader>
      <CardContent className="p-0">
        <div className="max-h-80 overflow-y-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="sticky top-0 z-[1] border-b border-border bg-card text-left text-[11px] font-semibold uppercase tracking-wide text-muted-foreground shadow-sm">
                <th className="px-4 py-2.5 font-medium">主题</th>
                <th className="w-14 px-2 py-2.5 text-right font-medium">篇数</th>
                {showBars ? (
                  <th className="hidden w-32 px-2 py-2.5 font-medium sm:table-cell">
                    相对规模
                  </th>
                ) : null}
                <th className="w-12 px-2 py-2.5 text-center font-medium">
                  图
                </th>
              </tr>
            </thead>
            <tbody>
              {stats.by_topic.map((row) => {
                const pct =
                  maxCount > 0
                    ? Math.round((row.paper_count / maxCount) * 100)
                    : 0;
                const sampleId = row.sample_arxiv_id
                  ? String(row.sample_arxiv_id).trim()
                  : "";
                return (
                  <tr
                    key={row.topic}
                    className="border-b border-border/80 transition-colors hover:bg-amber-50/50"
                  >
                    <td className="px-4 py-2.5 align-top">
                      <Link
                        href={`/papers?topic=${encodeURIComponent(row.topic)}`}
                        onClick={onPickTopic}
                        className="block text-left font-medium leading-snug text-stone-800 hover:text-amber-900"
                        title={row.topic}
                      >
                        {row.topic}
                      </Link>
                    </td>
                    <td className="px-2 py-2.5 text-right align-top">
                      <span className="inline-block min-w-[2rem] rounded-md bg-stone-100 px-2 py-0.5 text-center text-xs font-bold tabular-nums text-stone-800 ring-1 ring-stone-200/80">
                        {row.paper_count}
                      </span>
                    </td>
                    {showBars ? (
                      <td className="hidden align-middle px-2 py-2.5 sm:table-cell">
                        <div className="h-2 overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full min-w-[4px] rounded-full bg-gradient-to-r from-amber-500 to-orange-500"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </td>
                    ) : null}
                    <td className="px-1 py-1.5 text-center align-middle">
                      {sampleId ? (
                        <Link
                          href={`/graph?paper=${encodeURIComponent(sampleId)}`}
                          className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-amber-800 hover:bg-amber-100"
                          title={`知识图谱：${sampleId}`}
                        >
                          <Network className="h-4 w-4" />
                        </Link>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function PapersPageInner() {
  const searchParams = useSearchParams();
  const taskTopic = searchParams.get("topic") ?? "";

  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [searchMode, setSearchMode] = useState<"semantic" | "keyword">(
    "semantic"
  );
  const [papers, setPapers] = useState<Paper[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [stats, setStats] = useState<LibraryStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  /** 用于在重新搜索时保留上一屏列表，避免整块骨架「白屏」感 */
  const wasListedRef = useRef(false);
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
          searchMode,
        });
        if (!cancelled) {
          setPapers(result.papers);
          setTotal(result.total);
          if (result.papers.length > 0) wasListedRef.current = true;
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
  }, [appliedQuery, page, taskTopic, searchMode]);

  useEffect(() => {
    let cancelled = false;
    setStatsLoading(true);
    paperApi
      .getLibraryStats({
        query: appliedQuery,
        taskTopic: taskTopic || undefined,
        searchMode,
      })
      .then((s) => {
        if (!cancelled) setStats(s);
      })
      .catch((e) => console.error("Library stats failed:", e))
      .finally(() => {
        if (!cancelled) setStatsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [appliedQuery, taskTopic, searchMode]);

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
            {searchMode === "semantic"
              ? "语义模式：向量相似度 + 与本轮最佳结果挂钩的相对阈值，减少「搜一个词却列出整库」。"
              : "关键词模式：标题 / 核心问题 / 方法名包含查询子串即命中。"}
            支持主题筛选；详情页可查看 CoT 与实验对比。
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
                placeholder='Ask anything (e.g., "How to locate microservice root causes without tracing?")… 留空则按时间浏览全库'
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="h-12 rounded-xl pl-12 pr-[9.5rem] shadow-inner sm:pr-[10.5rem]"
              />
              <div
                className="absolute right-2 top-1/2 flex -translate-y-1/2 gap-0.5 rounded-lg border border-stone-200/90 bg-white/95 p-0.5 shadow-sm"
                role="group"
                aria-label="检索模式"
              >
                <button
                  type="button"
                  onClick={() => setSearchMode("semantic")}
                  title="语义：向量相似度，弱相关条目会被相对阈值过滤"
                  className={cn(
                    "flex items-center gap-1 rounded-md px-2 py-1.5 text-[11px] font-semibold transition-colors",
                    searchMode === "semantic"
                      ? "bg-violet-100 text-violet-900 ring-1 ring-violet-300/80"
                      : "text-stone-500 hover:bg-stone-100 hover:text-stone-800"
                  )}
                >
                  <Sparkles className="h-3.5 w-3.5 shrink-0 text-violet-600" />
                  <span className="hidden sm:inline">语义</span>
                </button>
                <button
                  type="button"
                  onClick={() => setSearchMode("keyword")}
                  title="关键词：标题、核心问题、方法名包含子串"
                  className={cn(
                    "flex items-center gap-1 rounded-md px-2 py-1.5 text-[11px] font-semibold transition-colors",
                    searchMode === "keyword"
                      ? "bg-amber-100 text-amber-950 ring-1 ring-amber-300/80"
                      : "text-stone-500 hover:bg-stone-100 hover:text-stone-800"
                  )}
                >
                  <Type className="h-3.5 w-3.5 shrink-0 text-amber-800" />
                  <span className="hidden sm:inline">关键词</span>
                </button>
              </div>
            </div>
            <Button type="submit" disabled={isLoading} className="h-12 min-w-[7.5rem] rounded-xl px-6">
              {isLoading ? (
                <>
                  <Loader2
                    className="mr-2 h-4 w-4 shrink-0 animate-spin"
                    aria-hidden
                  />
                  搜索中…
                </>
              ) : (
                <>
                  <Search className="mr-2 h-4 w-4" />
                  搜索
                </>
              )}
            </Button>
          </form>
          {searchMode === "semantic" ? (
            <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
              语义检索需要后端调用<strong>嵌入模型</strong>并查询 Neo4j
              向量索引，冷启动或网络较慢时可能需数秒；若只要字面匹配可切换「关键词」。
            </p>
          ) : null}
        </CardContent>
      </Card>

      {/* 图库统计（全库，与当前搜索关键词无关） */}
      {stats ? (
        <div
          className={cn(
            "relative grid gap-3 md:grid-cols-2 lg:grid-cols-4 transition-opacity",
            statsLoading && "opacity-65"
          )}
        >
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
          {statsLoading ? (
            <div className="pointer-events-none absolute inset-0 flex items-start justify-end pt-2 pr-2 md:pt-3 md:pr-3">
              <span className="flex items-center gap-1.5 rounded-full border border-amber-200/90 bg-amber-50/95 px-2.5 py-1 text-[11px] font-semibold text-amber-950 shadow-sm">
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                统计同步中
              </span>
            </div>
          ) : null}
        </div>
      ) : null}

      {stats && stats.by_topic.length > 0 ? (
        <TopicDistributionCard
          stats={stats}
          onPickTopic={() => setPage(0)}
          isRefreshing={statsLoading}
        />
      ) : null}

      {/* Results：有上一屏数据时保留展示并叠加载提示，避免「整块白屏」 */}
      {isLoading && papers.length === 0 && !wasListedRef.current ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2 rounded-xl border border-stone-200 bg-stone-50/80 px-4 py-3 text-sm text-stone-700">
            <Loader2 className="h-5 w-5 shrink-0 animate-spin text-amber-700" />
            <span>
              正在加载列表
              {searchMode === "semantic"
                ? "（语义模式会稍慢，请稍候）"
                : "…"}
            </span>
          </div>
          <div className="grid grid-cols-1 gap-4 stagger-children md:grid-cols-2">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton
                key={i}
                className="h-48 w-full rounded-xl border border-border bg-muted"
              />
            ))}
          </div>
        </div>
      ) : null}

      {isLoading && papers.length === 0 && wasListedRef.current ? (
        <div
          className="flex items-start gap-3 rounded-xl border border-violet-200/90 bg-violet-50/90 px-4 py-4 text-sm text-stone-800"
          role="status"
          aria-live="polite"
        >
          <Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-violet-600" />
          <div>
            <p className="font-semibold text-stone-900">正在检索…</p>
            <p className="mt-1 text-xs text-stone-600">
              上一批结果已清空，新列表加载中
              {searchMode === "semantic"
                ? "（语义模式需调用嵌入服务，请稍候）"
                : ""}
              。
            </p>
          </div>
        </div>
      ) : null}

      {isLoading && papers.length > 0 ? (
        <div
          className="flex items-start gap-3 rounded-xl border border-violet-200/90 bg-gradient-to-r from-violet-50/95 to-amber-50/80 px-4 py-3 text-sm text-stone-800 shadow-sm"
          role="status"
          aria-live="polite"
        >
          <Loader2
            className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-violet-600"
            aria-hidden
          />
          <div className="min-w-0 space-y-1">
            <p className="font-semibold text-stone-900">正在更新检索结果…</p>
            <p className="text-xs leading-relaxed text-stone-600">
              {searchMode === "semantic"
                ? "下方暂为上一批结果。语义检索需生成查询向量并访问向量索引，通常几秒完成。"
                : "下方暂为上一批结果，新列表马上替换。"}
            </p>
          </div>
        </div>
      ) : null}

      {!isLoading || papers.length > 0 ? (
        papers.length > 0 ? (
        <>
          <div
            className={cn(
              "flex flex-wrap items-center gap-x-2 gap-y-2 text-sm text-muted-foreground transition-opacity",
              isLoading && papers.length > 0 && "opacity-60"
            )}
          >
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

          <div
            className={cn(
              "grid grid-cols-1 gap-4 stagger-children md:grid-cols-2 transition-opacity",
              isLoading && papers.length > 0 && "pointer-events-none opacity-55"
            )}
            aria-busy={isLoading && papers.length > 0}
          >
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

                    {(paper.contributors?.length ?? 0) > 0 ? (
                      <p className="text-[11px] leading-snug text-muted-foreground">
                        <span className="font-medium text-stone-600">入库贡献</span>{" "}
                        {paper.contributors!.length} 条（用户与抓取任务已记入图谱）
                      </p>
                    ) : null}

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
        ) : !isLoading ? (
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
        ) : null
      ) : null}
    </div>
  );
}

function PapersPageFallback() {
  return (
    <div className="warm-page space-y-4">
      <Skeleton className="h-16 w-full rounded-xl" />
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
