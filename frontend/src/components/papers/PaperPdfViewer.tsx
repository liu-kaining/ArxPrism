"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import {
  ChevronLeft,
  ChevronRight,
  Loader2,
  Minus,
  Plus,
  RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

type ViewMode = "paginated" | "scroll";

type Props = {
  fileUrl: string;
  fallbackPdfHref: string;
  className?: string;
};

export default function PaperPdfViewer({
  fileUrl,
  fallbackPdfHref,
  className,
}: Props) {
  const [viewMode, setViewMode] = useState<ViewMode>("paginated");
  const [numPages, setNumPages] = useState(0);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1.05);
  const [err, setErr] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [pageWidth, setPageWidth] = useState(640);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const apply = () =>
      setPageWidth(Math.max(280, Math.floor(el.clientWidth - 56)));
    apply();
    const ro = new ResizeObserver(apply);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (viewMode === "scroll" && scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [viewMode]);

  const onLoadSuccess = useCallback(({ numPages: n }: { numPages: number }) => {
    setNumPages(n);
    setErr(null);
    setPageNumber(1);
  }, []);

  const onLoadError = useCallback(
    async (e: unknown) => {
      const msg =
        e instanceof Error
          ? e.message
          : typeof e === "object" && e && "message" in e
            ? String((e as { message?: unknown }).message)
            : "无法加载 PDF";
      let detail = msg || "无法加载 PDF";
      try {
        const r = await fetch(fileUrl);
        const ct = r.headers.get("content-type") ?? "";
        if (ct.includes("application/json")) {
          const j = (await r.json()) as { error?: string };
          if (j.error) detail = j.error;
        }
      } catch {
        /* keep pdf.js message */
      }
      setErr(detail);
    },
    [fileUrl]
  );

  const goPrev = () => setPageNumber((p) => Math.max(1, p - 1));
  const goNext = () => setPageNumber((p) => Math.min(numPages || 1, p + 1));

  const pageShell =
    "rounded-xl bg-white p-3 shadow-[0_4px_24px_-8px_rgba(0,0,0,0.18)] ring-1 ring-stone-200/80";

  return (
    <div
      className={cn(
        "flex min-h-[min(70vh,720px)] flex-col overflow-hidden rounded-2xl border border-stone-200/90 bg-white shadow-[0_8px_30px_-12px_rgba(120,90,60,0.25)]",
        className
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-amber-100/90 bg-gradient-to-r from-amber-50 via-orange-50/40 to-stone-50 px-3 py-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <div
            className="flex rounded-lg border border-stone-200/90 bg-white/90 p-0.5 shadow-sm"
            role="group"
            aria-label="阅读模式"
          >
            <button
              type="button"
              onClick={() => setViewMode("paginated")}
              disabled={!!err}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                viewMode === "paginated"
                  ? "bg-amber-200/90 text-amber-950 shadow-sm"
                  : "text-stone-600 hover:bg-amber-50/80 hover:text-stone-800"
              )}
            >
              翻页
            </button>
            <button
              type="button"
              onClick={() => setViewMode("scroll")}
              disabled={!!err}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                viewMode === "scroll"
                  ? "bg-amber-200/90 text-amber-950 shadow-sm"
                  : "text-stone-600 hover:bg-amber-50/80 hover:text-stone-800"
              )}
            >
              连续
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 border-stone-200 bg-white/90 text-stone-700 hover:bg-amber-50"
              onClick={goPrev}
              disabled={viewMode !== "paginated" || pageNumber <= 1 || !!err}
              aria-label="上一页"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="min-w-[7.5rem] text-center font-mono text-xs text-stone-600">
              {!numPages
                ? "—"
                : viewMode === "paginated"
                  ? `${pageNumber} / ${numPages}`
                  : `共 ${numPages} 页`}
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 border-stone-200 bg-white/90 text-stone-700 hover:bg-amber-50"
              onClick={goNext}
              disabled={
                viewMode !== "paginated" ||
                !numPages ||
                pageNumber >= numPages ||
                !!err
              }
              aria-label="下一页"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 border-stone-200 bg-white/90 text-stone-700 hover:bg-amber-50"
            onClick={() => setScale((s) => Math.max(0.65, Math.round((s - 0.1) * 100) / 100))}
            disabled={!!err}
            aria-label="缩小"
          >
            <Minus className="h-4 w-4" />
          </Button>
          <span className="w-12 text-center font-mono text-xs text-stone-600">
            {Math.round(scale * 100)}%
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 border-stone-200 bg-white/90 text-stone-700 hover:bg-amber-50"
            onClick={() => setScale((s) => Math.min(2.2, Math.round((s + 0.1) * 100) / 100))}
            disabled={!!err}
            aria-label="放大"
          >
            <Plus className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 border-stone-200 bg-white/90 text-stone-700 hover:bg-amber-50"
            onClick={() => setScale(1.05)}
            disabled={!!err}
            aria-label="重置缩放"
          >
            <RotateCcw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="relative flex-1 overflow-auto bg-gradient-to-b from-[#ebe6dd] to-[#e3ddd3] p-4"
      >
        {err ? (
          <div className="mx-auto max-w-md rounded-xl border border-amber-200/80 bg-amber-50/90 p-5 text-center text-sm text-stone-800">
            <p className="font-medium text-amber-900">预览加载失败</p>
            <p className="mt-2 text-stone-600">{err}</p>
            <a
              href={fallbackPdfHref}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 inline-flex rounded-lg bg-amber-800 px-4 py-2 text-sm font-medium text-amber-50 hover:bg-amber-900"
            >
              在浏览器中打开官方 PDF
            </a>
          </div>
        ) : (
          <Document
            file={fileUrl}
            loading={
              <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 text-stone-600">
                <Loader2 className="h-9 w-9 animate-spin text-amber-700" />
                <p className="text-sm">正在加载 PDF…</p>
              </div>
            }
            onLoadSuccess={onLoadSuccess}
            onLoadError={onLoadError}
            className={cn(
              viewMode === "scroll"
                ? "flex w-full flex-col items-center"
                : "flex justify-center"
            )}
          >
            {viewMode === "paginated" ? (
              <div className={pageShell}>
                <Page
                  pageNumber={pageNumber}
                  width={pageWidth}
                  scale={scale}
                  className="[&_.react-pdf__Page__canvas]:rounded-md"
                />
              </div>
            ) : (
              <div className="flex w-full flex-col items-center gap-5 pb-6 pt-1">
                {numPages > 0
                  ? Array.from({ length: numPages }, (_, i) => (
                      <div key={i + 1} className={pageShell}>
                        <Page
                          pageNumber={i + 1}
                          width={pageWidth}
                          scale={scale}
                          className="[&_.react-pdf__Page__canvas]:rounded-md"
                        />
                      </div>
                    ))
                  : null}
              </div>
            )}
          </Document>
        )}
      </div>
    </div>
  );
}
