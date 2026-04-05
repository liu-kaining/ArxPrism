"use client";

import { X, ExternalLink, FileText, Cpu, User, Database, BarChart3, Target, BookOpen } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import Link from "next/link";
import type { ApiGraphNode } from "@/lib/graph/paperGraphFlow";

interface NodeDetailPanelProps {
  node: ApiGraphNode | null;
  isOpen: boolean;
  onClose: () => void;
  onExpandNode?: (nodeId: string) => void;
}

// Helper to safely get string property
function getStringProp(props: Record<string, unknown> | undefined, key: string): string {
  if (!props) return "";
  const val = props[key];
  if (val == null) return "";
  return String(val);
}

// Helper to check if property exists and has content
function hasContent(props: Record<string, unknown> | undefined, key: string): boolean {
  if (!props) return false;
  const val = props[key];
  return val != null && val !== "" && (typeof val !== "object" || Array.isArray(val));
}

// Helper to get array property
function getArrayProp(props: Record<string, unknown> | undefined, key: string): unknown[] {
  if (!props) return [];
  const val = props[key];
  return Array.isArray(val) ? val : [];
}

export function NodeDetailPanel({
  node,
  isOpen,
  onClose,
  onExpandNode,
}: NodeDetailPanelProps) {
  if (!isOpen || !node) return null;

  const { labels, properties } = node;
  const primaryLabel = labels?.[0] || "Unknown";

  // Helper to get icon based on label
  const getIcon = () => {
    switch (primaryLabel) {
      case "Paper":
        return <FileText className="h-5 w-5 text-stone-600" />;
      case "Method":
        return <Cpu className="h-5 w-5 text-cyan-600" />;
      case "Author":
        return <User className="h-5 w-5 text-blue-600" />;
      case "Dataset":
        return <Database className="h-5 w-5 text-yellow-600" />;
      case "Metric":
        return <BarChart3 className="h-5 w-5 text-purple-600" />;
      case "Task":
        return <Target className="h-5 w-5 text-amber-600" />;
      default:
        return <BookOpen className="h-5 w-5 text-stone-600" />;
    }
  };

  // Get display title
  const displayTitle = getStringProp(properties, "title") ||
                       getStringProp(properties, "name") ||
                       getStringProp(properties, "original_name") ||
                       node.id;

  // Get relevant properties based on label type
  const getRelevantProperties = (): [string, unknown][] => {
    const skipKeys = new Set([
      "element_id", "labels", "title", "name", "original_name",
      "arxiv_id", "published_date", "core_architecture", "description",
      "summary", "authors", "key_innovations", "limitations"
    ]);

    return Object.entries(properties || {})
      .filter(([key]) => !skipKeys.has(key))
      .slice(0, 10) as [string, unknown][];
  };

  return (
    <div className="absolute right-0 top-0 z-50 h-full w-96 overflow-y-auto border-l border-stone-300 bg-stone-50 shadow-lg">
      {/* Header */}
      <div className="sticky top-0 flex items-center justify-between border-b border-stone-200 bg-stone-50 px-4 py-3">
        <div className="flex items-center gap-2">
          {getIcon()}
          <h3 className="font-semibold text-stone-900">{primaryLabel} Details</h3>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose} className="h-8 w-8 p-0">
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="p-4 space-y-4">
        {/* Title/Name */}
        <div>
          <h2 className="text-lg font-bold text-stone-900">{displayTitle}</h2>
          {primaryLabel === "Paper" && hasContent(properties, "arxiv_id") && (
            <p className="mt-1 font-mono text-xs text-cyan-600">
              arXiv: {getStringProp(properties, "arxiv_id")}
            </p>
          )}
          {primaryLabel === "Method" && hasContent(properties, "name") && (
            <p className="mt-1 font-mono text-xs text-cyan-600">
              Key: {getStringProp(properties, "name")}
            </p>
          )}
        </div>

        {/* Core Architecture (for Methods) */}
        {primaryLabel === "Method" && hasContent(properties, "core_architecture") && (
          <Card className="border-cyan-200 bg-cyan-50/50">
            <CardHeader className="pb-1">
              <CardTitle className="text-xs font-medium uppercase tracking-wide text-cyan-800">
                Core Architecture
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-stone-700">
                {getStringProp(properties, "core_architecture")}
              </p>
            </CardContent>
          </Card>
        )}

        {/* Key Properties based on type */}
        {primaryLabel === "Paper" && hasContent(properties, "summary") && (
          <Card className="border-stone-200">
            <CardHeader className="pb-1">
              <CardTitle className="text-xs font-medium uppercase tracking-wide text-stone-600">
                Abstract
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-stone-700 line-clamp-6">
                {getStringProp(properties, "summary")}
              </p>
            </CardContent>
          </Card>
        )}

        {primaryLabel === "Paper" && hasContent(properties, "authors") && (
          <Card className="border-stone-200">
            <CardHeader className="pb-1">
              <CardTitle className="text-xs font-medium uppercase tracking-wide text-stone-600">
                Authors
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-stone-700">
                {getArrayProp(properties, "authors").join(", ")}
              </p>
            </CardContent>
          </Card>
        )}

        {primaryLabel === "Method" && getArrayProp(properties, "key_innovations").length > 0 && (
          <Card className="border-purple-200 bg-purple-50/50">
            <CardHeader className="pb-1">
              <CardTitle className="text-xs font-medium uppercase tracking-wide text-purple-800">
                Key Innovations
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-1">
                {getArrayProp(properties, "key_innovations").map((innovation, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-sm text-stone-700">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-purple-500" />
                    {String(innovation)}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {primaryLabel === "Method" && getArrayProp(properties, "limitations").length > 0 && (
          <Card className="border-amber-200 bg-amber-50/50">
            <CardHeader className="pb-1">
              <CardTitle className="text-xs font-medium uppercase tracking-wide text-amber-800">
                Limitations
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-1">
                {getArrayProp(properties, "limitations").map((limitation, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-sm text-stone-700">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                    {String(limitation)}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {/* Published Date */}
        {hasContent(properties, "published_date") && (
          <div className="text-sm text-stone-600">
            <span className="font-medium">Published: </span>
            {getStringProp(properties, "published_date")}
          </div>
        )}

        {/* All Other Properties */}
        {getRelevantProperties().length > 0 && (
          <Card className="border-stone-200">
            <CardHeader className="pb-1">
              <CardTitle className="text-xs font-medium uppercase tracking-wide text-stone-600">
                Additional Properties
              </CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="space-y-2">
                {getRelevantProperties().map(([key, value]) => (
                  <div key={key} className="grid grid-cols-2 gap-2">
                    <dt className="font-mono text-[10px] text-stone-500 uppercase">
                      {key}
                    </dt>
                    <dd className="text-xs text-stone-700 truncate" title={String(value)}>
                      {String(value)}
                    </dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>
        )}

        {/* Action Buttons */}
        <div className="flex flex-col gap-2 pt-2">
          {primaryLabel === "Paper" && hasContent(properties, "arxiv_id") && (
            <Link href={`/papers/${getStringProp(properties, "arxiv_id")}`}>
              <Button variant="outline" className="w-full justify-start">
                <ExternalLink className="mr-2 h-4 w-4" />
                View Full Paper Details
              </Button>
            </Link>
          )}

          {primaryLabel === "Method" && hasContent(properties, "name") && (
            <Link href={`/evolution?method=${getStringProp(properties, "name")}`}>
              <Button variant="outline" className="w-full justify-start">
                <Cpu className="mr-2 h-4 w-4" />
                View Evolution Tree
              </Button>
            </Link>
          )}

          {onExpandNode && (
            <Button
              variant="outline"
              onClick={() => onExpandNode(node.id)}
              className="w-full justify-start"
            >
              <ExternalLink className="mr-2 h-4 w-4" />
              Expand from This Node
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
