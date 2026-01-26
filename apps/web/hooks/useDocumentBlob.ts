/**
 * useDocumentBlob Hook
 * Fetches a PDF document blob and exposes an object URL
 */

import { useEffect, useState } from 'react';
import axios from 'axios';
import { apiClient } from '@/lib/api/client';

interface UseDocumentBlobResult {
  blobUrl: string | null;
  loading: boolean;
  error: Error | null;
}

export function useDocumentBlob(documentId: string | null): UseDocumentBlobResult {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    let objectUrl: string | null = null;

    const revokeObjectUrl = () => {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
        objectUrl = null;
      }
    };

    const updateUrl = (nextUrl: string | null) => {
      revokeObjectUrl();
      if (nextUrl && nextUrl.startsWith('blob:')) {
        objectUrl = nextUrl;
      }
      setBlobUrl(nextUrl);
    };

    const fetchBlob = async () => {
      if (!documentId) {
        updateUrl(null);
        setError(null);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const response = await apiClient.get<Blob>(
          `/documents/${documentId}/download`,
          {
            responseType: 'blob',
            signal: controller.signal,
          }
        );

        if (!active) return;

        const contentType = response.headers['content-type'] || '';
        if (contentType.includes('application/json')) {
          const text = await response.data.text();
          const payload = JSON.parse(text) as { url?: string };
          if (payload.url) {
            updateUrl(payload.url);
          } else {
            throw new Error('Respuesta de documento no valida.');
          }
        } else {
          const url = URL.createObjectURL(response.data);
          updateUrl(url);
        }
      } catch (err) {
        if (!active) return;
        if (axios.isCancel(err)) return;
        setError(err instanceof Error ? err : new Error('Error cargando el documento'));
        updateUrl(null);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    fetchBlob();

    return () => {
      active = false;
      controller.abort();
      revokeObjectUrl();
    };
  }, [documentId]);

  return { blobUrl, loading, error };
}
