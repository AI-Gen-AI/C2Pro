/**
 * useWBSTree Hook
 *
 * Provides WBS tree state management with CRUD and drag-drop operations.
 *
 * TASK-FRT-164: WBS Tree UI Component
 */

import { useState, useCallback, useMemo } from "react";
import {
  useGetWbsApiV1ProjectsProjectIdWbsGet,
  getGetWbsApiV1ProjectsProjectIdWbsGetQueryKey,
  useCreateWbsItemApiV1ProjectsProjectIdWbsItemsPost,
  useUpdateWbsItemApiV1ProjectsProjectIdWbsItemsItemIdPatch,
  useDeleteWbsItemApiV1ProjectsProjectIdWbsItemsItemIdDelete,
  useMoveWbsItemApiV1ProjectsProjectIdWbsItemsItemIdMovePost,
} from "@/lib/api/generated/wbs/wbs";
import type {
  WBSItemOutput,
  CreateWBSItemInput,
  UpdateWBSItemInput,
  MoveWBSItemInput,
} from "@/lib/api/generated/models";

export interface WBSTreeItem {
  id: string;
  code: string;
  name: string;
  level: number;
  completion: number;
  status?: string;
  budgetAllocated?: number;
  budgetSpent?: number;
  plannedStart?: string;
  plannedEnd?: string;
  children: WBSTreeItem[];
}

interface UseWBSTreeOptions {
  projectId: string;
  enabled?: boolean;
}

interface UseWBSTreeReturn {
  // Data
  items: WBSTreeItem[];
  isLoading: boolean;
  isError: boolean;
  error: Error | null;

  // CRUD Actions
  createItem: (input: CreateWBSItemInput) => Promise<WBSTreeItem | null>;
  updateItem: (
    itemId: string,
    input: UpdateWBSItemInput,
  ) => Promise<WBSTreeItem | null>;
  deleteItem: (itemId: string, cascade?: boolean) => Promise<boolean>;
  moveItem: (itemId: string, newParentId: string | null) => Promise<boolean>;

  // State
  selectedItem: WBSTreeItem | null;
  setSelectedItem: (item: WBSTreeItem | null) => void;
  expandedItems: Set<string>;
  toggleExpanded: (itemId: string) => void;
  expandAll: () => void;
  collapseAll: () => void;

  // Refresh
  refetch: () => void;
}

/**
 * Transform API response to WBSTreeItem format
 */
const transformToTreeItems = (items: WBSItemOutput[]): WBSTreeItem[] => {
  const itemMap = new Map<string, WBSTreeItem>();
  const rootItems: WBSTreeItem[] = [];

  // First pass: create all items
  items.forEach((item) => {
    itemMap.set(item.id, {
      id: item.id,
      code: item.code,
      name: item.name,
      level: item.level ?? 0,
      completion: item.completion ?? 0,
      budgetAllocated:
        typeof item.budget === "object" &&
        item.budget !== null &&
        "allocated" in item.budget &&
        typeof item.budget.allocated === "number"
          ? item.budget.allocated
          : undefined,
      budgetSpent:
        typeof item.budget === "object" &&
        item.budget !== null &&
        "spent" in item.budget &&
        typeof item.budget.spent === "number"
          ? item.budget.spent
          : undefined,
      plannedStart: item.start_date ?? undefined,
      plannedEnd: item.end_date ?? undefined,
      children: [],
    });
  });

  // Second pass: build tree structure
  items.forEach((item) => {
    const treeItem = itemMap.get(item.id)!;
    if (item.parent_id && itemMap.has(item.parent_id)) {
      const parent = itemMap.get(item.parent_id)!;
      parent.children.push(treeItem);
    } else {
      rootItems.push(treeItem);
    }
  });

  return rootItems;
};

