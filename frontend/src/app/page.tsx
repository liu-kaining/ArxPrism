"use client";

import { useEffect } from "react";
import { useTaskStore } from "@/lib/stores/taskStore";
import TaskCreateForm from "@/components/task/TaskCreateForm";
import TaskProgressCard from "@/components/task/TaskProgressCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Rocket, Activity, History } from "lucide-react";

export default function HomePage() {
  const { tasks, fetchTasks, isLoading } = useTaskStore();

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // 分离活跃任务和历史任务
  const activeTasks = tasks.filter(
    (t) => t.status === "pending" || t.status === "running" || t.status === "paused"
  );
  const recentTasks = tasks.filter(
    (t) => !["pending", "running", "paused"].includes(t.status)
  ).slice(0, 10);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-primary p-8 text-white">
        <div className="relative z-10">
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Rocket className="w-8 h-8" />
            论文抓取与知识图谱
          </h1>
          <p className="mt-2 text-white/80 max-w-xl">
            从 arXiv 智能抓取论文，自动提取核心问题、方法创新和实验数据，构建领域知识图谱
          </p>
        </div>
        <div className="absolute -right-8 -top-8 w-32 h-32 rounded-full bg-white/10 blur-2xl" />
        <div className="absolute -bottom-4 -left-4 w-24 h-24 rounded-full bg-white/5 blur-xl" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 stagger-children">
        {/* 左侧：创建任务表单 */}
        <div className="lg:col-span-1">
          <Card className="card-hover border-0 shadow-lg">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg font-semibold">创建新任务</CardTitle>
            </CardHeader>
            <CardContent>
              <TaskCreateForm />
            </CardContent>
          </Card>
        </div>

        {/* 右侧：任务列表 */}
        <div className="lg:col-span-2 space-y-6">
          {/* 活跃任务 */}
          {isLoading && tasks.length === 0 ? (
            <Card className="border-0 shadow-lg">
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
            <Card className="border-0 shadow-lg">
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
            <Card className="border-0 shadow-lg">
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

          {/* 历史任务 */}
          {recentTasks.length > 0 && (
            <Card className="border-0 shadow-lg">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <History className="w-5 h-5 text-muted-foreground" />
                  最近完成
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {recentTasks.map((task) => (
                    <TaskProgressCard key={task.task_id} task={task} compact />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
