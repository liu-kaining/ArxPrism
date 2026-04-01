"use client";

import { useState, useEffect } from "react";
import { useTaskStore } from "@/lib/stores/taskStore";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import toast from "react-hot-toast";
import {
  Rocket,
  Search,
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
  microservices: "from-slate-500 to-gray-500",
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

export default function TaskCreateForm() {
  const { presets, fetchPresets, createTask, isLoading } = useTaskStore();
  const [query, setQuery] = useState("");
  const [domainPreset, setDomainPreset] = useState("sre");
  const [maxResults, setMaxResults] = useState(10);

  useEffect(() => {
    fetchPresets();
  }, [fetchPresets]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!query.trim()) {
      toast.error("请输入搜索查询");
      return;
    }

    try {
      const taskId = await createTask({
        query: query.trim(),
        domain_preset: domainPreset,
        max_results: maxResults,
      });
      if (taskId) {
        toast.success(`任务已创建: ${taskId.slice(0, 8)}...`);
        setQuery("");
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
          系统会自动使用英文在 arXiv 搜索
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

      {/* Submit Button */}
      <Button type="submit" className="w-full h-12 rounded-xl bg-gradient-primary hover:opacity-90 transition-opacity font-medium" disabled={isLoading}>
        {isLoading ? (
          <span className="animate-pulse">创建中...</span>
        ) : (
          <>
            <Rocket className="w-5 h-5 mr-2" />
            创建任务
          </>
        )}
      </Button>
    </form>
  );
}
