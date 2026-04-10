/**
 * useBudget Hook
 *
 * Provides budget state management with CRUD operations.
 *
 * TASK-FRT-165: Budget Dashboard UI
 */

import { useState, useCallback, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios/dist/browser/axios.cjs";

const API_BASE = "/api/v1";

export interface BudgetItem {
  id: string;
  name: string;
  category: string;
  amount: number;
  actualAmount?: number;
  variance?: number;
  description?: string;
  status: string;
}

export interface BudgetSummary {
  total_budget: number;
  spent_amount: number;
  remaining_budget: number;
  utilization_percentage: number;
  variance_status: string;
  currency: string;
  items: BudgetItem[];
}

interface UseBudgetOptions {
  projectId: string;
  enabled?: boolean;
}

interface UseBudgetReturn {
  // Data
  budget: BudgetSummary | null;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;

  // CRUD Actions
  createItem: (item: Partial<BudgetItem>) => Promise<BudgetItem | null>;
  updateItem: (
    itemId: string,
    item: Partial<BudgetItem>,
  ) => Promise<BudgetItem | null>;
  deleteItem: (itemId: string) => Promise<boolean>;

  // State
  selectedItem: BudgetItem | null;
  setSelectedItem: (item: BudgetItem | null) => void;

  // Refresh
  refetch: () => void;
}

export function useBudget({
  projectId,
  enabled = true,
}: UseBudgetOptions): UseBudgetReturn {
  const queryClient = useQueryClient();
  const [selectedItem, setSelectedItem] = useState<BudgetItem | null>(null);

  // Fetch budget
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["budget", projectId],
    queryFn: async () => {
      const response = await axios.get<BudgetSummary>(
        `${API_BASE}/projects/${projectId}/budget`,
      );
      return response.data;
    },
    enabled: !!projectId && enabled,
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: async (item: Partial<BudgetItem>) => {
      const response = await axios.post(
        `${API_BASE}/projects/${projectId}/budget/items`,
        item,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget", projectId] });
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: async ({
      itemId,
      item,
    }: {
      itemId: string;
      item: Partial<BudgetItem>;
    }) => {
      const response = await axios.patch(
        `${API_BASE}/budget/items/${itemId}`,
        item,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget", projectId] });
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async (itemId: string) => {
      await axios.delete(`${API_BASE}/budget/items/${itemId}`);
      return true;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget", projectId] });
    },
  });

  // Create item
  const createItem = useCallback(
    async (item: Partial<BudgetItem>): Promise<BudgetItem | null> => {
      try {
        const result = await createMutation.mutateAsync(item);
        return result;
      } catch (err) {
        console.error("Failed to create budget item:", err);
        return null;
      }
    },
    [createMutation],
  );

  // Update item
  const updateItem = useCallback(
    async (
      itemId: string,
      item: Partial<BudgetItem>,
    ): Promise<BudgetItem | null> => {
      try {
        const result = await updateMutation.mutateAsync({ itemId, item });
        return result;
      } catch (err) {
        console.error("Failed to update budget item:", err);
        return null;
      }
    },
    [updateMutation],
  );

  // Delete item
  const deleteItem = useCallback(
    async (itemId: string): Promise<boolean> => {
      try {
        await deleteMutation.mutateAsync(itemId);
        if (selectedItem?.id === itemId) {
          setSelectedItem(null);
        }
        return true;
      } catch (err) {
        console.error("Failed to delete budget item:", err);
        return false;
      }
    },
    [deleteMutation, selectedItem],
  );

  return {
    budget: data ?? null,
    isLoading,
    isError,
    error: error as Error | null,
    createItem,
    updateItem,
    deleteItem,
    selectedItem,
    setSelectedItem,
    refetch,
  };
}

/**
 * Calculate category breakdown from budget items
 */
export function calculateCategoryBreakdown(items: BudgetItem[]) {
  const categories: Record<string, { planned: number; actual: number }> = {};

  items.forEach((item) => {
    if (!categories[item.category]) {
      categories[item.category] = { planned: 0, actual: 0 };
    }
    categories[item.category].planned += item.amount;
    categories[item.category].actual += item.actualAmount ?? item.amount;
  });

  return Object.entries(categories).map(([name, values]) => ({
    name,
    planned: values.planned,
    actual: values.actual,
    variance: values.planned - values.actual,
  }));
}

/**
 * Calculate variance data for charts
 */
export function calculateVarianceData(items: BudgetItem[]) {
  return items.map((item) => ({
    name: item.name,
    planned: item.amount,
    actual: item.actualAmount ?? item.amount,
    variance: item.variance ?? item.amount - (item.actualAmount ?? item.amount),
  }));
}
