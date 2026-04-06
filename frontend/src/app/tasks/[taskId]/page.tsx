"use client";

import { Fragment, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useTaskStore } from "@/lib/stores/taskStore";
import { Button } from "@/components/ui/Button";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
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
  AlertTriangle,
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
    taskDetailLoading,
  } = useTaskStore();

  const [cancelConfirmOpen, setCancelConfirmOpen] = useState(false);

  // 必须用 focusDetail，否则 store 里 refreshCurrent 为 false，永远不会写入 currentTask
  useEffect(() => {
    if (taskId) {
      fetchTask(taskId, { focusDetail: true });
    }
  }, [taskId, fetchTask]);

  useEffect(() => {
    if (!taskId) return;
    const interval = setInterval(() => {
      const t = useTaskStore.getState().currentTask;
      if (
        t?.task_id === taskId &&
        (t.status === "running" || t.status === "pending")
      ) {
        fetchTask(taskId);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [taskId, fetchTask]);

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

  const confirmCancelTask = async () => {
    try {
      await cancelTask(taskId);
      toast.success("任务已取消");
    } catch {
      toast.error("取消失败");
      throw new Error("cancel failed");
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

  const cancelModal = (
    <ConfirmModal
      open={cancelConfirmOpen}
      onClose={() => setCancelConfirmOpen(false)}
      title="取消任务"
      description="确定要取消该任务吗？进度将停止，且不可恢复。"
      cancelLabel="保留任务"
      confirmLabel="确认取消"
      confirmVariant="destructive"
      icon={
        <AlertTriangle
          className="h-9 w-9 text-amber-600"
          aria-hidden
        />
      }
      onConfirm={confirmCancelTask}
    />
  );

  if (taskDetailLoading || (currentTask && currentTask.task_id !== taskId)) {
    return (
      <Fragment>
      <div className="warm-page space-y-6">
        <Skeleton className="h-12 w-64 rounded-lg bg-muted" />
        <Skeleton className="h-48 w-full rounded-xl bg-muted" />
      </div>
      {cancelModal}
      </Fragment>
    );
  }

  if (!currentTask) {
    return (
      <Fragment>
      <div className="warm-page py-12 text-center">
        <p className="text-destructive">任务不存在</p>
        <Link href="/papers" className="mt-4 inline-block">
          <Button variant="outline">返回论文列表</Button>
        </Link>
      </div>
      {cancelModal}
      </Fragment>
    );
  }

  const task = currentTask;
  const status = taskStatusUi[task.status];
  const StatusIcon = status.icon;

  return (
    <Fragment>
    <div className="warm-page space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Link href="/tasks">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <StatusIcon className={`w-8 h-8 ${status.color}`} />
            <h1 className="text-2xl font-bold text-stone-900">任务详情</h1>
          </div>
          <p className="text-muted-foreground mt-2">
            {task.query} • {task.domain_preset}
          </p>
          <p className="text-sm text-muted-foreground">
            创建于 {formatDateTime(task.created_at)}
          </p>
          {task.completion_summary && (
            <div className="mt-3 rounded-xl border border-amber-200/80 bg-amber-50/90 px-4 py-3 text-sm leading-relaxed text-stone-800">
              <span className="font-semibold text-amber-950">完成说明：</span>
              {task.completion_summary}
            </div>
          )}
        </div>
      </div>

      {/* Status & Progress */}
      <Card className="border-border bg-card shadow-sm">
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
              <Button
                variant="outline"
                onClick={() => setCancelConfirmOpen(true)}
              >
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
      <Card className="border-border bg-card shadow-sm">
        <CardHeader>
          <CardTitle>处理结果 ({task.results.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {task.results.length > 0 ? (
            <div className="space-y-3">
              {task.results.map((result) => {
                const resultStatus = paperResultStatusUi[result.status];

                const ResultIcon = resultStatus.icon;
                const canOpenInLibrary = result.status === "success";

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
                      {canOpenInLibrary ? (
                        <Link href={`/papers/${result.arxiv_id}`}>
                          <Button variant="ghost" size="icon" title="在本库中打开详情">
                            <BookOpen className="w-4 h-4" />
                          </Button>
                        </Link>
                      ) : (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          disabled
                          className="opacity-40"
                          title="仅成功入库的论文可打开详情；跳过或失败时本库可能无此篇"
                        >
                          <BookOpen className="w-4 h-4" />
                        </Button>
                      )}
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
    {cancelModal}
    </Fragment>
  );
}
