import { useState, useMemo, useCallback, useEffect } from 'react';
import type { Highlight } from '@/types/highlight';

/**
 * Extracted Entity interface
 * Matches the structure in EvidenceViewer.tsx
 */
interface ExtractedEntity {
  id: string;
  documentId: string;
  type: string;
  text: string;
  originalText: string;
  page: number;
  confidence: number;
  validated: boolean;
  linkedWbs: string[];
  linkedAlerts: string[];
  highlightRects: Array<{
    top: number;
    left: number;
    width: number;
    height: number;
  }>;
}

/**
 * Hook return type
 */
export interface UseHighlightSearchReturn {
  // State
  searchQuery: string;
  matches: Highlight[];
  currentIndex: number;
  isSearchActive: boolean;

  // Actions
  setSearchQuery: (query: string) => void;
  goToNext: () => void;
  goToPrevious: () => void;
  goToMatch: (index: number) => void;
  clearSearch: () => void;

  // Computed
  totalMatches: number;
  currentMatch: Highlight | null;
  matchCounter: string;
}

/**
 * Custom hook for searching and navigating through highlights
 *
 * @param highlights - Array of highlights to search through
 * @param entities - Array of extracted entities (source data)
 * @returns Search state and navigation functions
 *
 * @example
 * ```tsx
 * const {
 *   searchQuery,
 *   setSearchQuery,
 *   matches,
 *   currentMatch,
 *   goToNext,
 *   goToPrevious,
 *   matchCounter,
 * } = useHighlightSearch(highlights, entities);
 * ```
 */
export function useHighlightSearch(
  highlights: Highlight[],
  entities: ExtractedEntity[]
): UseHighlightSearchReturn {
  const [searchQuery, setSearchQuery] = useState('');
  const [currentIndex, setCurrentIndex] = useState(0);

  /**
   * Filter highlights based on search query
   * Searches in: type, text, originalText, and ID
   * Case-insensitive matching
   */
  const matches = useMemo(() => {
    const trimmedQuery = searchQuery.trim();

    if (!trimmedQuery) {
      return [];
    }

    const lowerQuery = trimmedQuery.toLowerCase();

    // Filter entities that match the query
    const matchedEntities = entities.filter((entity) => {
      // Search in entity type
      if (entity.type.toLowerCase().includes(lowerQuery)) {
        return true;
      }

      // Search in extracted text
      if (entity.text.toLowerCase().includes(lowerQuery)) {
        return true;
      }

      // Search in original text (full version)
      if (entity.originalText.toLowerCase().includes(lowerQuery)) {
        return true;
      }

      // Search in entity ID (for technical searches like "ENT-001")
      if (entity.id.toLowerCase().includes(lowerQuery)) {
        return true;
      }

      return false;
    });

    // Convert matched entity IDs to highlight IDs
    // Highlight ID format: "highlight-{entityId}"
    const matchedIds = new Set(
      matchedEntities.map((entity) => `highlight-${entity.id}`)
    );

    // Filter highlights that correspond to matched entities
    const matchedHighlights = highlights.filter((highlight) =>
      matchedIds.has(highlight.id)
    );

    // Sort by page number for logical navigation
    return matchedHighlights.sort((a, b) => a.page - b.page);
  }, [searchQuery, highlights, entities]);

  /**
   * Reset current index when matches change
   * Ensures index is always valid
   */
  useEffect(() => {
    if (matches.length > 0 && currentIndex >= matches.length) {
      setCurrentIndex(0);
    } else if (matches.length === 0) {
      setCurrentIndex(0);
    }
  }, [matches, currentIndex]);

  /**
   * Navigate to the next match
   * Loops back to first match when reaching the end
   */
  const goToNext = useCallback(() => {
    if (matches.length === 0) {
      return;
    }

    setCurrentIndex((prevIndex) => {
      const nextIndex = prevIndex + 1;
      // Loop back to 0 if we've reached the end
      return nextIndex >= matches.length ? 0 : nextIndex;
    });
  }, [matches.length]);

  /**
   * Navigate to the previous match
   * Loops to last match when going before the first
   */
  const goToPrevious = useCallback(() => {
    if (matches.length === 0) {
      return;
    }

    setCurrentIndex((prevIndex) => {
      const previousIndex = prevIndex - 1;
      // Loop to end if we're at the beginning
      return previousIndex < 0 ? matches.length - 1 : previousIndex;
    });
  }, [matches.length]);

  /**
   * Navigate to a specific match by index
   *
   * @param index - Zero-based index of the match to navigate to
   */
  const goToMatch = useCallback(
    (index: number) => {
      if (index >= 0 && index < matches.length) {
        setCurrentIndex(index);
      }
    },
    [matches.length]
  );

  /**
   * Clear the search query and reset state
   */
  const clearSearch = useCallback(() => {
    setSearchQuery('');
    setCurrentIndex(0);
  }, []);

  // Computed values
  const totalMatches = matches.length;
  const currentMatch = matches.length > 0 ? matches[currentIndex] : null;
  const matchCounter =
    totalMatches > 0 ? `${currentIndex + 1}/${totalMatches}` : '0/0';
  const isSearchActive = searchQuery.trim().length > 0;

  return {
    // State
    searchQuery,
    matches,
    currentIndex,
    isSearchActive,

    // Actions
    setSearchQuery,
    goToNext,
    goToPrevious,
    goToMatch,
    clearSearch,

    // Computed
    totalMatches,
    currentMatch,
    matchCounter,
  };
}
