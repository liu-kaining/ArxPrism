"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useTaskStore } from "@/lib/stores/taskStore";
import { arxivApi, type ArxivPreviewSearchResult } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import toast from "react-hot-toast";
import {
  Rocket,
  Search,
  Loader2,
  ExternalLink,
  Shield,
  Cloud,
  Eye,
  Lock,
  Server,
  Cpu,
  Sparkles,
  Zap,
  TrendingUp,
  Globe,
  BarChart3,
  Target,
  Activity,
  Layers,
} from "lucide-react";

// Topic icons mapping
const topicIcons: Record<string, any> = {
  sre: Server,
  ha: Shield,
  ai: Cpu,
  llm: Sparkles,
  aiops: Activity,
  microservices: Layers,
  distributed: Zap,
  cloudnative: Cloud,
  observability: Eye,
  security: Lock,
  // 金融相关
  quant: TrendingUp,
  fintech: Globe,
  fe: BarChart3,
  market_prediction: Target,
};

// Topic colors
const topicColors: Record<string, string> = {
  sre: "from-blue-500 to-cyan-500",
  ha: "from-green-500 to-emerald-500",
  ai: "from-purple-500 to-pink-500",
  llm: "from-orange-500 to-amber-500",
  aiops: "from-violet-500 to-purple-500",
  microservices: "from-stone-500 to-stone-600",
  distributed: "from-yellow-500 to-orange-500",
  cloudnative: "from-sky-500 to-blue-500",
  observability: "from-teal-500 to-cyan-500",
  security: "from-red-500 to-rose-500",
  // 金融相关
  quant: "from-emerald-500 to-green-500",
  fintech: "from-indigo-500 to-purple-500",
  fe: "from-amber-500 to-yellow-500",
  market_prediction: "from-cyan-500 to-blue-500",
};

/** 预设 query 的首段，与后端 build_optimized_query 的「用户词」一致 */
function firstTermFromPresetQuery(presetQuery: string | undefined): string {
  if (!presetQuery?.trim()) return "";
  return presetQuery.split(" OR ")[0]?.trim() ?? "";
}

