"use client";

import { useSession } from "@/components/providers/SupabaseProvider";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import {
  adminApi,
  meApi,
  type AdminUserRow,
  type HealGraphResult,
  type ImportGraphResult,
  type SystemSettingsDto,
  type SystemStatusDto,
} from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Database,
  Download,
  FileJson,
  KeyRound,
  Settings2,
  ShieldAlert,
  Trash2,
  Upload,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

type TabKey = "users" | "system" | "config";

export default function AdminPage() {
  const session = useSession();
  const router = useRouter();
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [tab, setTab] = useState<TabKey>("users");

  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);

  const [status, setStatus] = useState<SystemStatusDto | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);

  const [settings, setSettings] = useState<SystemSettingsDto | null>(null);
  const [settingsDraft, setSettingsDraft] = useState<SystemSettingsDto | null>(
    null
  );
  const [settingsSaving, setSettingsSaving] = useState(false);

  const [healLoading, setHealLoading] = useState(false);
  const [healResult, setHealResult] = useState<HealGraphResult | null>(null);
  const [wipeLoading, setWipeLoading] = useState(false);
  const [wipeModalOpen, setWipeModalOpen] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [includeEmbeddingsExport, setIncludeEmbeddingsExport] = useState(true);
  const [importMode, setImportMode] = useState<"merge" | "replace">("merge");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importReplaceModalOpen, setImportReplaceModalOpen] = useState(false);
  const importFileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!session) {
      router.replace("/login?next=/admin");
      return;
    }
    let cancelled = false;
    void meApi
      .getMe()
      .then((m) => {
        if (cancelled) return;
        if (m.profile.role !== "admin") {
          setAllowed(false);
          toast.error(
            `需要管理员权限。后端读到：user_id=${m.user_id}，profile.role=${m.profile.role}。请在「同一 Supabase 项目」里执行 update public.profiles set role = 'admin' where id = '${m.user_id}';（与 JWT 的 sub 必须一致）`
          );
          return;
        }
        setAllowed(true);
      })
      .catch(() => {
        if (!cancelled) setAllowed(false);
      });
    return () => {
      cancelled = true;
    };
  }, [session, router]);

  const loadUsers = useCallback(async () => {
    setUsersLoading(true);
    try {
      const rows = await adminApi.listUsers();
      setUsers(rows);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "加载用户失败");
    } finally {
      setUsersLoading(false);
    }
  }, []);

  const loadStatus = useCallback(async () => {
    setStatusLoading(true);
    try {
      const s = await adminApi.getSystemStatus();
      setStatus(s);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "加载系统状态失败");
    } finally {
      setStatusLoading(false);
    }
  }, []);

  const loadSettings = useCallback(async () => {
    try {
      const s = await adminApi.getSystemSettings();
      setSettings(s);
      setSettingsDraft(s);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "加载配置失败");
    }
  }, []);

  useEffect(() => {
    if (!allowed) return;
    if (tab === "users") void loadUsers();
    if (tab === "system") void loadStatus();
    if (tab === "config") void loadSettings();
  }, [allowed, tab, loadUsers, loadStatus, loadSettings]);

  const runHeal = async () => {
    setHealLoading(true);
    setHealResult(null);
    try {
      const data = await adminApi.healGraph();
      setHealResult(data);
      toast.success("图谱自愈已完成");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "自愈失败");
    } finally {
      setHealLoading(false);
    }
  };

  const runExport = async () => {
    setExportLoading(true);
    try {
      const blob = await adminApi.exportGraph({
        includeEmbeddings: includeEmbeddingsExport,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `arxprism-graph-export-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("已下载图快照 JSON");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "导出失败");
    } finally {
      setExportLoading(false);
    }
  };

  const runImport = async () => {
    const f = importFile;
    if (!f) return;
    setImportReplaceModalOpen(false);
    setImportLoading(true);
    try {
      const r: ImportGraphResult = await adminApi.importGraph(f, importMode);
      toast.success(
        `导入完成：节点 ${r.nodes_upserted}，关系 ${r.relationships_upserted}` +
          (r.nodes_skipped || r.relationships_skipped
            ? `（跳过 节点 ${r.nodes_skipped} / 关系 ${r.relationships_skipped}）`
            : "")
      );
      setImportFile(null);
      if (importFileRef.current) importFileRef.current.value = "";
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "导入失败");
    } finally {
      setImportLoading(false);
    }
  };

  const executeWipe = async () => {
    setWipeModalOpen(false);
    setWipeLoading(true);
    try {
      const data = await adminApi.clearAllData();
      toast.success(
        `已清空：Neo4j 删除 ${data.neo4j?.nodes_deleted ?? "?"} 个节点`
      );
      if (data.redis_warning) toast.error(`Redis：${data.redis_warning}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "清空失败");
    } finally {
      setWipeLoading(false);
    }
  };

  const saveSettings = async () => {
    if (!settingsDraft) return;
    setSettingsSaving(true);
    try {
      await adminApi.patchSystemSettings({
        triage_threshold: settingsDraft.triage_threshold,
        html_first_enabled: settingsDraft.html_first_enabled,
      });
      setSettings(settingsDraft);
      toast.success("系统配置已保存");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSettingsSaving(false);
    }
  };

  const onUserAction = async (
    u: AdminUserRow,
    action: "ban" | "unban" | "refill" | "role"
  ) => {
    try {
      if (action === "ban") await adminApi.banUser(u.id);
      else if (action === "unban") await adminApi.unbanUser(u.id);
      else if (action === "refill") await adminApi.refillQuota(u.id);
      else if (action === "role") {
        const nextRole = u.role === "admin" ? "user" : "admin";
        await adminApi.patchUser(u.id, { role: nextRole });
      }
      toast.success("已更新");
      void loadUsers();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "操作失败");
    }
  };

  const onWipeKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape") setWipeModalOpen(false);
  }, []);

  useEffect(() => {
    if (!wipeModalOpen) return;
    document.addEventListener("keydown", onWipeKeyDown);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onWipeKeyDown);
      document.body.style.overflow = prev;
    };
  }, [wipeModalOpen, onWipeKeyDown]);

  const onImportReplaceKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape") setImportReplaceModalOpen(false);
  }, []);

  useEffect(() => {
    if (!importReplaceModalOpen) return;
    document.addEventListener("keydown", onImportReplaceKeyDown);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onImportReplaceKeyDown);
      document.body.style.overflow = prev;
    };
  }, [importReplaceModalOpen, onImportReplaceKeyDown]);

  if (!session || allowed === null) {
    return (
      <div className="warm-page py-16 text-center text-stone-500">校验权限中…</div>
    );
  }

  if (!allowed) {
    return (
      <div className="warm-page space-y-4 py-16 text-center">
        <p className="text-stone-700">无权访问管理后台。</p>
        <Link href="/">
          <Button className="rounded-xl">返回首页</Button>
        </Link>
      </div>
    );
  }

  const tabs: { key: TabKey; label: string; icon: typeof Users }[] = [
    { key: "users", label: "用户管理", icon: Users },
    { key: "system", label: "系统状态", icon: Database },
    { key: "config", label: "系统配置", icon: Settings2 },
  ];

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
            控制中心
          </h1>
          <p className="mt-1 text-sm text-stone-600">
            Supabase 管理员会话；危险操作请仅在可信环境使用。
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-stone-200 pb-2">
        {tabs.map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={cn(
                "flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-amber-100 text-amber-950 ring-1 ring-amber-200"
                  : "text-stone-600 hover:bg-stone-100"
              )}
            >
              <Icon className="h-4 w-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === "users" ? (
        <Card className="border border-stone-200 shadow-md">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-base">用户列表</CardTitle>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="rounded-xl"
              disabled={usersLoading}
              onClick={() => void loadUsers()}
            >
              刷新
            </Button>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b text-stone-500">
                  <th className="py-2 pr-2">邮箱</th>
                  <th className="py-2 pr-2">角色</th>
                  <th className="py-2 pr-2">配额</th>
                  <th className="py-2 pr-2">封禁</th>
                  <th className="py-2">操作</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-stone-100">
                    <td className="py-2 pr-2 font-mono text-xs">
                      {u.email ?? u.id.slice(0, 8)}
                    </td>
                    <td className="py-2 pr-2">{u.role}</td>
                    <td className="py-2 pr-2">
                      {u.quota_used} / {u.quota_limit}
                    </td>
                    <td className="py-2 pr-2">
                      {u.is_banned ? "是" : "否"}
                    </td>
                    <td className="py-2">
                      <div className="flex flex-wrap gap-1">
                        {u.is_banned ? (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="h-8 rounded-lg text-xs"
                            onClick={() => void onUserAction(u, "unban")}
                          >
                            解封
                          </Button>
                        ) : (
                          <Button
                            type="button"
                            size="sm"
                            variant="destructive"
                            className="h-8 rounded-lg text-xs"
                            onClick={() => void onUserAction(u, "ban")}
                          >
                            封禁
                          </Button>
                        )}
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="h-8 rounded-lg text-xs"
                          onClick={() => void onUserAction(u, "refill")}
                        >
                          重置配额
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="h-8 rounded-lg text-xs"
                          onClick={() => void onUserAction(u, "role")}
                        >
                          {u.role === "admin" ? "降为 user" : "升为 admin"}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!usersLoading && users.length === 0 ? (
              <p className="py-6 text-center text-stone-500">暂无用户数据</p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {tab === "system" ? (
        <div className="space-y-6">
          <Card className="border border-stone-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">运行概览</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-stone-200 bg-stone-50/80 p-4">
                <p className="text-xs text-stone-500">Neo4j 节点</p>
                <p className="text-2xl font-semibold text-stone-900">
                  {statusLoading
                    ? "…"
                    : status?.neo4j_node_count ?? "—"}
                </p>
              </div>
              <div className="rounded-xl border border-stone-200 bg-stone-50/80 p-4">
                <p className="text-xs text-stone-500">Celery 队列 (redis list)</p>
                <p className="text-2xl font-semibold text-stone-900">
                  {statusLoading
                    ? "…"
                    : status?.celery_queue_depth ?? "—"}
                </p>
              </div>
              <div className="rounded-xl border border-stone-200 bg-stone-50/80 p-4">
                <p className="text-xs text-stone-500">近期任务数</p>
                <p className="text-2xl font-semibold text-stone-900">
                  {statusLoading
                    ? "…"
                    : status?.recent_tasks_total ?? "—"}
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="rounded-xl sm:col-span-3"
                disabled={statusLoading}
                onClick={() => void loadStatus()}
              >
                刷新状态
              </Button>
            </CardContent>
          </Card>

          <Card className="border border-cyan-500/30 bg-gradient-to-b from-stone-950/[0.03] to-violet-950/[0.04] shadow-lg shadow-cyan-900/10">
            <CardHeader className="pb-2">
              <CardTitle className="text-base text-stone-900">
                图谱运维
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
              <Button
                type="button"
                disabled={healLoading}
                onClick={() => void runHeal()}
                className="h-12 flex-1 rounded-xl border-0 bg-gradient-to-r from-cyan-600 to-violet-600 font-semibold text-white shadow-md"
              >
                <Activity className="mr-2 h-4 w-4" />
                {healLoading ? "自愈中…" : "Heal Graph"}
              </Button>
              <Button
                type="button"
                variant="destructive"
                disabled={wipeLoading}
                onClick={() => setWipeModalOpen(true)}
                className="h-12 flex-1 rounded-xl"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                {wipeLoading ? "清空中…" : "清空图库 + 任务键"}
              </Button>
            </CardContent>
          </Card>

          <Card className="border border-stone-300/80 bg-white/95 shadow-md">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base text-stone-900">
                <FileJson className="h-5 w-5 text-cyan-700" />
                图数据导入 / 导出
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-col gap-3 rounded-xl border border-stone-200/90 bg-stone-50/50 p-4 sm:flex-row sm:items-center sm:justify-between">
                <label className="flex cursor-pointer items-center gap-2 text-sm text-stone-600">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-stone-400"
                    checked={includeEmbeddingsExport}
                    onChange={(e) => setIncludeEmbeddingsExport(e.target.checked)}
                  />
                  导出包含论文向量
                </label>
                <Button
                  type="button"
                  variant="outline"
                  disabled={exportLoading}
                  onClick={() => void runExport()}
                  className="h-11 rounded-xl"
                >
                  <Download className="mr-2 h-4 w-4" />
                  {exportLoading ? "导出中…" : "下载 JSON"}
                </Button>
              </div>
              <div className="space-y-3 rounded-xl border border-stone-200/90 bg-stone-50/50 p-4">
                <div className="flex flex-wrap gap-3 text-sm">
                  <label className="flex cursor-pointer items-center gap-2">
                    <input
                      type="radio"
                      name="importMode"
                      checked={importMode === "merge"}
                      onChange={() => setImportMode("merge")}
                    />
                    合并
                  </label>
                  <label className="flex cursor-pointer items-center gap-2">
                    <input
                      type="radio"
                      name="importMode"
                      checked={importMode === "replace"}
                      onChange={() => setImportMode("replace")}
                    />
                    替换
                  </label>
                </div>
                <input
                  ref={importFileRef}
                  type="file"
                  accept="application/json,.json"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    setImportFile(f ?? null);
                  }}
                />
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => importFileRef.current?.click()}
                  >
                    <Upload className="mr-2 h-4 w-4" />
                    选择文件
                  </Button>
                  <Button
                    type="button"
                    disabled={importLoading || !importFile}
                    onClick={() => {
                      if (importMode === "replace")
                        setImportReplaceModalOpen(true);
                      else void runImport();
                    }}
                  >
                    {importLoading ? "导入中…" : "导入"}
                  </Button>
                </div>
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
                <p>Method 数：{healResult.method_names_count}</p>
                <p>LLM 聚类：{healResult.clusters_from_llm}</p>
                <p>已融合节点：{healResult.alias_nodes_merged}</p>
              </CardContent>
            </Card>
          ) : null}
        </div>
      ) : null}

      {tab === "config" && settingsDraft ? (
        <Card className="max-w-lg border border-stone-200">
          <CardHeader>
            <CardTitle className="text-base">流水线开关</CardTitle>
            <p className="text-xs text-stone-500">
              写入{" "}
              <code className="rounded bg-muted px-1">system_settings</code>
              ，Worker 约 60s 内生效。
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-stone-800">
                分诊阈值（relevance_score ≥ 此值才抓取全文）
              </label>
              <Input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={settingsDraft.triage_threshold}
                onChange={(e) =>
                  setSettingsDraft({
                    ...settingsDraft,
                    triage_threshold: Number(e.target.value),
                  })
                }
                className="rounded-xl"
              />
            </div>
            <label className="flex cursor-pointer items-center gap-2 text-sm text-stone-700">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-stone-400"
                checked={settingsDraft.html_first_enabled}
                onChange={(e) =>
                  setSettingsDraft({
                    ...settingsDraft,
                    html_first_enabled: e.target.checked,
                  })
                }
              />
              启用 HTML-First 正文解析
            </label>
            <Button
              type="button"
              disabled={settingsSaving}
              onClick={() => void saveSettings()}
              className="rounded-xl bg-amber-700 text-white hover:bg-amber-800"
            >
              {settingsSaving ? "保存中…" : "保存配置"}
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {tab === "config" && !settingsDraft && settings === null ? (
        <p className="text-stone-500">加载配置中…</p>
      ) : null}

      {importReplaceModalOpen ? (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          role="presentation"
        >
          <button
            type="button"
            aria-label="关闭"
            className="absolute inset-0 bg-stone-950/55 backdrop-blur-[2px]"
            onClick={() => setImportReplaceModalOpen(false)}
          />
          <div
            role="dialog"
            aria-modal="true"
            className="relative z-[1] w-full max-w-md rounded-2xl border border-amber-300/90 bg-amber-50/98 p-6 shadow-xl"
          >
            <h2 className="text-lg font-bold text-stone-900">
              确认以「替换」模式导入？
            </h2>
            <p className="mt-2 text-sm text-stone-700">
              将先清空 Neo4j 再写入快照。
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Button
                variant="outline"
                className="rounded-xl"
                onClick={() => setImportReplaceModalOpen(false)}
              >
                取消
              </Button>
              <Button
                className="rounded-xl bg-amber-800 text-white"
                onClick={() => void runImport()}
              >
                确认导入
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {wipeModalOpen ? (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          role="presentation"
        >
          <button
            type="button"
            aria-label="关闭"
            className="absolute inset-0 bg-stone-950/55 backdrop-blur-[2px]"
            onClick={() => setWipeModalOpen(false)}
          />
          <div
            role="dialog"
            aria-modal="true"
            className="relative z-[1] w-full max-w-md overflow-hidden rounded-2xl border-2 border-red-300/90 bg-stone-50 p-6 shadow-xl"
          >
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-10 w-10 shrink-0 text-red-600" />
              <div>
                <h2 className="text-lg font-bold text-stone-900">
                  确认清空图库？
                </h2>
                <p className="mt-2 text-sm text-stone-700">
                  将删除 Neo4j 全部节点与关系，并清理 Redis 中{" "}
                  <code className="rounded bg-white px-1">arxprism:*</code>{" "}
                  任务键。
                </p>
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <Button
                variant="outline"
                className="rounded-xl"
                onClick={() => setWipeModalOpen(false)}
              >
                取消
              </Button>
              <Button
                variant="destructive"
                className="rounded-xl"
                onClick={() => void executeWipe()}
              >
                确认清空
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
