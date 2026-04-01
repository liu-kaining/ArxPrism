"use client";

import { useState, useEffect } from "react";
import { useTaskStore } from "@/lib/stores/taskStore";
import { Button } from "@/components/ui/Button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { Input } from "@/components/ui/Input";
import toast from "react-hot-toast";

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
      toast.success(`任务已创建: ${taskId.slice(0, 8)}...`);
      setQuery("");
    } catch (error) {
      toast.error(`创建任务失败: ${error}`);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* 领域预设 */}
      <div className="space-y-2">
        <label className="text-sm font-medium">领域预设</label>
        <Select value={domainPreset} onValueChange={setDomainPreset}>
          <SelectTrigger>
            <SelectValue placeholder="选择领域" />
          </SelectTrigger>
          <SelectContent>
            {presets.map((preset) => (
              <SelectItem key={preset.key} value={preset.key}>
                <div className="flex flex-col">
                  <span>{preset.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {preset.description}
                  </span>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* 搜索查询 */}
      <div className="space-y-2">
        <label className="text-sm font-medium">搜索查询</label>
        <Input
          placeholder="例如: site reliability engineering"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {/* 最大论文数 */}
      <div className="space-y-2">
        <label className="text-sm font-medium">最大论文数</label>
        <div className="flex items-center gap-4">
          <input
            type="range"
            min="1"
            max="50"
            value={maxResults}
            onChange={(e) => setMaxResults(Number(e.target.value))}
            className="flex-1"
          />
          <span className="w-12 text-center font-mono">{maxResults}</span>
        </div>
      </div>

      {/* 提交按钮 */}
      <Button type="submit" className="w-full" disabled={isLoading}>
        {isLoading ? "创建中..." : "🚀 创建任务"}
      </Button>
    </form>
  );
}
