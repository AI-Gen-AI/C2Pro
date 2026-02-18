/**
 * useWbsSearch Hook
 *
 * Custom React hook for searching WBS items by name, code, and description
 * with highlighting, debouncing, and fuzzy matching.
 *
 * Test Suite: TS-UAD-WBS-SEARCH-001
 * Phase: GREEN
 */

import { useState, useMemo, useCallback, useRef } from "react";

/** WBS Item interface */
export interface WBSItem {
  id: string;
  code: string;
  name: string;
  description?: string;
}

/** Highlight information for matched text */
export interface Highlight {
  field: "name" | "code" | "description";
  text: string;
  matchIndices: [number, number][];
}

/** Search result with item and highlights */
export interface SearchResult {
  item: WBSItem;
  highlights: Highlight[];
}

/** Return type for useWbsSearch hook */
export interface UseWbsSearchReturn {
  /** Current search query */
  query: string;
  /** Set a new search query */
  setQuery: (query: string) => void;
  /** Search results with highlights */
  results: SearchResult[];
  /** Whether search is in progress (debouncing) */
  isSearching: boolean;
  /** Whether search returned no results */
  noResults: boolean;
}

/** Configuration */
const CONFIG = {
  DEBOUNCE_MS: 300,
  FUZZY_TOLERANCE: 2,
};

/**
 * Calculate Levenshtein distance between two strings
 */
function levenshteinDistance(a: string, b: string): number {
  const matrix: number[][] = [];

  for (let i = 0; i <= b.length; i++) {
    matrix[i] = [i];
  }

  for (let j = 0; j <= a.length; j++) {
    matrix[0][j] = j;
  }

  for (let i = 1; i <= b.length; i++) {
    for (let j = 1; j <= a.length; j++) {
      if (b.charAt(i - 1) === a.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1,
          matrix[i][j - 1] + 1,
          matrix[i - 1][j] + 1,
        );
      }
    }
  }

  return matrix[b.length][a.length];
}

/**
 * Check if two strings match with fuzzy tolerance for typos
 */
function fuzzyMatch(query: string, text: string): boolean {
  const normalizedQuery = query.toLowerCase();
  const normalizedText = text.toLowerCase();

  // Exact match
  if (normalizedText.includes(normalizedQuery)) {
    return true;
  }

  // Check each word in the text against the query
  const words = normalizedText.split(/\s+/);
  for (const word of words) {
    // Allow words that start with the query
    if (word.startsWith(normalizedQuery)) {
      return true;
    }

    // Check Levenshtein distance for fuzzy matching
    const lengthDiff = Math.abs(word.length - normalizedQuery.length);
    if (lengthDiff <= CONFIG.FUZZY_TOLERANCE) {
      const distance = levenshteinDistance(normalizedQuery, word);
      if (distance <= CONFIG.FUZZY_TOLERANCE) {
        return true;
      }
    }
  }

  return false;
}

/**
 * Find all match indices for a query in text
 */
function findMatchIndices(query: string, text: string): [number, number][] {
  const indices: [number, number][] = [];
  const normalizedQuery = query.toLowerCase();
  const normalizedText = text.toLowerCase();

  // Find exact substring matches
  let startIndex = 0;
  let index = normalizedText.indexOf(normalizedQuery, startIndex);

  while (index !== -1) {
    indices.push([index, index + query.length - 1]);
    startIndex = index + 1;
    index = normalizedText.indexOf(normalizedQuery, startIndex);
  }

  // If no exact match, try fuzzy matching for word boundaries
  if (indices.length === 0) {
    const words = normalizedText.split(/\s+/);
    let charIndex = 0;

    for (const word of words) {
      const lengthDiff = Math.abs(word.length - normalizedQuery.length);
      if (lengthDiff <= CONFIG.FUZZY_TOLERANCE) {
        const distance = levenshteinDistance(normalizedQuery, word);
        if (distance <= CONFIG.FUZZY_TOLERANCE) {
          const wordIndex = normalizedText.indexOf(word, charIndex);
          if (wordIndex !== -1) {
            indices.push([wordIndex, wordIndex + word.length - 1]);
          }
        }
      }
      charIndex += word.length + 1;
    }
  }

  return indices;
}

/**
 * Search items and return results with highlights
 */
function searchItems(items: WBSItem[], query: string): SearchResult[] {
  if (!query.trim()) {
    return [];
  }

  const results: SearchResult[] = [];

  for (const item of items) {
    const highlights: Highlight[] = [];

    // Check name
    if (fuzzyMatch(query, item.name)) {
      const indices = findMatchIndices(query, item.name);
      if (indices.length > 0) {
        highlights.push({
          field: "name",
          text: item.name,
          matchIndices: indices,
        });
      }
    }

    // Check code
    if (fuzzyMatch(query, item.code)) {
      const indices = findMatchIndices(query, item.code);
      if (indices.length > 0) {
        highlights.push({
          field: "code",
          text: item.code,
          matchIndices: indices,
        });
      }
    }

    // Check description
    if (item.description && fuzzyMatch(query, item.description)) {
      const indices = findMatchIndices(query, item.description);
      if (indices.length > 0) {
        highlights.push({
          field: "description",
          text: item.description,
          matchIndices: indices,
        });
      }
    }

    if (highlights.length > 0) {
      results.push({ item, highlights });
    }
  }

  return results;
}

/**
 * Hook for searching WBS items with highlighting and fuzzy matching
 */
export function useWbsSearch(items: WBSItem[]): UseWbsSearchReturn {
  const [query, setQueryState] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);

  // Use ref to store timeout ID (won't trigger re-renders)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Calculate results
  const results = useMemo(() => {
    if (!debouncedQuery) return [];
    return searchItems(items, debouncedQuery);
  }, [items, debouncedQuery]);

  const noResults = useMemo(() => {
    return debouncedQuery.length > 0 && results.length === 0;
  }, [debouncedQuery, results]);

  // Set query with debouncing
  const setQuery = useCallback((newQuery: string) => {
    // Update query state immediately
    setQueryState(newQuery);

    // Clear existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    // If empty, clear results immediately
    if (!newQuery.trim()) {
      setDebouncedQuery("");
      setIsSearching(false);
      return;
    }

    // Set searching state
    setIsSearching(true);

    // Set new timeout
    timeoutRef.current = setTimeout(() => {
      setDebouncedQuery(newQuery);
      setIsSearching(false);
    }, CONFIG.DEBOUNCE_MS);
  }, []);

  return {
    query,
    setQuery,
    results,
    isSearching,
    noResults,
  };
}
