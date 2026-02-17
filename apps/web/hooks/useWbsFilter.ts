/**
 * useWbsFilter Hook
 *
 * Custom React hook for filtering WBS items by completion status.
 * Features:
 * - Filter by status: not-started, in-progress, complete
 * - URL query parameter synchronization
 * - localStorage persistence
 *
 * Test Suite: TS-UAD-WBS-FILTER-001
 * Phase: REFACTOR (Triangulation complete)
 *
 * @example
 * ```typescript
 * const { filter, setFilter, filteredItems, clearFilter } = useWbsFilter(wbsItems);
 *
 * // Filter by status
 * setFilter("in-progress");
 *
 * // Clear filter
 * clearFilter();
 * ```
 */

import { useState, useMemo, useEffect, useCallback, useRef } from "react";

/** Valid filter values for WBS items */
export type WBSFilterType = "not-started" | "in-progress" | "complete";

/** WBS Item interface */
export interface WBSItem {
  id: string;
  code: string;
  name: string;
  completion: number;
}

/** Return type for useWbsFilter hook */
export interface UseWbsFilterReturn {
  /** Current active filter or null if none */
  filter: WBSFilterType | null;
  /** Set a new filter value */
  setFilter: (filter: WBSFilterType) => void;
  /** Filtered items based on current filter */
  filteredItems: WBSItem[];
  /** Clear the current filter */
  clearFilter: () => void;
}

/** Configuration constants */
const CONFIG = {
  STORAGE_KEY: "wbs-filter",
  URL_PARAM: "filter",
  VALID_FILTERS: ["not-started", "in-progress", "complete"] as const,
} as const;

/** Check if running in browser environment */
const isBrowser = (): boolean => typeof window !== "undefined";

/**
 * Validates if a string is a valid filter type
 * @param value - Value to validate
 * @returns True if valid filter type
 */
function isValidFilter(value: string | null): value is WBSFilterType {
  if (!value) return false;
  return CONFIG.VALID_FILTERS.includes(value as WBSFilterType);
}

/**
 * Filters WBS items based on completion status
 * @param items - Array of WBS items to filter
 * @param filter - Filter criteria or null for all items
 * @returns Filtered array of items
 */
function filterItems(
  items: WBSItem[],
  filter: WBSFilterType | null,
): WBSItem[] {
  if (!filter) return items;

  const filterStrategies: Record<WBSFilterType, (item: WBSItem) => boolean> = {
    "not-started": (item) => item.completion === 0,
    "in-progress": (item) => item.completion > 0 && item.completion < 100,
    complete: (item) => item.completion === 100,
  };

  return items.filter(filterStrategies[filter]);
}

/**
 * Gets initial filter from URL or localStorage
 * URL takes precedence over localStorage
 * @returns Valid filter value or null
 */
function getInitialFilter(): WBSFilterType | null {
  if (!isBrowser()) return null;

  try {
    // Check URL first (takes precedence)
    const urlParams = new URLSearchParams(window.location.search);
    const urlFilter = urlParams.get(CONFIG.URL_PARAM);

    if (isValidFilter(urlFilter)) {
      return urlFilter;
    }

    // Fall back to localStorage
    const storedFilter = localStorage.getItem(CONFIG.STORAGE_KEY);

    if (isValidFilter(storedFilter)) {
      return storedFilter;
    }
  } catch (error) {
    // Silently fail in SSR or if storage is unavailable
    console.warn("Failed to get initial filter:", error);
  }

  return null;
}

/**
 * Updates URL query parameter without page reload
 * @param filter - Filter value to set or null to remove
 */
function updateUrlParam(filter: WBSFilterType | null): void {
  if (!isBrowser()) return;

  try {
    const url = new URL(window.location.href);

    if (filter) {
      url.searchParams.set(CONFIG.URL_PARAM, filter);
    } else {
      url.searchParams.delete(CONFIG.URL_PARAM);
    }

    window.history.replaceState({}, "", url.toString());
  } catch (error) {
    console.warn("Failed to update URL:", error);
  }
}

/**
 * Persists filter to localStorage
 * @param filter - Filter value to persist or null to remove
 */
function persistToStorage(filter: WBSFilterType | null): void {
  if (!isBrowser()) return;

  try {
    if (filter) {
      localStorage.setItem(CONFIG.STORAGE_KEY, filter);
    } else {
      localStorage.removeItem(CONFIG.STORAGE_KEY);
    }
  } catch (error) {
    // Handle private browsing mode or storage quota exceeded
    console.warn("Failed to persist filter:", error);
  }
}

/**
 * Hook for filtering WBS items by completion status
 *
 * @param items - Array of WBS items to filter
 * @returns Filter state and operations
 */
export function useWbsFilter(items: WBSItem[]): UseWbsFilterReturn {
  // Initialize filter from URL or localStorage
  const [filter, setFilterState] = useState<WBSFilterType | null>(
    getInitialFilter,
  );

  // Ref to track if this is the first render
  const isFirstRender = useRef(true);

  // Memoized filtered items
  const filteredItems = useMemo(
    () => filterItems(items, filter),
    [items, filter],
  );

  // Set filter with side effects (URL and localStorage)
  const setFilter = useCallback((newFilter: WBSFilterType) => {
    if (!isValidFilter(newFilter)) {
      console.warn(`Invalid filter value: ${newFilter}`);
      return;
    }

    setFilterState(newFilter);
    updateUrlParam(newFilter);
    persistToStorage(newFilter);
  }, []);

  // Clear filter
  const clearFilter = useCallback(() => {
    setFilterState(null);
    updateUrlParam(null);
    persistToStorage(null);
  }, []);

  // Sync with URL on mount and browser navigation
  useEffect(() => {
    // Skip on first render since we already initialized in useState
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }

    const handlePopState = () => {
      const urlParams = new URLSearchParams(window.location.search);
      const urlFilter = urlParams.get(CONFIG.URL_PARAM);

      if (isValidFilter(urlFilter)) {
        setFilterState(urlFilter);
      } else if (urlFilter === null) {
        setFilterState(null);
      }
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  return {
    filter,
    setFilter,
    filteredItems,
    clearFilter,
  };
}