export default function TaskCreateForm() {
  const router = useRouter();
  const { presets, fetchPresets, createTask, isLoading } = useTaskStore();
  const [query, setQuery] = useState("");
  const [domainPreset, setDomainPreset] = useState("sre");
  const [maxResults, setMaxResults] = useState(10);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [preview, setPreview] = useState<ArxivPreviewSearchResult | null>(null);

  useEffect(() => {
    fetchPresets();
  }, [fetchPresets]);

  /**
   * 默认选中 SRE 时不会触发主题卡 onClick，搜索框曾长期为空 → 预览/创建误报「请先输入」。
   * 仅在预设加载或切换主题时，若输入仍为空则填入该主题默认检索词（不依赖 query，避免清空后被立刻写回）。
   */
  useEffect(() => {
    if (domainPreset === "custom") return;
    if (presets.length === 0) return;
    const preset = presets.find((p) => p.key === domainPreset);
    const hint = firstTermFromPresetQuery(preset?.query);
    if (!hint) return;
    setQuery((prev) => (prev.trim() === "" ? hint : prev));
  }, [presets, domainPreset]);

  const getEffectiveQuery = useCallback((): string => {
    const typed = query.trim();
    if (typed) return typed;
    if (domainPreset === "custom") return "";
    const preset = presets.find((p) => p.key === domainPreset);
    return firstTermFromPresetQuery(preset?.query);
  }, [query, domainPreset, presets]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const q = getEffectiveQuery();
    if (!q) {
      toast.error(
        domainPreset === "custom"
          ? "自定义模式下请在搜索框输入 arXiv 检索式"
          : "请输入搜索查询，或等待主题预设加载完成"
      );
      return;
    }

    try {
      const taskId = await createTask({
        query: q,
        domain_preset: domainPreset,
        max_results: maxResults,
      });
      if (taskId) {
        toast.success("任务已创建，正在打开进度页…");
        router.push(`/tasks/${taskId}`);
      } else {
        toast.error("创建任务失败: 返回的任务ID为空");
      }
    } catch (error) {
      toast.error(`创建任务失败: ${error}`);
    }
  };

  const handleTopicSelect = (key: string) => {
    setDomainPreset(key);
    // Find the preset to use its query as a hint
    const preset = presets.find((p) => p.key === key);
    if (preset?.query) {
      // 取第一个查询词（按 " OR " 分割）
      const firstQuery = preset.query.split(" OR ")[0]?.trim();
      if (firstQuery) {
        setQuery(firstQuery);
      }
    }
  };

  const handlePreviewSearch = async () => {
    const q = getEffectiveQuery();
    if (!q) {
      toast.error(
        domainPreset === "custom"
          ? "自定义模式下请先输入检索式再预览"
          : "请先输入搜索查询，或等待主题预设加载完成"
      );
      return;
    }
    setPreviewLoading(true);
    setPreview(null);
    try {
      const limit = Math.min(Math.max(maxResults, 5), 25);
      const data = await arxivApi.previewSearch({
        query: q,
        domain_preset: domainPreset,
        limit,
      });
      setPreview(data);
      if (data.returned === 0) {
        toast.error("arXiv 未返回结果，可换关键词或改用「自定义」预设");
      } else {
        toast.success(`预览到 ${data.returned} 条，请确认后再创建任务`);
      }
    } catch (e) {
      toast.error(`预览失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setPreviewLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Topic Selector */}
      <div className="space-y-3">
        <label className="text-sm font-medium flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-primary" />
          选择研究主题
        </label>
        <div className="grid grid-cols-2 gap-2">
          {presets.filter(p => p.key !== "custom").map((preset) => {
            const Icon = topicIcons[preset.key] || Search;
            const colorClass = topicColors[preset.key] || "from-gray-500 to-gray-600";
            const isSelected = domainPreset === preset.key;

            return (
              <button
                key={preset.key}
                type="button"
                onClick={() => handleTopicSelect(preset.key)}
                className={cn(
                  "relative p-3 rounded-xl border-2 transition-all duration-200 text-left",
                  isSelected
                    ? "border-primary bg-primary/5 shadow-sm"
                    : "border-transparent bg-muted/50 hover:bg-muted"
                )}
              >
                <div className="flex items-center gap-2">
                  <div className={cn(
                    "w-8 h-8 rounded-lg bg-gradient-to-br flex items-center justify-center",
                    colorClass
                  )}>
                    <Icon className="w-4 h-4 text-white" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-medium text-sm truncate">{preset.name}</p>
                    <p className="text-xs text-muted-foreground truncate">{preset.name_en}</p>
                  </div>
                </div>
                {isSelected && (
                  <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-primary flex items-center justify-center">
                    <div className="w-1.5 h-1.5 rounded-full bg-white" />
                  </div>
                )}
              </button>
            );
          })}
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          以上主题与「预览 arXiv」「创建抓取任务」共用同一套后端逻辑；各主题仅提示词、排除词、学科支路不同。你在搜索框里输入的内容会参与全库匹配，并与该主题的领域支路做「或」组合，不再出现「选了 SRE 就搜不到人工智能」那种整段被 cat
          锁死的情况。选「自定义」时则完全使用下方输入框里的检索式（需符合 arXiv 语法）。
        </p>
        <button
          type="button"
          onClick={() => setDomainPreset("custom")}
          className={cn(
            "w-full rounded-xl border px-3 py-2 text-left text-sm transition-colors",
            domainPreset === "custom"
              ? "border-amber-700 bg-amber-50 text-amber-950"
              : "border-dashed border-stone-300 bg-stone-50/80 text-stone-600 hover:bg-amber-50/60"
          )}
        >
          <span className="font-medium">自定义检索</span>
          <span className="block text-xs text-muted-foreground">
            不加领域类别/排除词，检索式即下方输入框内容（适合先试词再抓取）
          </span>
        </button>
      </div>

      {/* Search Query */}
      <div className="space-y-2">
        <label className="text-sm font-medium flex items-center gap-2">
          <Search className="w-4 h-4 text-primary" />
          搜索查询
        </label>
        <Input
          placeholder="例如: site reliability engineering"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="h-11 rounded-xl"
        />
        <p className="text-xs text-muted-foreground">
          建议先点「预览 arXiv」确认能命中。上方「研究主题」只叠加领域提示与过滤，不会再把你输入的关键词锁死在某个
          arXiv 小类里（例如误选 SRE 仍可直接搜人工智能）。
        </p>
      </div>

      {/* Max Results */}
      <div className="space-y-2">
        <label className="text-sm font-medium flex items-center gap-2">
          <Rocket className="w-4 h-4 text-primary" />
          最大论文数: <span className="font-mono font-bold text-primary">{maxResults}</span>
        </label>
        <input
          type="range"
          min="1"
          max="50"
          value={maxResults}
          onChange={(e) => setMaxResults(Number(e.target.value))}
          className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>1</span>
          <span>50</span>
        </div>
      </div>

      {/* Preview */}
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button
          type="button"
          variant="outline"
          className="h-11 flex-1 rounded-xl border-stone-300 bg-white hover:bg-amber-50"
          onClick={handlePreviewSearch}
          disabled={previewLoading || isLoading}
        >
          {previewLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              检索中…
            </>
          ) : (
            <>
              <Search className="mr-2 h-4 w-4" />
              预览 arXiv
            </>
          )}
        </Button>
        <Button
          type="submit"
          className="h-11 flex-1 rounded-xl bg-gradient-primary font-medium hover:opacity-90"
          disabled={isLoading || previewLoading}
        >
          {isLoading ? (
            <span className="animate-pulse">创建中...</span>
          ) : (
            <>
              <Rocket className="mr-2 h-5 w-5" />
              创建抓取任务
            </>
          )}
        </Button>
      </div>

      {preview && (
        <Card className="space-y-3 border-amber-200/80 bg-gradient-to-b from-amber-50/90 to-stone-50/80 p-4 shadow-sm">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
              实际发往 arXiv 的检索式
            </p>
            <code className="mt-1 block max-h-24 overflow-auto rounded-lg border border-stone-200/90 bg-white/90 p-2 text-[11px] leading-snug text-stone-800">
              {preview.optimized_query || "（空）"}
            </code>
          </div>
          <p className="text-xs text-stone-600">
            共 <span className="font-mono font-semibold">{preview.returned}</span>{" "}
            条（仅元数据预览）。{preview.note}
          </p>
          <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
            {preview.papers.map((p) => (
              <div
                key={p.arxiv_id}
                className="rounded-lg border border-stone-200/80 bg-white/95 p-3 text-sm shadow-sm"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="min-w-0 font-medium leading-snug text-stone-900">
                    {p.title || p.arxiv_id}
                  </p>
                  <a
                    href={`https://arxiv.org/abs/${p.arxiv_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0 text-amber-800 hover:text-amber-950"
                    aria-label="在 arXiv 打开"
                  >
                    <ExternalLink className="h-4 w-4" />
                  </a>
                </div>
                <p className="mt-1 text-xs text-stone-500">
                  <span className="font-mono text-amber-900/90">{p.arxiv_id}</span>
                  {p.published_date ? ` · ${p.published_date}` : null}
                  {p.authors?.length ? ` · ${p.authors.slice(0, 3).join(", ")}${p.authors.length > 3 ? "…" : ""}` : null}
                </p>
                {p.summary_preview ? (
                  <p className="mt-2 text-xs leading-relaxed text-stone-600">
                    {p.summary_preview}
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        </Card>
      )}
    </form>
  );
}
