import { apiClient } from '@/lib/api/client';

/** Effective outcome returned by POST .../reextract-source-units. */
export interface BudgetReextractionResult {
  document_id: string;
  revision_id: string;
  blob_hash: string;
  units_before: number;
  units_after: number;
  changed: boolean;
  added_locators: string[];
  removed_locators: string[];
  summary?: { state?: string; units?: number; reason?: string };
}

interface RevisionStatus {
  status?: string;
  revision_id: string;
  is_current?: boolean;
  blob_hash?: string | null;
}

/**
 * Re-derives the original XLSX rows of the CURRENT revision of an already analysed budget.
 *
 * The revision id and its immutable blob hash are read from the revision lineage and sent as a
 * compare-and-set precondition, so the backend refuses if the current revision changed. Auth comes
 * from the shared `apiClient` (existing Clerk session interceptor); no token is read or logged here.
 */
export async function reextractBudgetSourceRows(
  projectId: string,
  documentId: string,
): Promise<BudgetReextractionResult> {
  const revisions = await apiClient.get<RevisionStatus[]>(`/documents/${documentId}/revisions`);
  const current = revisions.data.find((revision) => revision.is_current);
  if (!current || current.status === 'unavailable' || !current.blob_hash) {
    throw new Error('The current revision of this document is unavailable.');
  }
  const response = await apiClient.post<BudgetReextractionResult>(
    `/projects/${projectId}/documents/${documentId}/reextract-source-units`,
    null,
    {
      params: {
        expected_revision_id: current.revision_id,
        expected_blob_hash: current.blob_hash,
      },
    },
  );
  return response.data;
}
