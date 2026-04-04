"use client";

import TaskCreateForm from "@/components/task/TaskCreateForm";
import RecentTasksPanel from "@/components/task/RecentTasksPanel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Rocket } from "lucide-react";

export default function TasksPage() {
  return (
    <div className="warm-page space-y-8">
      <div>
        <h1 className="flex items-center gap-3 text-2xl font-bold text-stone-900 md:text-3xl">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-amber-300/80 bg-amber-100">
            <Rocket className="h-5 w-5 text-amber-800" />
          </span>
          抓取任务
        </h1>
        <p className="mt-2 text-sm text-stone-600">
          从 arXiv 拉取论文并触发萃取流水线。创建成功后会<strong>自动打开进度详情页</strong>（
          <code className="rounded bg-muted px-1 font-mono text-xs">
            /tasks/任务ID
          </code>
          ）。下方「任务进度一览」可随时点回任意任务的详情；顶部默认主题会带出检索词，可直接预览。
        </p>
      </div>

      <RecentTasksPanel />

      <Card className="card-hover border-border bg-card shadow-md">
        <CardHeader className="pb-4">
          <CardTitle className="text-lg font-semibold">创建新任务</CardTitle>
        </CardHeader>
        <CardContent>
          <TaskCreateForm />
        </CardContent>
      </Card>
    </div>
  );
}
