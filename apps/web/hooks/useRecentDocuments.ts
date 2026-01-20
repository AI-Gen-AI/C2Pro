/**
 * Hook for tracking and managing recently accessed documents
 * Stores last 5 documents in localStorage
 */

import { useState, useEffect, useCallback } from 'react';
import type { DocumentInfo } from '@/types/document';

const STORAGE_KEY = 'c2pro_recent_documents';
const MAX_RECENT_DOCUMENTS = 5;

interface RecentDocument {
  id: string;
  name: string;
  type: string;
  extension: string;
  accessedAt: string; // ISO timestamp
  totalPages?: number;
  fileSize?: number;
}

export function useRecentDocuments() {
  const [recentDocuments, setRecentDocuments] = useState<RecentDocument[]>([]);

  // Load recent documents from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        setRecentDocuments(parsed);
      } catch (error) {
        console.error('Failed to parse recent documents:', error);
        localStorage.removeItem(STORAGE_KEY);
      }
    }
  }, []);

  // Add a document to recent list
  const addRecentDocument = useCallback((document: DocumentInfo) => {
    setRecentDocuments((prev) => {
      // Remove if already exists (to move to top)
      const filtered = prev.filter((doc) => doc.id !== document.id);

      // Create new recent document entry
      const newRecent: RecentDocument = {
        id: document.id,
        name: document.name,
        type: document.type,
        extension: document.extension,
        accessedAt: new Date().toISOString(),
        totalPages: document.totalPages,
        fileSize: document.fileSize,
      };

      // Add to beginning and limit to MAX_RECENT_DOCUMENTS
      const updated = [newRecent, ...filtered].slice(0, MAX_RECENT_DOCUMENTS);

      // Persist to localStorage
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      } catch (error) {
        console.error('Failed to save recent documents:', error);
      }

      return updated;
    });
  }, []);

  // Clear all recent documents
  const clearRecentDocuments = useCallback(() => {
    setRecentDocuments([]);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  // Remove a specific document from recent list
  const removeRecentDocument = useCallback((documentId: string) => {
    setRecentDocuments((prev) => {
      const updated = prev.filter((doc) => doc.id !== documentId);

      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      } catch (error) {
        console.error('Failed to save recent documents:', error);
      }

      return updated;
    });
  }, []);

  return {
    recentDocuments,
    addRecentDocument,
    clearRecentDocuments,
    removeRecentDocument,
  };
}
