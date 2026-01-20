/**
 * useViewerPersistence Hook
 * Persists Evidence Viewer state to localStorage
 * Preserves document selection, page, zoom, and rotation across sessions
 */

import { useState, useEffect, useCallback } from 'react';
import type { DocumentStateMap } from '@/types/document';

const STORAGE_KEY = 'c2pro_viewer_state';

interface ViewerState {
  currentDocumentId: string;
  documentStates: DocumentStateMap;
  lastUpdated: string;
}

interface ViewerPersistenceOptions {
  defaultDocumentId?: string;
  defaultDocumentStates?: DocumentStateMap;
}

/**
 * Custom hook for persisting viewer state to localStorage
 */
export function useViewerPersistence(options: ViewerPersistenceOptions = {}) {
  const {
    defaultDocumentId = 'contract',
    defaultDocumentStates = {
      contract: { currentPage: 1, scale: 1.0, rotation: 0 },
      schedule: { currentPage: 1, scale: 1.0, rotation: 0 },
      bom: { currentPage: 1, scale: 1.0, rotation: 0 },
      specification: { currentPage: 1, scale: 1.0, rotation: 0 },
    },
  } = options;

  // Load initial state from localStorage or use defaults
  const loadState = useCallback((): ViewerState => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as ViewerState;

        // Validate structure
        if (
          parsed.currentDocumentId &&
          parsed.documentStates &&
          typeof parsed.documentStates === 'object'
        ) {
          return parsed;
        }
      }
    } catch (error) {
      console.error('Failed to load viewer state from localStorage:', error);
    }

    // Return defaults if no valid state found
    return {
      currentDocumentId: defaultDocumentId,
      documentStates: defaultDocumentStates,
      lastUpdated: new Date().toISOString(),
    };
  }, [defaultDocumentId, defaultDocumentStates]);

  // Initialize state from localStorage
  const [currentDocumentId, setCurrentDocumentId] = useState<string>(
    () => loadState().currentDocumentId
  );
  const [documentStates, setDocumentStates] = useState<DocumentStateMap>(
    () => loadState().documentStates
  );

  // Save state to localStorage whenever it changes
  useEffect(() => {
    try {
      const state: ViewerState = {
        currentDocumentId,
        documentStates,
        lastUpdated: new Date().toISOString(),
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (error) {
      console.error('Failed to save viewer state to localStorage:', error);
    }
  }, [currentDocumentId, documentStates]);

  /**
   * Update the current document and optionally persist its state
   */
  const updateCurrentDocument = useCallback((documentId: string) => {
    setCurrentDocumentId(documentId);
  }, []);

  /**
   * Update state for a specific document
   */
  const updateDocumentState = useCallback(
    (
      documentId: string,
      updates: Partial<{ currentPage: number; scale: number; rotation: number }>
    ) => {
      setDocumentStates((prev) => ({
        ...prev,
        [documentId]: {
          ...prev[documentId],
          ...updates,
        },
      }));
    },
    []
  );

  /**
   * Update state for the current document
   */
  const updateCurrentState = useCallback(
    (updates: Partial<{ currentPage: number; scale: number; rotation: number }>) => {
      setDocumentStates((prev) => ({
        ...prev,
        [currentDocumentId]: {
          ...prev[currentDocumentId],
          ...updates,
        },
      }));
    },
    [currentDocumentId]
  );

  /**
   * Reset all viewer state to defaults
   */
  const resetViewerState = useCallback(() => {
    setCurrentDocumentId(defaultDocumentId);
    setDocumentStates(defaultDocumentStates);

    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      console.error('Failed to clear viewer state from localStorage:', error);
    }
  }, [defaultDocumentId, defaultDocumentStates]);

  /**
   * Get state for a specific document
   */
  const getDocumentState = useCallback(
    (documentId: string) => {
      return (
        documentStates[documentId] || {
          currentPage: 1,
          scale: 1.0,
          rotation: 0,
        }
      );
    },
    [documentStates]
  );

  return {
    // Current state
    currentDocumentId,
    documentStates,

    // Update functions
    updateCurrentDocument,
    updateDocumentState,
    updateCurrentState,

    // Utility functions
    getDocumentState,
    resetViewerState,
  };
}
