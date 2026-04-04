"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { taskApi, type Task } from "@/lib/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { ListTodo, ChevronRight, RefreshCw } from "lucide-react";
import { taskStatusUi } from "@/lib/task-status";
import { cn } from "@/lib/utils";

export default function RecentTasksPanel() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await taskApi.listTasks({ limit: 20, offset: 0 });
      setTasks(res.tasks);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setTasks([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  return (
    <Card className="card-hover border-border bg-card shadow-md">
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 pb-2">
        <CardTitle className="flex items-center gap-2 text-lg font-semibold">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-amber-200 bg-amber-50 text-amber-900">
            <ListTodo className="h-4 w-4" />
          </span>
          任务进度一览
        </CardTitle>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="rounded-lg"
          onClick={() => void load()}
          disabled={loading}
        >
          <RefreshCw
            className={cn("mr-1.5 h-3.5 w-3.5", loading && "animate-spin")}
          />
          刷新
        </Button>
      </CardHeader>
      <CardContent className="pt-0">
        <p className="mb-3 text-xs text-muted-foreground">
          点击下方任一行进入<strong>进度详情页</strong>（暂停 / 取消 / 逐篇结果）。创建任务成功后也会自动跳转同一页面。
        </p>
        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-14 w-full rounded-xl" />
            ))}
          </div>
        ) : error ? (
          <p className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            加载失败：{error}
          </p>
        ) : tasks.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border bg-muted/40 px-4 py-6 text-center text-sm text-muted-foreground">
            暂无任务记录。创建抓取任务后，会出现在此列表；也可直接访问{" "}
            <code className="rounded bg-muted px-1 font-mono text-xs">
              /tasks/任务ID
            </code>
            。
          </p>
        ) : (
          <ul className="max-h-[min(28rem,55vh)] space-y-2 overflow-y-auto pr-1">
            {tasks.map((t) => {
              const ui = taskStatusUi[t.status];
              const Icon = ui.icon;
              const pct =
                t.progress.total > 0
                  ? Math.round(
                      (t.progress.processed / t.progress.total) * 100
                    )
                  : 0;
              return (
                <li key={t.task_id}>
                  <Link
                    href={`/tasks/${t.task_id}`}
                    className="flex items-center gap-3 rounded-xl border border-border bg-card px-3 py-2.5 transition-colors hover:border-amber-300/80 hover:bg-amber-50/40"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-black/5",
                            ui.color
                          )}
                        >
                          <Icon className="h-3 w-3" />
                          {ui.label}
                        </span>
                        <span className="font-mono text-[11px] text-muted-foreground">
                          {t.task_id.slice(0, 8)}…
                        </span>
                      </div>
                      <p className="mt-1 truncate text-sm font-medium text-foreground">
                        {t.query || "（无查询摘要）"}
                      </p>
                      <p className="mt-0.5 text-[11px] text-muted-foreground">
                        进度 {t.progress.processed}/{t.progress.total}
                        {t.progress.total > 0 ? ` · ${pct}%` : null}
                        {t.domain_preset
                          ? ` · 预设 ${t.domain_preset}`
                          : null}
                      </p>
                    </div>
                    <ChevronRight className="h-5 w-5 shrink-0 text-muted-foreground" />
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
        {!loading && !error && total > tasks.length ? (
          <p className="mt-2 text-center text-[11px] text-muted-foreground">
            共 {total} 条，此处显示最近 {tasks.length} 条
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
