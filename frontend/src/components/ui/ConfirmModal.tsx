"use client";

import * as React from "react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

export interface ConfirmModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmVariant?: "default" | "destructive";
  /** 失败时请 throw，弹窗会保持打开 */
  onConfirm: () => void | Promise<void>;
  icon?: React.ReactNode;
}

export function ConfirmModal({
  open,
  onClose,
  title,
  description,
  confirmLabel = "确定",
  cancelLabel = "取消",
  confirmVariant = "default",
  onConfirm,
  icon,
}: ConfirmModalProps) {
  const [pending, setPending] = React.useState(false);

  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !pending) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose, pending]);

  if (!open) return null;

  const handleConfirm = async () => {
    try {
      setPending(true);
      await onConfirm();
      onClose();
    } catch {
      // 调用方负责 toast；失败时不关闭
    } finally {
      setPending(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      role="presentation"
    >
      <button
        type="button"
        aria-label="关闭"
        className="absolute inset-0 bg-stone-950/40 backdrop-blur-[2px]"
        onClick={() => !pending && onClose()}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
        className={cn(
          "relative z-[1] w-full max-w-md overflow-hidden rounded-2xl",
          "border border-stone-200/90 bg-stone-50 p-6 shadow-xl"
        )}
      >
        <div className="flex items-start gap-3">
          {icon ? <div className="shrink-0">{icon}</div> : null}
          <div className="min-w-0 flex-1">
            <h2
              id="confirm-modal-title"
              className="text-lg font-semibold tracking-tight text-stone-900"
            >
              {title}
            </h2>
            {description ? (
              <p className="mt-2 text-sm leading-relaxed text-stone-600">
                {description}
              </p>
            ) : null}
          </div>
        </div>
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            className="rounded-xl"
            onClick={onClose}
            disabled={pending}
          >
            {cancelLabel}
          </Button>
          <Button
            type="button"
            variant={confirmVariant}
            className="rounded-xl"
            onClick={() => void handleConfirm()}
            disabled={pending}
          >
            {pending ? "请稍候…" : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
