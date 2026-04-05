"use client";

import { X, ExternalLink, GitBranch, FileText, TrendingUp, Award } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import type { MethodDetail, MethodPaper } from "@/lib/api/client";
import Link from "next/link";

interface MethodDetailPanelProps {
  method: MethodDetail | null;
  isOpen: boolean;
  onClose: () => void;
  onViewEvolution: (methodName: string) => void;
  onViewPapers: (methodName: string) => void;
}

export function MethodDetailPanel({
  method,
  isOpen,
  onClose,
  onViewEvolution,
  onViewPapers,
}: MethodDetailPanelProps) {
  if (!isOpen || !method) return null;

  return (
    <div className="absolute right-0 top-0 z-50 h-full w-96 overflow-y-auto border-l border-stone-300 bg-stone-50 shadow-lg">
      {/* Header */}
      <div className="sticky top-0 flex items-center justify-between border-b border-stone-200 bg-stone-50 px-4 py-3">
        <div className="flex items-center gap-2">
          <GitBranch className="h-5 w-5 text-cyan-600" />
          <h3 className="font-semibold text-stone-900">方法详情</h3>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose} className="h-8 w-8 p-0">
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="p-4 space-y-4">
        {/* Method Name */}
        <div>
          <h2 className="text-xl font-bold text-stone-900">{method.name}</h2>
          <p className="mt-1 font-mono text-xs text-stone-500">
            Key: {method.name_key}
          </p>
        </div>

        {/* Core Architecture */}
        {method.core_architecture && (
          <Card className="border-cyan-200 bg-cyan-50/50">
            <CardHeader className="pb-1">
              <CardTitle className="text-xs font-medium uppercase tracking-wide text-cyan-800">
                Core Architecture
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-stone-700">{method.core_architecture}</p>
            </CardContent>
          </Card>
        )}

        {/* Key Innovations */}
        {method.key_innovations && method.key_innovations.length > 0 && (
          <Card className="border-purple-200 bg-purple-50/50">
            <CardHeader className="pb-1">
              <CardTitle className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-purple-800">
                <Award className="h-3.5 w-3.5" />
                Key Innovations
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-1">
                {method.key_innovations.map((innovation, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-sm text-stone-700">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-purple-500" />
                    {innovation}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {/* Limitations */}
        {method.limitations && method.limitations.length > 0 && (
          <Card className="border-amber-200 bg-amber-50/50">
            <CardHeader className="pb-1">
              <CardTitle className="text-xs font-medium uppercase tracking-wide text-amber-800">
                Limitations
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-1">
                {method.limitations.map((limitation, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-sm text-stone-700">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                    {limitation}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {/* Evolution Stats */}
        <Card className="border-stone-200">
          <CardHeader className="pb-1">
            <CardTitle className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-stone-600">
              <TrendingUp className="h-3.5 w-3.5" />
              Evolution Statistics
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded bg-purple-100 p-2">
                <p className="text-lg font-bold text-purple-700">
                  {method.evolution_stats.ancestor_count}
                </p>
                <p className="text-[10px] text-purple-600">Ancestors</p>
              </div>
              <div className="rounded bg-cyan-100 p-2">
                <p className="text-lg font-bold text-cyan-700">
                  {method.evolution_stats.descendant_count}
                </p>
                <p className="text-[10px] text-cyan-600">Descendants</p>
              </div>
              <div className="rounded bg-orange-100 p-2">
                <p className="text-lg font-bold text-orange-700">
                  {method.evolution_stats.improves_count}
                </p>
                <p className="text-[10px] text-orange-600">Improves</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Related Papers (first 5) */}
        {method.papers && method.papers.length > 0 && (
          <Card className="border-stone-200">
            <CardHeader className="pb-1">
              <CardTitle className="flex items-center justify-between text-xs font-medium uppercase tracking-wide text-stone-600">
                <span className="flex items-center gap-1.5">
                  <FileText className="h-3.5 w-3.5" />
                  Proposing Papers ({method.papers_count})
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onViewPapers(method.name_key)}
                  className="h-6 px-2 text-[10px]"
                >
                  View All
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {method.papers.slice(0, 5).map((paper) => (
                  <Link
                    key={paper.arxiv_id}
                    href={`/graph?paper=${paper.arxiv_id}`}
                    className="block rounded p-2 hover:bg-stone-100 transition-colors"
                  >
                    <p className="font-mono text-[10px] text-cyan-600">{paper.arxiv_id}</p>
                    <p className="line-clamp-2 text-xs text-stone-700">{paper.title}</p>
                    {paper.published_date && (
                      <p className="mt-0.5 font-mono text-[9px] text-stone-400">
                        {paper.published_date}
                      </p>
                    )}
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Baselines */}
        {method.baselines && method.baselines.length > 0 && (
          <Card className="border-stone-200">
            <CardHeader className="pb-1">
              <CardTitle className="text-xs font-medium uppercase tracking-wide text-stone-600">
                Compared Against (Baselines)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {method.baselines.slice(0, 5).map((baseline, i) => (
                  <div key={i} className="rounded bg-stone-100 p-2">
                    <p className="text-xs font-medium text-stone-700">
                      {baseline.title || baseline.arxiv_id}
                    </p>
                    {baseline.dataset && (
                      <p className="mt-0.5 font-mono text-[10px] text-amber-600">
                        Dataset: {baseline.dataset}
                      </p>
                    )}
                    {baseline.improvement && (
                      <p className="font-mono text-[10px] text-green-600">
                        +{baseline.improvement}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Action Buttons */}
        <div className="flex flex-col gap-2 pt-2">
          <Button
            variant="outline"
            onClick={() => onViewEvolution(method.name_key)}
            className="w-full justify-start"
          >
            <GitBranch className="mr-2 h-4 w-4" />
            View Full Evolution Tree
          </Button>
          {method.papers_count > 0 && (
            <Button
              variant="outline"
              onClick={() => onViewPapers(method.name_key)}
              className="w-full justify-start"
            >
              <FileText className="mr-2 h-4 w-4" />
              View All {method.papers_count} Papers
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

interface MethodPapersPanelProps {
  methodName: string;
  papers: MethodPaper[];
  isOpen: boolean;
  onClose: () => void;
}

export function MethodPapersPanel({
  methodName,
  papers,
  isOpen,
  onClose,
}: MethodPapersPanelProps) {
  if (!isOpen) return null;

  const getRelationshipColor = (rel: string) => {
    switch (rel) {
      case "PROPOSES":
        return "bg-cyan-100 text-cyan-800 border-cyan-300";
      case "IMPROVES_UPON":
        return "bg-orange-100 text-orange-800 border-orange-300";
      case "BASELINE_FOR":
        return "bg-purple-100 text-purple-800 border-purple-300";
      default:
        return "bg-stone-100 text-stone-800 border-stone-300";
    }
  };

  return (
    <div className="absolute right-0 top-0 z-50 h-full w-[28rem] overflow-y-auto border-l border-stone-300 bg-stone-50 shadow-lg">
      {/* Header */}
      <div className="sticky top-0 flex items-center justify-between border-b border-stone-200 bg-stone-50 px-4 py-3">
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-cyan-600" />
          <h3 className="font-semibold text-stone-900">
            Papers for &quot;{methodName}&quot;
          </h3>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose} className="h-8 w-8 p-0">
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="p-4">
        <p className="mb-4 text-sm text-stone-600">
          Found {papers.length} papers related to this method.
        </p>

        <div className="space-y-3">
          {papers.map((paper, i) => (
            <Link
              key={`${paper.arxiv_id}-${i}`}
              href={`/graph?paper=${paper.arxiv_id}`}
              className="block rounded-lg border border-stone-200 bg-white p-3 shadow-sm hover:border-stone-300 hover:shadow transition-shadow"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <p className="font-mono text-[10px] text-cyan-600">{paper.arxiv_id}</p>
                  <p className="mt-1 text-sm font-medium text-stone-900">{paper.title}</p>
                  {paper.published_date && (
                    <p className="mt-0.5 font-mono text-[10px] text-stone-400">
                      {paper.published_date}
                    </p>
                  )}
                </div>
                <ExternalLink className="h-4 w-4 shrink-0 text-stone-400" />
              </div>

              <div className="mt-2 flex flex-wrap gap-2">
                <span
                  className={`inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[10px] ${getRelationshipColor(
                    paper.relationship
                  )}`}
                >
                  {paper.relationship}
                </span>
                {paper.dataset && (
                  <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 font-mono text-[10px] text-amber-700">
                    {paper.dataset}
                  </span>
                )}
                {paper.improvement && (
                  <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 font-mono text-[10px] text-green-700">
                    +{paper.improvement}
                  </span>
                )}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
