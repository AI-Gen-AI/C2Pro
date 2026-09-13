/**
 * useWBSTree Hook
 *
 * Read-only WBS tree for a project, from the authoritative
 * GET /api/v1/projects/{project_id}/wbs contract (procurement WBS store):
 * root items with nested `children`.
 *
 * TASK-FRT-164: WBS Tree UI Component
 * IR-4: the in-memory WBS write routes this hook used to call were a second,
 * unread implementation of the same resource and are no longer served, so the
 * hook exposes no create/update/delete/move operations.
 */

import { useState, useCallback, useMemo } from "react";
import {
  useGetProjectWbsApiV1ProjectsProjectIdWbsGet,
  getGetProjectWbsApiV1ProjectsProjectIdWbsGetQueryKey,
} from "@/lib/api/generated/projects/projects";
import type { ProjectWBSNode } from "@/lib/api/generated/models";

export interface WBSTreeItem {
  id: string;
  code: string;
  name: string;
  level: number;
  itemType?: string | null;
  description?: string | null;
  budgetAllocated?: number | null;
  budgetSpent?: number;
  plannedStart?: string | null;
  plannedEnd?: string | null;
  children: WBSTreeItem[];
}

interface UseWBSTreeOptions {
  projectId: string;
  enabled?: boolean;
}

interface UseWBSTreeReturn {
  items: WBSTreeItem[];
  /** Every WBS item of the project (not only roots); null until loaded. */
  totalItems: number | null;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  expandedItems: Set<string>;
  toggleExpanded: (itemId: string) => void;
  expandAll: () => void;
  collapseAll: () => void;
  refetch: () => void;
}

const toTreeItem = (node: ProjectWBSNode): WBSTreeItem => ({
  id: node.id,
  code: node.code,
  name: node.name,
  level: node.level,
  itemType: node.item_type ?? null,
  description: node.description ?? null,
  budgetAllocated: node.budget_allocated ?? null,
  budgetSpent: node.budget_spent,
  plannedStart: node.planned_start ?? null,
  plannedEnd: node.planned_end ?? null,
  children: (node.children ?? []).map(toTreeItem),
});

export function useWBSTree({
  projectId,
  enabled = true,
}: UseWBSTreeOptions): UseWBSTreeReturn {
  const queryKey = getGetProjectWbsApiV1ProjectsProjectIdWbsGetQueryKey(projectId);
  const { data, isLoading, isError, error, refetch } =
    useGetProjectWbsApiV1ProjectsProjectIdWbsGet(projectId, {
      query: {
        enabled: !!projectId && enabled,
        queryKey,
      },
    });

  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

  const items = useMemo(() => (data?.items ?? []).map(toTreeItem), [data]);

  const toggleExpanded = useCallback((itemId: string) => {
    setExpandedItems((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  }, []);

  const expandAll = useCallback(() => {
    const ids = new Set<string>();
    const collect = (nodes: WBSTreeItem[]) => {
      nodes.forEach((node) => {
        if (node.children.length > 0) {
          ids.add(node.id);
          collect(node.children);
        }
      });
    };
    collect(items);
    setExpandedItems(ids);
  }, [items]);

  const collapseAll = useCallback(() => {
    setExpandedItems(new Set());
  }, []);

  return {
    items,
    totalItems: data?.total_items ?? null,
    isLoading,
    isError,
    error: error as Error | null,
    expandedItems,
    toggleExpanded,
    expandAll,
    collapseAll,
    refetch,
  };
}
