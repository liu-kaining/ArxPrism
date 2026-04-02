"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useTaskStore } from "@/lib/stores/taskStore";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Progress } from "@/components/ui/Progress";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  ArrowLeft,
  Play,
  Pause,
  X,
  RotateCcw,
  AlertCircle,
  BookOpen,
} from "lucide-react";
import { formatDateTime } from "@/lib/utils";
import { paperResultStatusUi, taskStatusUi } from "@/lib/task-status";
import toast from "react-hot-toast";

export default function TaskDetailPage() {
  const params = useParams();
  const taskId = params.taskId as string;

  const {
    currentTask,
    fetchTask,
    pauseTask,
    resumeTask,
    cancelTask,
    retryTask,
    isLoading,
  } = useTaskStore();

  useEffect(() => {
    fetchTask(taskId);
    const interval = setInterval(() => {
      if (currentTask?.status === "running" || currentTask?.status === "pending") {
        fetchTask(taskId);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [taskId, currentTask?.status, fetchTask]);

  const handlePause = async () => {
    try {
      await pauseTask(taskId);
      toast.success("任务已暂停");
    } catch {
      toast.error("暂停失败");
    }
  };

  const handleResume = async () => {
    try {
      await resumeTask(taskId);
      toast.success("任务已恢复");
    } catch {
      toast.error("恢复失败");
    }
  };

  const handleCancel = async () => {
    if (!confirm("确定要取消该任务吗？")) return;
    try {
      await cancelTask(taskId);
      toast.success("任务已取消");
    } catch {
      toast.error("取消失败");
    }
  };

  const handleRetry = async () => {
    try {
      await retryTask(taskId);
      toast.success("任务已重试");
    } catch {
      toast.error("重试失败");
    }
  };

  if (isLoading && !currentTask) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-64" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (!currentTask) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive">任务不存在</p>
        <Link href="/" className="mt-4 inline-block">
          <Button variant="outline">返回首页</Button>
        </Link>
      </div>
    );
  }

  const task = currentTask;
  const status = taskStatusUi[task.status];
  const StatusIcon = status.icon;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Link href="/">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <StatusIcon className={`w-8 h-8 ${status.color}`} />
            <h1 className="text-2xl font-bold">任务详情</h1>
          </div>
          <p className="text-muted-foreground mt-2">
            {task.query} • {task.domain_preset}
          </p>
          <p className="text-sm text-muted-foreground">
            创建于 {formatDateTime(task.created_at)}
          </p>
        </div>
      </div>

      {/* Status & Progress */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center gap-2">
              <StatusIcon className={`w-6 h-6 ${status.color}`} />
              {status.label}
            </span>
            <span className={`text-lg font-medium ${status.color}`}>
              {task.progress.percentage}%
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Progress value={task.progress.percentage} className="h-3" />

          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold">{task.progress.total}</p>
              <p className="text-xs text-muted-foreground">总数</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{task.progress.processed}</p>
              <p className="text-xs text-muted-foreground">已处理</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-green-500">
                {task.progress.succeeded}
              </p>
              <p className="text-xs text-muted-foreground">成功</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-yellow-500">
                {task.progress.skipped}
              </p>
              <p className="text-xs text-muted-foreground">跳过</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-red-500">
                {task.progress.failed}
              </p>
              <p className="text-xs text-muted-foreground">失败</p>
            </div>
          </div>

          {task.progress.current_paper_title && (
            <div className="p-3 rounded bg-accent">
              <p className="text-sm text-muted-foreground">正在处理</p>
              <p className="font-medium truncate">{task.progress.current_paper_title}</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2 pt-4 border-t">
            {task.can_pause && (
              <Button variant="outline" onClick={handlePause}>
                <Pause className="w-4 h-4 mr-2" />
                暂停
              </Button>
            )}
            {task.can_resume && (
              <Button variant="outline" onClick={handleResume}>
                <Play className="w-4 h-4 mr-2" />
                恢复
              </Button>
            )}
            {task.can_cancel && (
              <Button variant="outline" onClick={handleCancel}>
                <X className="w-4 h-4 mr-2" />
                取消
              </Button>
            )}
            {task.can_retry && (
              <Button variant="outline" onClick={handleRetry}>
                <RotateCcw className="w-4 h-4 mr-2" />
                重试
              </Button>
            )}
          </div>

          {task.error_message && (
            <div className="p-3 rounded bg-destructive/10 text-destructive">
              <AlertCircle className="w-4 h-4 inline mr-2" />
              {task.error_message}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Results */}
      <Card>
        <CardHeader>
          <CardTitle>处理结果 ({task.results.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {task.results.length > 0 ? (
            <div className="space-y-3">
              {task.results.map((result) => {
                const resultStatus = paperResultStatusUi[result.status];

                const ResultIcon = resultStatus.icon;

                return (
                  <div
                    key={result.arxiv_id}
                    className="flex items-center justify-between p-3 rounded-lg border"
                  >
                    <div className="flex items-center gap-3">
                      <ResultIcon className={`w-5 h-5 ${resultStatus.color}`} />
                      <div>
                        <p className="font-medium">{result.title || result.arxiv_id}</p>
                        <p className="text-sm text-muted-foreground">
                          {result.message || result.status}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {result.method_name && (
                        <span className="text-sm text-primary">{result.method_name}</span>
                      )}
                      <Link href={`/papers/${result.arxiv_id}`}>
                        <Button variant="ghost" size="icon">
                          <BookOpen className="w-4 h-4" />
                        </Button>
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-muted-foreground text-center py-8">暂无处理结果</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
