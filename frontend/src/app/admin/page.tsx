"use client";

import { useState } from "react";
import Link from "next/link";
import toast from "react-hot-toast";
import { adminApi, type HealGraphResult } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { ArrowLeft, Activity, Trash2, ShieldAlert } from "lucide-react";

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [healLoading, setHealLoading] = useState(false);
  const [wipeLoading, setWipeLoading] = useState(false);
  const [healResult, setHealResult] = useState<HealGraphResult | null>(null);

  const runHeal = async () => {
    const t = token.trim();
    if (!t) {
      toast.error("请先输入 Admin Token");
      return;
    }
    setHealLoading(true);
    setHealResult(null);
    try {
      const data = await adminApi.healGraph(t);
      setHealResult(data);
      toast.success("图谱自愈已完成");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (/403|Forbidden|Invalid or missing admin token|disabled/i.test(msg)) {
        toast.error("拒绝访问：Admin Token 无效或服务端未配置 ADMIN_RESET_TOKEN");
      } else {
        toast.error(msg || "自愈请求失败");
      }
    } finally {
      setHealLoading(false);
    }
  };

  const runWipe = async () => {
    const t = token.trim();
    if (!t) {
      toast.error("请先输入 Admin Token");
      return;
    }
    const ok = window.confirm(
      "确认清空 Neo4j 全库与 Redis 中 arxprism 任务键？此操作不可恢复。"
    );
    if (!ok) return;
    setWipeLoading(true);
    try {
      const data = await adminApi.clearAllData(t);
      toast.success(
        `已清空：Neo4j 删除 ${data.neo4j?.nodes_deleted ?? "?"} 个节点`
      );
      if (data.redis_warning) {
        toast.error(`Redis：${data.redis_warning}`);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (/403|Forbidden|Invalid or missing admin token|disabled/i.test(msg)) {
        toast.error("拒绝访问：Admin Token 无效或服务端未配置 ADMIN_RESET_TOKEN");
      } else {
        toast.error(msg || "清空失败");
      }
    } finally {
      setWipeLoading(false);
    }
  };

  return (
    <div className="warm-page space-y-6">
      <div className="flex items-start gap-3">
        <Link href="/">
          <Button
            variant="outline"
            size="icon"
            className="shrink-0 rounded-xl border-stone-400 bg-white/90"
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-stone-900">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-500/50 bg-gradient-to-br from-cyan-950/20 to-violet-950/25 text-cyan-700 shadow-inner">
              <ShieldAlert className="h-5 w-5" />
            </span>
            图谱指挥所
          </h1>
          <p className="mt-1 text-sm text-stone-600">
            架构师专用：实体自愈与危险操作。请勿在公网暴露且无 Token 保护时部署。
          </p>
        </div>
      </div>

      <Card className="border border-cyan-500/30 bg-gradient-to-b from-stone-950/[0.03] to-violet-950/[0.04] shadow-lg shadow-cyan-900/10">
        <CardHeader className="pb-2">
          <CardTitle className="text-base text-stone-900">
            管理员凭证
          </CardTitle>
          <p className="text-xs text-stone-500">
            与后端环境变量 <code className="rounded bg-muted px-1">ADMIN_RESET_TOKEN</code>{" "}
            一致；通过请求头{" "}
            <code className="rounded bg-muted px-1">X-ArxPrism-Admin-Token</code>{" "}
            传递。
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            type="password"
            autoComplete="off"
            placeholder="Admin Token"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            className="h-11 rounded-xl border-stone-300 font-mono text-sm"
          />

          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <Button
              type="button"
              disabled={healLoading}
              onClick={() => void runHeal()}
              className="h-12 flex-1 rounded-xl border-0 bg-gradient-to-r from-cyan-600 to-violet-600 font-semibold text-white shadow-md shadow-cyan-900/30 hover:from-cyan-500 hover:to-violet-500 disabled:opacity-60"
            >
              <Activity className="mr-2 h-4 w-4" />
              {healLoading ? "自愈中…" : "Heal Graph (实体自愈)"}
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={wipeLoading}
              onClick={() => void runWipe()}
              className="h-12 flex-1 rounded-xl border-2 border-red-600/80 bg-red-950/90 font-semibold text-red-50 shadow-lg shadow-red-900/40 hover:bg-red-900 disabled:opacity-60"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {wipeLoading ? "清空中…" : "Wipe Database (清空图谱)"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {healResult ? (
        <Card className="border border-emerald-500/40 bg-emerald-50/40">
          <CardHeader className="pb-2">
            <CardTitle className="text-base text-emerald-950">
              上次自愈结果
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm text-emerald-950">
            <p>
              <span className="font-medium text-emerald-900">Method 名称数：</span>{" "}
              {healResult.method_names_count}
            </p>
            <p>
              <span className="font-medium text-emerald-900">LLM 聚类数：</span>{" "}
              {healResult.clusters_from_llm}
            </p>
            <p>
              <span className="font-medium text-emerald-900">已应用聚类：</span>{" "}
              {healResult.clusters_applied}
            </p>
            <p>
              <span className="font-medium text-emerald-900">已融合别名节点：</span>{" "}
              {healResult.alias_nodes_merged}
            </p>
            {Array.isArray(healResult.skipped_clusters) &&
            healResult.skipped_clusters.length > 0 ? (
              <p className="text-xs text-emerald-800/90">
                跳过项：{healResult.skipped_clusters.length} 条（详见后端日志）
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