export function useWBSTree({
  projectId,
  enabled = true,
}: UseWBSTreeOptions): UseWBSTreeReturn {
  // Query state
  const queryKey = getGetWbsApiV1ProjectsProjectIdWbsGetQueryKey(projectId);
  const { data, isLoading, isError, error, refetch } =
    useGetWbsApiV1ProjectsProjectIdWbsGet(projectId, {
      query: {
        enabled: !!projectId && enabled,
        queryKey,
      },
    });

  // Mutations
  const createMutation = useCreateWbsItemApiV1ProjectsProjectIdWbsItemsPost();
  const updateMutation =
    useUpdateWbsItemApiV1ProjectsProjectIdWbsItemsItemIdPatch();
  const deleteMutation =
    useDeleteWbsItemApiV1ProjectsProjectIdWbsItemsItemIdDelete();
  const moveMutation =
    useMoveWbsItemApiV1ProjectsProjectIdWbsItemsItemIdMovePost();

  // Local state
  const [selectedItem, setSelectedItem] = useState<WBSTreeItem | null>(null);
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

  // Transform data
  const items = useMemo(() => {
    if (!data) return [];
    return transformToTreeItems(data.items ?? []);
  }, [data]);

  // Toggle expanded
  const toggleExpanded = useCallback((itemId: string) => {
    setExpandedItems((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(itemId)) {
        newSet.delete(itemId);
      } else {
        newSet.add(itemId);
      }
      return newSet;
    });
  }, []);

  // Expand all
  const expandAll = useCallback(() => {
    const allIds = new Set<string>();
    const collectIds = (items: WBSTreeItem[]) => {
      items.forEach((item) => {
        if (item.children.length > 0) {
          allIds.add(item.id);
          collectIds(item.children);
        }
      });
    };
    collectIds(items);
    setExpandedItems(allIds);
  }, [items]);

  // Collapse all
  const collapseAll = useCallback(() => {
    setExpandedItems(new Set());
  }, []);

  // Create item
  const createItem = useCallback(
    async (input: CreateWBSItemInput): Promise<WBSTreeItem | null> => {
      const result = await createMutation.mutateAsync({
        projectId,
        data: input,
      });
      refetch();
      return result
        ? {
            id: result.id,
            code: result.code,
            name: result.name,
            level: result.level ?? 0,
            completion: result.completion ?? 0,
            plannedStart: result.start_date ?? undefined,
            plannedEnd: result.end_date ?? undefined,
            children: [],
          }
        : null;
    },
    [projectId, createMutation, refetch],
  );

  // Update item
  const updateItem = useCallback(
    async (
      itemId: string,
      input: UpdateWBSItemInput,
    ): Promise<WBSTreeItem | null> => {
      const result = await updateMutation.mutateAsync({
        projectId,
        itemId,
        data: input,
      });
      refetch();
      return result
        ? {
            id: result.id,
            code: result.code,
            name: result.name,
            level: result.level ?? 0,
            completion: result.completion ?? 0,
            plannedStart: result.start_date ?? undefined,
            plannedEnd: result.end_date ?? undefined,
            children: [],
          }
        : null;
    },
    [projectId, updateMutation, refetch],
  );

  // Delete item
  const deleteItem = useCallback(
    async (itemId: string, cascade = false): Promise<boolean> => {
      await deleteMutation.mutateAsync({
        projectId,
        itemId,
        params: { cascade },
      });
      refetch();
      if (selectedItem?.id === itemId) {
        setSelectedItem(null);
      }
      return true;
    },
    [projectId, deleteMutation, refetch, selectedItem],
  );

  // Move item (drag-drop)
  const moveItem = useCallback(
    async (itemId: string, newParentId: string | null): Promise<boolean> => {
      const input: MoveWBSItemInput = {
        new_parent_id: newParentId,
      };
      await moveMutation.mutateAsync({ projectId, itemId, data: input });
      refetch();
      return true;
    },
    [projectId, moveMutation, refetch],
  );

  return {
    items,
    isLoading,
    isError,
    error: error as Error | null,
    createItem,
    updateItem,
    deleteItem,
    moveItem,
    selectedItem,
    setSelectedItem,
    expandedItems,
    toggleExpanded,
    expandAll,
    collapseAll,
    refetch,
  };
}
