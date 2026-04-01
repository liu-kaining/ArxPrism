"use client";

import { useEffect } from "react";
import { useTaskStore } from "@/lib/stores/taskStore";
import TaskCreateForm from "@/components/task/TaskCreateForm";
import TaskProgressCard from "@/components/task/TaskProgressCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";

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
      <div>
        <h1 className="text-3xl font-bold">任务管理</h1>
        <p className="text-muted-foreground mt-1">
          创建和管理论文抓取任务，实时追踪处理进度
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：创建任务表单 */}
        <div className="lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle>创建新任务</CardTitle>
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
            <Card>
              <CardHeader>
                <CardTitle>活跃任务</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-24 w-full" />
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : activeTasks.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>活跃任务 ({activeTasks.length})</CardTitle>
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
            <Card>
              <CardHeader>
                <CardTitle>活跃任务</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground text-center py-8">
                  暂无活跃任务
                </p>
              </CardContent>
            </Card>
          )}

          {/* 历史任务 */}
          {recentTasks.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>最近完成</CardTitle>
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
