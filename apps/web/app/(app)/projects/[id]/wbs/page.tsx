/**
 * WBS Page - Work Breakdown Structure View
 *
 * TASK-FRT-164: WBS Tree UI Component
 * IR-4: read-only view of the authoritative project WBS (procurement WBS store).
 * No create/edit/move actions are offered because no served endpoint persists them.
 *
 * PC-7a (#672/#688): shows the real WBS authority state from the single resolver
 * (PC-2a.3 / ADR-029) -- NO_WBS / DRAFT_ONLY / LEGACY_UNGOVERNED / APPROVED_BASELINE --
 * instead of silently implying every WBS is an approved baseline. Dates and budget on
 * the rows below are never approved schedule/cost authority, in every state.
 *
 * PC-7b (#672, board #1049): adds a live project-alerts panel (real
 * `GET /alerts/projects/{project_id}`, via `useProjectAlerts`) with an honest count
 * -- never implied before the fetch resolves -- and source-linked navigation using
 * only a real, persisted `source_clause_id`. No clause id is ever invented here.
 *
 * Test Suite ID: TASK-1427
 */

"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { env } from "@/config/env";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronRight, ChevronDown, Expand, Loader2 } from "lucide-react";
import { useWBSTree, type WBSTreeItem } from "@/hooks/useWBSTree";
import { useProjectAlerts } from "@/hooks/useProjectAlerts";
import { TechnicalWBSReviewPanel } from "@/components/features/wbs/TechnicalWBSReviewPanel";
import type { ProjectWBSAuthority } from "@/lib/api/generated/models";

const ALERT_SEVERITY_CLASSES: Record<string, string> = {
  critical: "border-red-200 bg-red-50 text-red-900",
  high: "border-orange-200 bg-orange-50 text-orange-900",
  medium: "border-amber-200 bg-amber-50 text-amber-900",
  low: "border-muted bg-muted/50 text-muted-foreground",
};

function WBSAlertsPanel({ projectId }: { projectId: string }) {
  const { alerts, loading, error } = useProjectAlerts(projectId);

  if (loading) {
    return (
      <Card data-testid="wbs-alerts-panel">
        <CardContent className="py-4 text-sm text-muted-foreground">
          Loading project alerts…
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card data-testid="wbs-alerts-panel">
        <CardContent className="py-4 text-sm text-red-800" data-testid="wbs-alerts-error">
          Failed to load project alerts: {error.message}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-testid="wbs-alerts-panel">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Project Alerts</CardTitle>
        <span className="text-sm text-muted-foreground" data-testid="wbs-alerts-count">
          {alerts.length === 1 ? "1 alert" : `${alerts.length} alerts`}
        </span>
      </CardHeader>
      <CardContent className="space-y-2">
        {alerts.length === 0 ? (
          <p className="text-sm text-muted-foreground">No alerts recorded for this project.</p>
        ) : (
          alerts.map((alert) => (
            <div
              key={alert.id}
              className={`rounded-lg border p-2 text-sm ${
                ALERT_SEVERITY_CLASSES[alert.severity] ?? ALERT_SEVERITY_CLASSES.low
              }`}
              data-testid={`wbs-alert-${alert.id}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span>{alert.title}</span>
                {alert.clauseId ? (
                  alert.addressableClauseId && alert.sourceDocumentId ? (
                    <Link
                      href={
                        `/projects/${encodeURIComponent(projectId)}/evidence` +
                        `?documentId=${encodeURIComponent(alert.sourceDocumentId)}` +
                        `&highlightId=${encodeURIComponent(alert.addressableClauseId)}`
                      }
                      className="shrink-0 font-mono text-xs underline"
                      aria-label={`View evidence for ${alert.addressableClauseId}`}
                      data-testid={`wbs-alert-${alert.id}-evidence-link`}
                    >
                      {alert.clauseId}
                    </Link>
                  ) : (
                    // A clause was reported by the detector but is not yet
                    // persisted/addressable -- shown for context, never linked.
                    <span
                      className="shrink-0 font-mono text-xs opacity-70"
                      data-testid={`wbs-alert-${alert.id}-clause`}
                    >
                      {alert.clauseId}
                    </span>
                  )
                ) : null}
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

const AUTHORITY_BANNER_CLASSES: Record<string, string> = {
  APPROVED_BASELINE: "border-green-200 bg-green-50 text-green-900",
  DRAFT_ONLY: "border-blue-200 bg-blue-50 text-blue-900",
  LEGACY_UNGOVERNED: "border-amber-200 bg-amber-50 text-amber-900",
  NO_WBS: "border-muted bg-muted/50 text-muted-foreground",
};

function WBSAuthorityBanner({ authority }: { authority: ProjectWBSAuthority }) {
  const bannerClasses =
    AUTHORITY_BANNER_CLASSES[authority.display_state] ?? AUTHORITY_BANNER_CLASSES.NO_WBS;

  return (
    <div
      className={`rounded-lg border p-3 ${bannerClasses}`}
      data-testid="wbs-authority-banner"
      data-authority-state={authority.display_state}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-medium" data-testid="wbs-authority-label">
            {authority.scope_label}
          </p>
          {authority.display_state === "APPROVED_BASELINE" && authority.applied_at ? (
            <p className="text-xs opacity-80" data-testid="wbs-authority-applied-at">
              Approved {authority.applied_at.slice(0, 10)}
            </p>
          ) : null}
        </div>
        {authority.draft_exists && authority.display_state !== "DRAFT_ONLY" ? (
          <span
            className="rounded border px-2 py-0.5 text-xs"
            data-testid="wbs-authority-draft-pending"
          >
            Open WBS change set
          </span>
        ) : null}
      </div>
      <p className="mt-1 text-xs opacity-80" data-testid="wbs-authority-disclaimer">
        Dates and budget below are informational only -- not approved schedule or cost
        authority.
      </p>
    </div>
  );
}

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
    coverage,
    authority,
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

      {authority ? <WBSAuthorityBanner authority={authority} /> : null}

      {coverage ? (
        <p className="text-sm text-muted-foreground" data-testid="wbs-coverage-summary">
          {coverage.total_items === 1 ? "1 item" : `${coverage.total_items} items`} total ·{" "}
          {coverage.items_with_budget} with budget · {coverage.items_with_dates} with dates
          {coverage.approved_scope_items ? (
            <> · {coverage.approved_scope_items} in the approved baseline</>
          ) : null}
          {coverage.unapproved_legacy_items ? (
            <> · {coverage.unapproved_legacy_items} unapproved legacy</>
          ) : null}
        </p>
      ) : null}

      <WBSAlertsPanel projectId={projectId} />
      <TechnicalWBSReviewPanel projectId={projectId} authority={authority} />

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
