import { beforeEach, describe, expect, it, vi } from 'vitest';

const getMock = vi.fn();
const postMock = vi.fn();

vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: (...args: unknown[]) => getMock(...args),
    post: (...args: unknown[]) => postMock(...args),
  },
}));

import { reextractBudgetSourceRows } from './reextractBudgetSource';

describe('reextractBudgetSourceRows', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
  });

  it('sends the CURRENT revision id and blob hash as the CAS precondition and returns the effective result', async () => {
    getMock.mockResolvedValueOnce({
      data: [
        { revision_id: 'rev-old', is_current: false, blob_hash: 'old-hash' },
        { revision_id: 'rev-current', is_current: true, blob_hash: 'hash-current', status: 'available' },
      ],
    });
    const result = {
      document_id: 'doc-1',
      revision_id: 'rev-current',
      blob_hash: 'hash-current',
      units_before: 3,
      units_after: 4,
      changed: true,
      added_locators: ['Budget!5'],
      removed_locators: [],
    };
    postMock.mockResolvedValueOnce({ data: result });

    await expect(reextractBudgetSourceRows('proj-1', 'doc-1')).resolves.toEqual(result);

    expect(getMock).toHaveBeenCalledWith('/documents/doc-1/revisions');
    expect(postMock).toHaveBeenCalledWith(
      '/projects/proj-1/documents/doc-1/reextract-source-units',
      null,
      { params: { expected_revision_id: 'rev-current', expected_blob_hash: 'hash-current' } },
    );
  });

  it('fails closed without calling the endpoint when the current revision or its hash is unavailable', async () => {
    getMock.mockResolvedValueOnce({ data: [{ revision_id: 'rev-1', is_current: true, blob_hash: null }] });
    await expect(reextractBudgetSourceRows('proj-1', 'doc-1')).rejects.toThrow(/current revision/i);
    getMock.mockResolvedValueOnce({ data: [{ revision_id: 'rev-1', is_current: false, blob_hash: 'h' }] });
    await expect(reextractBudgetSourceRows('proj-1', 'doc-1')).rejects.toThrow(/current revision/i);
    expect(postMock).not.toHaveBeenCalled();
  });
});
