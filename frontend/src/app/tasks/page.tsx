"use client";

import { useEffect } from "react";
import { useTaskStore } from "@/lib/stores/taskStore";
import TaskCreateForm from "@/components/task/TaskCreateForm";
import TaskProgressCard from "@/components/task/TaskProgressCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { Rocket, Activity, History } from "lucide-react";

export default function TasksPage() {
  const {
    tasks,
    fetchTasks,
    isLoading,
    completedTasks,
    completedTotal,
    completedPage,
    completedPageSize,
    completedLoading,
    fetchCompletedPage,
  } = useTaskStore();

  useEffect(() => {
    fetchTasks();
    fetchCompletedPage(0);
  }, [fetchTasks, fetchCompletedPage]);

  const activeTasks = tasks.filter(
    (t) => t.status === "pending" || t.status === "running" || t.status === "paused"
  );
  const completedTotalPages = Math.max(
    1,
    Math.ceil(completedTotal / completedPageSize)
  );

  return (
    <div className="warm-page space-y-8">
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-amber-600 via-orange-700 to-amber-900 p-8 text-amber-50 shadow-md">
        <div className="relative z-10">
          <h1 className="flex items-center gap-3 text-3xl font-bold">
            <Rocket className="h-8 w-8" />
            论文抓取与知识图谱
          </h1>
          <p className="mt-2 max-w-xl text-amber-100/95">
            从 arXiv 智能抓取论文，自动提取核心问题、方法创新和实验数据，构建领域知识图谱
          </p>
        </div>
        <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-white/15 blur-2xl" />
        <div className="absolute -bottom-4 -left-4 h-24 w-24 rounded-full bg-amber-300/20 blur-xl" />
      </div>

      <div className="grid grid-cols-1 gap-6 stagger-children lg:grid-cols-3">
        <div className="lg:col-span-1">
          <Card className="card-hover border-border bg-card shadow-md">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg font-semibold">创建新任务</CardTitle>
            </CardHeader>
            <CardContent>
              <TaskCreateForm />
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2 space-y-6">
          {isLoading && tasks.length === 0 ? (
            <Card className="border-border bg-card shadow-md">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <Activity className="w-5 h-5 text-primary" />
                  活跃任务
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-24 w-full rounded-xl" />
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : activeTasks.length > 0 ? (
            <Card className="border-border bg-card shadow-md">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <Activity className="w-5 h-5 text-primary" />
                  活跃任务 ({activeTasks.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {activeTasks.map((task) => (
                    <TaskProgressCard key={task.task_id} task={task} />
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card className="border-border bg-card shadow-md">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <Activity className="w-5 h-5 text-primary" />
                  活跃任务
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-center py-12">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-muted flex items-center justify-center">
                    <Activity className="w-8 h-8 text-muted-foreground" />
                  </div>
                  <p className="text-muted-foreground">暂无活跃任务</p>
                  <p className="text-sm text-muted-foreground/70 mt-1">
                    在左侧创建新任务开始论文抓取
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          <Card className="border-border bg-card shadow-md">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg font-semibold flex items-center gap-2">
                <History className="w-5 h-5 text-muted-foreground" />
                最近完成
                {completedTotal > 0 ? (
                  <span className="text-sm font-normal text-muted-foreground">
                    （共 {completedTotal} 条，Redis 最近队列最多保留 100 条任务 ID）
                  </span>
                ) : null}
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                已结束任务含：完成、失败、取消。每页 {completedPageSize}{" "}
                条，可翻页浏览。
              </p>
            </CardHeader>
            <CardContent>
              {completedLoading && completedTasks.length === 0 ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-20 w-full rounded-xl" />
                  ))}
                </div>
              ) : completedTotal === 0 ? (
                <div className="py-10 text-center text-sm text-muted-foreground">
                  暂无已结束任务
                </div>
              ) : (
                <>
                  <div
                    className={`space-y-3 ${completedLoading ? "opacity-60" : ""}`}
                  >
                    {completedTasks.map((task) => (
                      <TaskProgressCard key={task.task_id} task={task} compact />
                    ))}
                  </div>
                  {completedTotal > completedPageSize ? (
                    <div className="mt-4 flex flex-wrap items-center justify-center gap-3">
                      <Button
                        variant="outline"
                        size="sm"
                        className="rounded-xl"
                        disabled={completedLoading || completedPage <= 0}
                        onClick={() =>
                          fetchCompletedPage(Math.max(0, completedPage - 1))
                        }
                      >
                        上一页
                      </Button>
                      <span className="text-sm text-muted-foreground tabular-nums">
                        第 {completedPage + 1} / {completedTotalPages} 页
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        className="rounded-xl"
                        disabled={
                          completedLoading ||
                          (completedPage + 1) * completedPageSize >=
                            completedTotal
                        }
                        onClick={() => fetchCompletedPage(completedPage + 1)}
                      >
                        下一页
                      </Button>
                    </div>
                  ) : null}
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
