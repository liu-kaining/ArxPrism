"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Task } from "@/lib/api/client";
import { useTaskStore } from "@/lib/stores/taskStore";
import { Button } from "@/components/ui/Button";
import { Progress } from "@/components/ui/Progress";
import {
  Pause,
  Play,
  X,
  RotateCcw,
  ExternalLink,
  AlertCircle,
} from "lucide-react";
import { formatDateTime, truncate } from "@/lib/utils";
import { taskStatusUi } from "@/lib/task-status";
import toast from "react-hot-toast";

interface TaskProgressCardProps {
  task: Task;
  compact?: boolean;
}

export default function TaskProgressCard({ task, compact = false }: TaskProgressCardProps) {
  const { fetchTask, pauseTask, resumeTask, cancelTask, retryTask } = useTaskStore();
  const [isPolling, setIsPolling] = useState(false);

  const status = taskStatusUi[task.status];
  const StatusIcon = status.icon;
  const progress = task.progress.percentage || 0;

  // 轮询更新运行中的任务
  useEffect(() => {
    if (task.status !== "running" && task.status !== "pending") {
      setIsPolling(false);
      return;
    }

    setIsPolling(true);
    const interval = setInterval(() => {
      fetchTask(task.task_id);
    }, 3000);

    return () => {
      clearInterval(interval);
      setIsPolling(false);
    };
  }, [task.task_id, task.status, fetchTask]);

  const handlePause = async () => {
    try {
      await pauseTask(task.task_id);
      toast.success("任务已暂停");
    } catch {
      toast.error("暂停失败");
    }
  };

  const handleResume = async () => {
    try {
      await resumeTask(task.task_id);
      toast.success("任务已恢复");
    } catch {
      toast.error("恢复失败");
    }
  };

  const handleCancel = async () => {
    if (!confirm("确定要取消该任务吗？")) return;
    try {
      await cancelTask(task.task_id);
      toast.success("任务已取消");
    } catch {
      toast.error("取消失败");
    }
  };

  const handleRetry = async () => {
    try {
      await retryTask(task.task_id);
      toast.success("任务已重试");
    } catch {
      toast.error("重试失败");
    }
  };

  if (compact) {
    return (
      <div className="flex items-center justify-between p-3 rounded-lg border">
        <div className="flex items-center gap-3">
          <StatusIcon className={`w-5 h-5 ${status.color}`} />
          <div>
            <p className="font-medium text-sm">{truncate(task.query, 30)}</p>
            <p className="text-xs text-muted-foreground">
              {formatDateTime(task.created_at)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-sm ${status.color}`}>{status.label}</span>
          <Link href={`/tasks/${task.task_id}`}>
            <Button variant="ghost" size="icon">
              <ExternalLink className="w-4 h-4" />
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 rounded-lg border space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <StatusIcon className={`w-6 h-6 ${status.color}`} />
          <div>
            <p className="font-medium">{truncate(task.query, 40)}</p>
            <p className="text-xs text-muted-foreground">
              {task.domain_preset} • {formatDateTime(task.created_at)}
            </p>
          </div>
        </div>
        <span className={`text-sm font-medium ${status.color}`}>
          {status.label}
        </span>
      </div>

      {/* Progress */}
      {task.status === "running" || task.status === "pending" ? (
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>
              {task.progress.processed} / {task.progress.total} 篇
            </span>
            <span>{progress}%</span>
          </div>
          <Progress value={progress} className="h-2" />
          {task.progress.current_paper_title && (
            <p className="text-xs text-muted-foreground truncate">
              正在处理: {task.progress.current_paper_title}
            </p>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4 text-center">
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
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-2 border-t">
        {task.can_pause && (
          <Button variant="outline" size="sm" onClick={handlePause}>
            <Pause className="w-4 h-4 mr-1" />
            暂停
          </Button>
        )}
        {task.can_resume && (
          <Button variant="outline" size="sm" onClick={handleResume}>
            <Play className="w-4 h-4 mr-1" />
            恢复
          </Button>
        )}
        {task.can_cancel && (
          <Button variant="outline" size="sm" onClick={handleCancel}>
            <X className="w-4 h-4 mr-1" />
            取消
          </Button>
        )}
        {task.can_retry && (
          <Button variant="outline" size="sm" onClick={handleRetry}>
            <RotateCcw className="w-4 h-4 mr-1" />
            重试
          </Button>
        )}
        <div className="flex-1" />
        <Link href={`/tasks/${task.task_id}`}>
          <Button variant="ghost" size="sm">
            查看详情
            <ExternalLink className="w-4 h-4 ml-1" />
          </Button>
        </Link>
      </div>

      {/* Error message */}
      {task.error_message && (
        <div className="p-3 rounded bg-destructive/10 text-destructive text-sm">
          <AlertCircle className="w-4 h-4 inline mr-2" />
          {task.error_message}
        </div>
      )}
    </div>
  );
}
