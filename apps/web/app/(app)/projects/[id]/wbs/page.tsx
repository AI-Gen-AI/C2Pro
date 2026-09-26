/**
 * WBS Page - Work Breakdown Structure View
 *
 * TASK-FRT-164: WBS Tree UI Component
 * IR-4: read-only view of the authoritative project WBS (procurement WBS store).
 * No create/edit/move actions are offered because no served endpoint persists them.
 *
 * Test Suite ID: TASK-1427
 */

"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { env } from "@/config/env";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronRight, ChevronDown, Expand, Loader2 } from "lucide-react";
import { useWBSTree, type WBSTreeItem } from "@/hooks/useWBSTree";

function labelItemType(itemType: string | null | undefined): string | null {
  if (!itemType) return null;
  const words = itemType.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function plannedWindow(item: WBSTreeItem): string {
  const start = item.plannedStart?.slice(0, 10);
  const end = item.plannedEnd?.slice(0, 10);
  if (!start && !end) return "Not scheduled";
  return `${start ?? "?"} → ${end ?? "?"}`;
}

interface WBSTreeRowProps {
  item: WBSTreeItem;
  level?: number;
  expandedItems: Set<string>;
  onToggleExpand: (id: string) => void;
}

function WBSTreeRow({
  item,
  level = 0,
  expandedItems,
  onToggleExpand,
}: WBSTreeRowProps) {
  const isExpanded = expandedItems.has(item.id);
  const hasChildren = item.children.length > 0;
  const typeLabel = labelItemType(item.itemType);

  return (
    <div>
      <div
        className="flex items-center gap-2 py-2 hover:bg-muted/50"
        style={{ paddingLeft: `${level * 24}px` }}
        data-testid={`wbs-item-${item.id}`}
      >
        {hasChildren ? (
          <button
            onClick={() => onToggleExpand(item.id)}
            className="rounded p-1 hover:bg-muted"
            data-testid={`wbs-expand-${item.id}`}
            aria-label={`${isExpanded ? "Collapse" : "Expand"} ${item.code}`}
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>
        ) : (
          <span className="w-6" />
        )}

        <span
          className="w-20 font-mono text-sm text-muted-foreground"
          data-testid={`wbs-item-code-${item.code}`}
        >
          {item.code}
        </span>

        <div className="flex flex-1 items-center gap-2">
          <span className="font-medium">{item.name}</span>
          {typeLabel ? (
            <span className="rounded border px-1.5 py-0.5 text-xs text-muted-foreground">
              {typeLabel}
            </span>
          ) : null}
        </div>

        <span
          className="w-56 text-right text-sm text-muted-foreground"
          data-testid={`wbs-item-${item.id}-planned`}
        >
          {plannedWindow(item)}
        </span>
      </div>

      {isExpanded &&
        item.children.map((child) => (
          <WBSTreeRow
            key={child.id}
            item={child}
            level={level + 1}
            expandedItems={expandedItems}
            onToggleExpand={onToggleExpand}
          />
        ))}
    </div>
  );
}

export default function ProjectWBSPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params.id as string;

  useEffect(() => {
    if (!env.FEATURE_PHASE2_MODULES) {
      router.replace(`/projects/${projectId}`);
    }
  }, [router, projectId]);

  const {
    items,
    totalItems,
    isLoading,
    isError,
    error,
    expandedItems,
    toggleExpanded,
    expandAll,
  } = useWBSTree({ projectId });

  if (!env.FEATURE_PHASE2_MODULES) return null;

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4">
        <p className="text-red-800">Failed to load WBS: {error?.message}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="wbs-tree-view">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Work Breakdown Structure</h1>
          <p className="text-muted-foreground">
            Read-only view of the WBS items recorded for this project
          </p>
        </div>
        <Button
          variant="outline"
          onClick={expandAll}
          data-testid="wbs-expand-all-button"
        >
          <Expand className="mr-2 h-4 w-4" />
          Expand All
        </Button>
      </div>

      <Card data-testid="wbs-tree">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Project Structure</CardTitle>
          {totalItems !== null && items.length > 0 ? (
            <span className="text-sm text-muted-foreground">
              {totalItems === 1 ? "1 item" : `${totalItems} items`}
            </span>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-2">
          {items.length > 0 ? (
            items.map((item) => (
              <WBSTreeRow
                key={item.id}
                item={item}
                expandedItems={expandedItems}
                onToggleExpand={toggleExpanded}
              />
            ))
          ) : (
            <div className="py-8 text-center text-muted-foreground">
              No WBS items recorded for this project.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
