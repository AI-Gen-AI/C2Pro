/**
 * Test Suite ID: TS-FRT-HITL-QUEUE-001
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ReviewPage from './page';

// Mock next/navigation
const { mockSearchParams } = vi.hoisted(() => ({
  mockSearchParams: vi.fn(() => new URLSearchParams()),
}));
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'test-project-id' }),
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
  useSearchParams: () => mockSearchParams(),
}));

const { mockInvalidateQueries } = vi.hoisted(() => ({ mockInvalidateQueries: vi.fn() }));
vi.mock('@tanstack/react-query', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@tanstack/react-query')>()),
  useQueryClient: () => ({ invalidateQueries: mockInvalidateQueries }),
}));

vi.mock('@clerk/nextjs', () => ({
  useUser: () => ({
    isLoaded: true,
    user: {
      id: 'user_123',
      primaryEmailAddress: { emailAddress: 'jane@acme.com' },
    },
  }),
}));

// Mock hooks
const mockRefetch = vi.fn();
const mockApproveMutate = vi.fn();
const mockRejectMutate = vi.fn();
const mockShowToast = vi.fn();

vi.mock('@/components/features/review/ReviewFindingsPanel', () => ({
  ReviewFindingsPanel: ({ reviewRowId }: { reviewRowId: string }) => (
    <div data-testid={`findings-panel-${reviewRowId}`} />
  ),
}));

// S5-02: the advisory capabilities of the review's project (undefined = not loaded / unavailable: nothing is hidden).
const { mockCapabilities } = vi.hoisted(() => ({
  mockCapabilities: vi.fn<() => { approve_candidate: boolean } | undefined>(() => undefined),
}));
vi.mock('@/components/features/review/useReviewCapabilities', () => ({
  useReviewCapabilities: () => mockCapabilities(),
}));

vi.mock('@/hooks/useProject', () => ({
  useProject: () => ({
    data: { name: 'Test Project' },
    isLoading: false,
  }),
}));

vi.mock('@/lib/api/generated/hitl/hitl', () => ({
  useListReviewQueueApiV1HitlQueueGet: vi.fn(),
  useApproveItemApiV1HitlQueueItemIdApprovePost: () => ({
    mutateAsync: mockApproveMutate,
    isPending: false,
  }),
  useRejectItemApiV1HitlQueueItemIdRejectPost: () => ({
    mutateAsync: mockRejectMutate,
    isPending: false,
  }),
}));

const mockStructuredDecide = vi.fn();
vi.mock('@/lib/api/generated/structured-source-trust/structured-source-trust', () => ({
  useDecideStructuredSourceTrustApiV1StructuredSourceTrustDecisionsPost: () => ({
    mutateAsync: mockStructuredDecide,
    isPending: false,
  }),
}));

vi.mock('@/lib/ui/toast', () => ({
  showToast: (...args: unknown[]) => mockShowToast(...args),
}));

// Import after mocking
import { useListReviewQueueApiV1HitlQueueGet } from '@/lib/api/generated/hitl/hitl';

const mockUseQueue = vi.mocked(useListReviewQueueApiV1HitlQueueGet);

const MOCK_ITEMS = [
  {
    item_id: 'item-1',
    row_id: 'row-1',
    item_type: 'alert',
    current_status: 'PENDING_REVIEW_REQUIRED',
    confidence: 0.85,
    impact_level: 'HIGH',
    approved_by: null,
    approved_at: null,
    sla_due_date: '2026-12-31T00:00:00Z',
    created_at: '2026-04-09T10:00:00Z',
    item_data: { message: 'Budget discrepancy detected' },
  },
  {
    item_id: 'item-2',
    row_id: 'row-2',
    item_type: 'finding',
    current_status: 'APPROVED',
    confidence: 0.92,
    impact_level: 'MEDIUM',
    approved_by: 'reviewer-1',
    approved_at: '2026-04-09T12:00:00Z',
    sla_due_date: '2026-12-31T00:00:00Z',
    created_at: '2026-04-08T10:00:00Z',
    item_data: null,
  },
  {
    item_id: 'item-3',
    row_id: 'row-3',
    item_type: 'alert',
    current_status: 'REJECTED',
    confidence: 0.45,
    impact_level: 'LOW',
    approved_by: 'reviewer-2',
    approved_at: '2026-04-09T14:00:00Z',
    sla_due_date: '2026-12-31T00:00:00Z',
    created_at: '2026-04-07T10:00:00Z',
    item_data: null,
  },
];

function setupMock(overrides: Record<string, unknown> = {}) {
  mockUseQueue.mockReturnValue({
    data: { items: MOCK_ITEMS, total: 3 },
    isLoading: false,
    error: null,
    refetch: mockRefetch,
    ...overrides,
  } as unknown as ReturnType<typeof useListReviewQueueApiV1HitlQueueGet>);
}

describe('ReviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams.mockReturnValue(new URLSearchParams());
    mockCapabilities.mockReturnValue(undefined);
  });

  it('labels the queue as project-scoped because the API now supports project filtering', () => {
    setupMock();
    render(<ReviewPage />);

    expect(screen.getByRole('heading', { name: /review queue/i })).toBeInTheDocument();
    expect(screen.getByText(/Human-in-the-loop review for Test Project/i)).toBeInTheDocument();
  });

  it('passes project_id to the queue hook', () => {
    setupMock();
    render(<ReviewPage />);

    expect(mockUseQueue).toHaveBeenCalledWith(
      expect.objectContaining({ project_id: 'test-project-id' }),
      expect.anything(),
    );
  });

  it('always revalidates the queue on open, so a new revision review is never hidden by a cached queue', () => {
    setupMock();
    render(<ReviewPage />);

    expect(mockUseQueue).toHaveBeenCalledWith(expect.anything(), {
      query: { refetchOnMount: 'always' },
    });
  });

  it('highlights and scrolls to the exact item linked from the Documents page (#712)', () => {
    mockSearchParams.mockReturnValue(new URLSearchParams('itemId=item-1'));
    const scrollIntoViewMock = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoViewMock;
    setupMock();

    render(<ReviewPage />);

    const target = document.getElementById('review-item-item-1');
    expect(target).toHaveClass('ring-2');
    expect(scrollIntoViewMock).toHaveBeenCalled();
  });

  it('shows loading state', () => {
    setupMock({ isLoading: true, data: undefined });
    render(<ReviewPage />);
    expect(screen.getByTestId('review-loading')).toBeInTheDocument();
  });

  it('shows error state', () => {
    setupMock({ error: new Error('Network error'), data: undefined });
    render(<ReviewPage />);
    expect(screen.getByTestId('review-error')).toBeInTheDocument();
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('shows empty state when no items', () => {
    setupMock({ data: { items: [], total: 0 } });
    render(<ReviewPage />);
    expect(screen.getByTestId('review-empty')).toBeInTheDocument();
  });

  it('renders review queue with items', () => {
    setupMock();
    render(<ReviewPage />);
    expect(screen.getByTestId('review-page')).toBeInTheDocument();
    expect(screen.getByTestId('review-queue')).toBeInTheDocument();
    expect(screen.getByTestId('review-item-item-1')).toBeInTheDocument();
  });

  it('shows correct stat counts', () => {
    setupMock();
    render(<ReviewPage />);
    // 1 pending, 1 approved, 1 rejected
    expect(screen.getByTestId('stat-pending')).toHaveTextContent('1');
    expect(screen.getByTestId('stat-approved')).toHaveTextContent('1');
    expect(screen.getByTestId('stat-rejected')).toHaveTextContent('1');
  });

  it('shows approve/reject buttons for pending items only', () => {
    setupMock();
    render(<ReviewPage />);
    // item-1 is pending - should have approve/reject
    expect(screen.getByTestId('approve-item-1')).toBeInTheDocument();
    expect(screen.getByTestId('reject-item-1')).toBeInTheDocument();
  });

  it('S5-02: without APPROVE_CANDIDATE on the project, Approve and Reject are not offered and say why', () => {
    mockCapabilities.mockReturnValue({ approve_candidate: false });
    setupMock();
    render(<ReviewPage />);
    expect(screen.getByTestId('approve-item-1')).toBeDisabled();
    expect(screen.getByTestId('reject-item-1')).toBeDisabled();
    expect(screen.getByTestId('approve-item-1')).toHaveAttribute(
      'title',
      expect.stringMatching(/do not have permission to approve or reject/i),
    );
  });

  it('S5-02: an unavailable capabilities hint never hides the actions (the server decides)', () => {
    mockCapabilities.mockReturnValue(undefined);
    setupMock();
    render(<ReviewPage />);
    expect(screen.getByTestId('approve-item-1')).toBeEnabled();
  });

  it('S5-02: with APPROVE_CANDIDATE the actions stay available', () => {
    mockCapabilities.mockReturnValue({ approve_candidate: true });
    setupMock();
    render(<ReviewPage />);
    expect(screen.getByTestId('approve-item-1')).toBeEnabled();
  });

  it('expands item detail on click', async () => {
    setupMock();
    render(<ReviewPage />);
    const expandBtn = screen.getByTestId('expand-item-1');
    await userEvent.click(expandBtn);
    expect(screen.getByTestId('detail-item-1')).toBeInTheDocument();
  });

  it('does not present unassessed extraction confidence as a measured percentage in approve dialog', async () => {
    setupMock({ data: {
      items: [{
        ...MOCK_ITEMS[0], confidence: 0.85,
        item_data: { confidence_assessed: false, document_filename: '01_Contrato_EPC.docx' },
      }],
      total: 1,
    } });
    render(<ReviewPage />);
    await userEvent.click(screen.getByTestId('approve-item-1'));
    expect(screen.getByText('Extraction confidence:')).toBeInTheDocument();
    expect(screen.getByText('Not evaluated')).toBeInTheDocument();
    expect(screen.queryByText('85.0%')).not.toBeInTheDocument();
  });

  it('shows legacy sentinel zero as not evaluated, but preserves an assessed zero', async () => {
    setupMock({ data: {
      items: [{
        ...MOCK_ITEMS[0], confidence: 0,
        item_data: { confidence_assessed: true },
      }],
      total: 1,
    } });
    const { unmount } = render(<ReviewPage />);
    await userEvent.click(screen.getByTestId('approve-item-1'));
    expect(screen.getByText('0.0%')).toBeInTheDocument();
    unmount();

    setupMock({ data: {
      items: [{
        ...MOCK_ITEMS[0], confidence: 0,
        item_data: { message: 'Unassessed legacy extraction' },
      }],
      total: 1,
    } });
    render(<ReviewPage />);
    await userEvent.click(screen.getByTestId('approve-item-1'));
    expect(screen.getByText('Not evaluated')).toBeInTheDocument();
    expect(screen.queryByText('0.0%')).not.toBeInTheDocument();
  });

  it('opens approve dialog and calls API', async () => {
    setupMock();
    mockApproveMutate.mockResolvedValue({});
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('approve-item-1'));
    expect(screen.getByText('Approve Review Item')).toBeInTheDocument();

    await userEvent.click(screen.getByText('Confirm Approve'));
    await waitFor(() => {
      // Reviewer identity is server-derived from the authenticated session
      // (EPIC-OPS-DOCFLOW Stream C); the client must never supply it.
      expect(mockApproveMutate).toHaveBeenCalledWith({
        itemId: 'row-1',
        data: {},
      });
    });
  });

  it('refreshes the project documents after a decision so the row does not stay "Review required"', async () => {
    setupMock();
    mockApproveMutate.mockResolvedValue({});
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('approve-item-1'));
    await userEvent.click(screen.getByText('Confirm Approve'));

    await waitFor(() => {
      expect(mockInvalidateQueries).toHaveBeenCalledWith({
        queryKey: ['project-documents', 'test-project-id'],
      });
    });
  });

  it('does not refresh the documents when the decision failed', async () => {
    setupMock();
    mockApproveMutate.mockRejectedValue(new Error('boom'));
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('approve-item-1'));
    await userEvent.click(screen.getByText('Confirm Approve'));

    await waitFor(() => expect(mockShowToast).toHaveBeenCalled());
    expect(mockInvalidateQueries).not.toHaveBeenCalled();
  });

  it('keeps approve dialog open and surfaces mutation errors', async () => {
    setupMock();
    mockApproveMutate.mockRejectedValue(new Error('Approval failed'));
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('approve-item-1'));
    await userEvent.click(screen.getByText('Confirm Approve'));

    expect(await screen.findByRole('alert')).toHaveTextContent('Approval failed');
    expect(screen.getByText('Approve Review Item')).toBeInTheDocument();
    expect(mockShowToast).toHaveBeenCalledWith('Approval failed');
  });

  // P0b #1090: the generated Axios client reports a generic HTTP 400 in
  // error.message; the actionable checkpoint status is in response.data.detail.
  it('shows the checkpoint-not-ready detail and permits an explicit retry that succeeds', async () => {
    setupMock();
    const transient = Object.assign(new Error('Request failed with status code 400'), {
      response: { status: 400, data: { detail: 'Candidate not ready: checkpoint pending' } },
    });
    mockApproveMutate.mockRejectedValueOnce(transient).mockResolvedValueOnce({});
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('approve-item-1'));
    await userEvent.click(screen.getByRole('button', { name: /confirm approve/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Candidate not ready: checkpoint pending');
    expect(mockShowToast).toHaveBeenCalledWith('Candidate not ready: checkpoint pending');
    expect(mockApproveMutate).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: /confirm approve/i })).not.toBeDisabled();

    await userEvent.click(screen.getByRole('button', { name: /confirm approve/i }));
    await waitFor(() => expect(mockApproveMutate).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByText('Approve Review Item')).not.toBeInTheDocument());
  });

  it('surfaces an unrelated HTTP 400 detail without auto-retrying or marking approved', async () => {
    setupMock();
    const denied = Object.assign(new Error('Request failed with status code 400'), {
      response: { status: 400, data: { detail: 'Approval denied: tenant mismatch' } },
    });
    mockApproveMutate.mockRejectedValue(denied);
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('approve-item-1'));
    await userEvent.click(screen.getByRole('button', { name: /confirm approve/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Approval denied: tenant mismatch');
    expect(mockShowToast).toHaveBeenCalledWith('Approval denied: tenant mismatch');
    expect(mockApproveMutate).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Approve Review Item')).toBeInTheDocument();
    expect(mockRefetch).not.toHaveBeenCalled();
  });

  it('falls back to the Axios message when response detail is not a nonempty string', async () => {
    setupMock();
    const malformed = Object.assign(new Error('Request failed with status code 400'), {
      response: { status: 400, data: { detail: { code: 'INVALID' } } },
    });
    mockApproveMutate.mockRejectedValue(malformed);
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('approve-item-1'));
    await userEvent.click(screen.getByRole('button', { name: /confirm approve/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Request failed with status code 400');
    expect(mockApproveMutate).toHaveBeenCalledTimes(1);
    expect(mockRefetch).not.toHaveBeenCalled();
  });

  it('opens reject dialog and requires reason', async () => {
    setupMock();
    mockRejectMutate.mockResolvedValue({});
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('reject-item-1'));
    expect(screen.getByText('Reject Review Item')).toBeInTheDocument();

    // Button should be disabled without reason
    const confirmBtn = screen.getByText('Confirm Reject');
    expect(confirmBtn).toBeDisabled();

    // Type reason
    const textarea = screen.getByPlaceholderText(/explain why/i);
    await userEvent.type(textarea, 'Insufficient evidence');

    expect(confirmBtn).not.toBeDisabled();
    await userEvent.click(confirmBtn);

    await waitFor(() => {
      // Reason only — reviewer identity is server-derived, never client-supplied.
      expect(mockRejectMutate).toHaveBeenCalledWith({
        itemId: 'row-1',
        data: {
          reason: 'Insufficient evidence',
        },
      });
    });
  });

  it('shows load more when the current page fills the supported limit', () => {
    const fullPage = Array.from({ length: 50 }, (_, index) => ({
      ...MOCK_ITEMS[0],
      item_id: `item-${index}`,
    }));
    setupMock({ data: { items: fullPage, total: 50 } });
    render(<ReviewPage />);

    expect(screen.getByRole('button', { name: 'Load more' })).toBeInTheDocument();
  });

  it('expands the page limit when load more is clicked', async () => {
    const fullPage = Array.from({ length: 50 }, (_, index) => ({
      ...MOCK_ITEMS[0],
      item_id: `item-${index}`,
    }));
    setupMock({ data: { items: fullPage, total: 50 } });
    render(<ReviewPage />);

    await userEvent.click(screen.getByRole('button', { name: 'Load more' }));

    await waitFor(() => {
      expect(mockUseQueue).toHaveBeenCalledWith(
        expect.objectContaining({ limit: 100 }),
        expect.anything(),
      );
    });
  });

  const STRUCTURED_ITEM = {
    ...MOCK_ITEMS[0],
    item_id: 'doc-budget',
    row_id: 'row-trust-1',
    item_type: 'budget',
    resumable: false,
    trust_kind: 'structured_source',
    candidate_binding: { artifact_id: 'art-1', artifact_version: 2, artifact_hash: 'a'.repeat(64) },
  };

  it('ADR-032: approving a structured-source review decides the exact bound candidate, never the legacy route', async () => {
    setupMock({ data: { items: [STRUCTURED_ITEM], total: 1 } });
    mockStructuredDecide.mockResolvedValue({});
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('approve-doc-budget'));
    await userEvent.click(screen.getByText('Confirm Approve'));

    await waitFor(() => {
      expect(mockStructuredDecide).toHaveBeenCalledWith({
        data: expect.objectContaining({
          review_row_id: 'row-trust-1',
          artifact_id: 'art-1',
          artifact_version: 2,
          artifact_hash: 'a'.repeat(64),
          decision: 'APPROVE',
          idempotency_key: 'ui-approve-row-trust-1',
        }),
      });
    });
    expect(mockApproveMutate).not.toHaveBeenCalled();
  });

  it('ADR-032: rejecting a structured-source review sends the reason through the trust-decision endpoint', async () => {
    setupMock({ data: { items: [STRUCTURED_ITEM], total: 1 } });
    mockStructuredDecide.mockResolvedValue({});
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('reject-doc-budget'));
    await userEvent.type(screen.getByRole('textbox'), 'Wrong file');
    await userEvent.click(screen.getByText('Confirm Reject'));

    await waitFor(() => {
      expect(mockStructuredDecide).toHaveBeenCalledWith({
        data: expect.objectContaining({ decision: 'REJECT', reason: 'Wrong file', artifact_id: 'art-1' }),
      });
    });
    expect(mockRejectMutate).not.toHaveBeenCalled();
  });

  it('ADR-032: a structured review without its exact binding fails closed and calls nothing', async () => {
    setupMock({ data: { items: [{ ...STRUCTURED_ITEM, candidate_binding: null }], total: 1 } });
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('approve-doc-budget'));
    await userEvent.click(screen.getByText('Confirm Approve'));

    await waitFor(() => expect(mockShowToast).toHaveBeenCalled());
    expect(mockStructuredDecide).not.toHaveBeenCalled();
    expect(mockApproveMutate).not.toHaveBeenCalled();
  });

  it('targets the exact row_id rather than reusable item_id on approve', async () => {
    setupMock({
      data: {
        items: [
          { ...MOCK_ITEMS[0], row_id: 'row-distinct-999', resumable: true },
        ],
        total: 1,
      },
    });
    mockApproveMutate.mockResolvedValue({});
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('approve-item-1'));
    await userEvent.click(screen.getByText('Confirm Approve'));

    await waitFor(() => {
      expect(mockApproveMutate).toHaveBeenCalledWith({
        itemId: 'row-distinct-999',
        data: {},
      });
    });
    expect(mockApproveMutate).not.toHaveBeenCalledWith(
      expect.objectContaining({ itemId: 'item-1' }),
    );
  });

  it('fails closed when a pending review lacks exact row identity', () => {
    setupMock({
      data: {
        items: [
          { ...MOCK_ITEMS[0], row_id: null, resumable: true },
        ],
        total: 1,
      },
    });
    render(<ReviewPage />);

    expect(screen.getByTestId('approve-item-1')).toBeDisabled();
    expect(screen.getByTestId('reject-item-1')).toBeDisabled();
    expect(screen.getByTestId('approve-item-1')).toHaveAttribute(
      'title',
      expect.stringMatching(/exact review identity unavailable/i),
    );
    expect(mockApproveMutate).not.toHaveBeenCalled();
    expect(mockRejectMutate).not.toHaveBeenCalled();
  });

  it('describes a resumable item approval as resuming the analysis workflow', async () => {
    setupMock({
      data: {
        items: [{ ...MOCK_ITEMS[0], resumable: true }],
        total: 1,
      },
    });
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('approve-item-1'));
    expect(
      screen.getByText(/this will resume the analysis workflow/i),
    ).toBeInTheDocument();
  });

  it('describes a non-resumable item approval as a plain status change', async () => {
    setupMock({
      data: {
        items: [{ ...MOCK_ITEMS[0], resumable: false }],
        total: 1,
      },
    });
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('approve-item-1'));
    expect(screen.getByText(/this will mark the item as approved/i)).toBeInTheDocument();
  });

  it('describes a resumable item rejection as terminating the workflow', async () => {
    setupMock({
      data: {
        items: [{ ...MOCK_ITEMS[0], resumable: true }],
        total: 1,
      },
    });
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('reject-item-1'));
    expect(
      screen.getByText(/this will terminate the analysis workflow/i),
    ).toBeInTheDocument();
  });

  it('describes a non-resumable item rejection as a plain status change', async () => {
    setupMock({
      data: {
        items: [{ ...MOCK_ITEMS[0], resumable: false }],
        total: 1,
      },
    });
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('reject-item-1'));
    expect(screen.getByText(/this will mark the item as rejected/i)).toBeInTheDocument();
  });

  it('keeps reject dialog open and surfaces the 502 resume-failure message', async () => {
    setupMock();
    mockRejectMutate.mockRejectedValue(new Error('Resume failed: workflow error (502)'));
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('reject-item-1'));
    await userEvent.type(screen.getByPlaceholderText(/explain why/i), 'Bad extraction');
    await userEvent.click(screen.getByText('Confirm Reject'));

    expect(await screen.findByRole('alert')).toHaveTextContent('Resume failed: workflow error (502)');
    expect(screen.getByText('Reject Review Item')).toBeInTheDocument();
    expect(mockShowToast).toHaveBeenCalledWith('Resume failed: workflow error (502)');
  });

  // C2PRO #649: one human decision must produce ONE request. The backend is
  // idempotent on its own (a replay adds no audit event), but the page must
  // not rely on that: a slow resume invites repeated clicks.
  describe('double-submit protection (#649)', () => {
    function deferred<T>() {
      let resolve!: (value: T) => void;
      let reject!: (reason: unknown) => void;
      const promise = new Promise<T>((res, rej) => {
        resolve = res;
        reject = rej;
      });
      return { promise, resolve, reject };
    }

    it('sends exactly one approve request for rapid repeated Confirm clicks while in flight', async () => {
      setupMock();
      const inFlight = deferred<object>();
      mockApproveMutate.mockReturnValue(inFlight.promise);
      render(<ReviewPage />);

      await userEvent.click(screen.getByTestId('approve-item-1'));
      const confirm = screen.getByRole('button', { name: /confirm approve/i });
      fireEvent.click(confirm);
      fireEvent.click(confirm);
      fireEvent.click(confirm);
      await userEvent.click(confirm);

      expect(mockApproveMutate).toHaveBeenCalledTimes(1);
      // Visible, non-actionable pending state; the dialog cannot be dismissed
      // (and re-opened for a second submit) while the decision is in flight.
      expect(confirm).toBeDisabled();
      expect(screen.getByRole('status')).toHaveTextContent(/approving/i);
      expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
      await userEvent.keyboard('{Escape}');
      expect(screen.getByText('Approve Review Item')).toBeInTheDocument();

      await act(async () => {
        inFlight.resolve({});
        await inFlight.promise;
      });
      expect(mockApproveMutate).toHaveBeenCalledTimes(1);
    });

    it('keeps the decided item non-actionable after success, before the queue refresh lands', async () => {
      // refetch() returns but the cached queue still shows item-1 PENDING --
      // exactly the window in which a second Approve used to be possible.
      setupMock();
      mockApproveMutate.mockResolvedValue({});
      render(<ReviewPage />);

      await userEvent.click(screen.getByTestId('approve-item-1'));
      await userEvent.click(screen.getByRole('button', { name: /confirm approve/i }));
      await waitFor(() => expect(screen.queryByText('Approve Review Item')).not.toBeInTheDocument());

      expect(screen.getByTestId('approve-item-1')).toBeDisabled();
      expect(screen.getByTestId('reject-item-1')).toBeDisabled();
      await userEvent.click(screen.getByTestId('approve-item-1'));
      expect(screen.queryByText('Approve Review Item')).not.toBeInTheDocument();
      expect(mockApproveMutate).toHaveBeenCalledTimes(1);
      expect(mockRefetch).toHaveBeenCalled();
    });

    it('restores retry truthfully after a failed approve', async () => {
      setupMock();
      mockApproveMutate
        .mockRejectedValueOnce(new Error('Resuming the analysis workflow failed'))
        .mockResolvedValueOnce({});
      render(<ReviewPage />);

      await userEvent.click(screen.getByTestId('approve-item-1'));
      await userEvent.click(screen.getByRole('button', { name: /confirm approve/i }));
      expect(await screen.findByRole('alert')).toHaveTextContent('Resuming the analysis workflow failed');

      const retry = screen.getByRole('button', { name: /confirm approve/i });
      expect(retry).not.toBeDisabled();
      expect(screen.getByRole('button', { name: /cancel/i })).not.toBeDisabled();
      await userEvent.click(retry);
      await waitFor(() => expect(mockApproveMutate).toHaveBeenCalledTimes(2));
    });

    it('sends exactly one reject request for rapid repeated Confirm clicks while in flight', async () => {
      setupMock();
      const inFlight = deferred<object>();
      mockRejectMutate.mockReturnValue(inFlight.promise);
      render(<ReviewPage />);

      await userEvent.click(screen.getByTestId('reject-item-1'));
      await userEvent.type(screen.getByPlaceholderText(/explain why/i), 'Bad extraction');
      const confirm = screen.getByRole('button', { name: /confirm reject/i });
      fireEvent.click(confirm);
      fireEvent.click(confirm);
      await userEvent.click(confirm);

      expect(mockRejectMutate).toHaveBeenCalledTimes(1);
      expect(confirm).toBeDisabled();
      expect(screen.getByRole('status')).toHaveTextContent(/rejecting/i);

      await act(async () => {
        inFlight.resolve({});
        await inFlight.promise;
      });
      expect(mockRejectMutate).toHaveBeenCalledTimes(1);
    });
  });

  it('S5 — a Documents deep link finds the 75th review without manually paginating', () => {
    const items = Array.from({ length: 75 }, (_, index) => ({
      ...MOCK_ITEMS[0],
      item_id: `item-${index}`,
      row_id: `review-row-${index}`,
    }));
    mockSearchParams.mockReturnValue(new URLSearchParams('itemId=item-74'));
    setupMock({ data: { items, total: items.length } });

    render(<ReviewPage />);
    expect(mockUseQueue).toHaveBeenCalledWith(
      expect.objectContaining({ project_id: 'test-project-id', limit: 200 }),
      expect.anything(),
    );
    expect(document.getElementById('review-item-item-74')).toHaveClass('ring-2');
    expect(screen.queryByTestId('review-target-unavailable')).not.toBeInTheDocument();
  });

  it('S5 — missing linked review explains unavailability without silently selecting another row', () => {
    mockSearchParams.mockReturnValue(new URLSearchParams('itemId=not-in-this-project'));
    setupMock();

    render(<ReviewPage />);
    expect(screen.getByTestId('review-target-unavailable')).toHaveTextContent(
      /no other review was selected/i,
    );
    expect(document.getElementById('review-item-item-1')).not.toHaveClass('ring-2');
  });

  it('S5 — a new review row with the same item_id remounts a fresh decision card', async () => {
    const original = { ...MOCK_ITEMS[0], row_id: 'revision-a-row' };
    setupMock({ data: { items: [original], total: 1 } });
    const { rerender } = render(<ReviewPage />);
    await userEvent.click(screen.getByTestId('expand-item-1'));
    expect(screen.getByTestId('detail-item-1')).toBeInTheDocument();

    // Backend creates a distinct row for a new revision of the same document.
    // It MUST NOT inherit the old card's expanded/internal decision state.
    const next = { ...MOCK_ITEMS[0], row_id: 'revision-b-row' };
    setupMock({ data: { items: [next], total: 1 } });
    rerender(<ReviewPage />);
    expect(screen.queryByTestId('detail-item-1')).not.toBeInTheDocument();
    expect(screen.getByTestId('approve-item-1')).toBeEnabled();

    mockApproveMutate.mockResolvedValue({ current_status: 'APPROVED' });
    await userEvent.click(screen.getByTestId('approve-item-1'));
    await userEvent.click(screen.getByRole('button', { name: /confirm approve/i }));
    await waitFor(() => expect(mockApproveMutate).toHaveBeenCalledWith({
      itemId: 'revision-b-row',
      data: {},
    }));
  });

  it('S5 — approval is acknowledged but only a refreshed saved row confirms it', async () => {
    setupMock();
    mockApproveMutate.mockResolvedValue({ current_status: 'APPROVED' });
    const { rerender } = render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('approve-item-1'));
    await userEvent.click(screen.getByRole('button', { name: /confirm approve/i }));

    const receipt = await screen.findByTestId('review-decision-receipt');
    expect(receipt).toHaveTextContent(/approval was sent, not yet confirmed as saved/i);
    expect(receipt).toHaveTextContent(/do not treat the document as analyzed/i);
    expect(screen.getByTestId('review-receipt-title')).toHaveTextContent(/alert/);
    expect(screen.getByTestId('approve-item-1')).toBeDisabled();
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ['/api/v1/projects/test-project-id/health'],
    });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ['/api/coherence/dashboard/test-project-id'],
    });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ['/api/v1/coherence/dashboard/test-project-id'],
    });

    setupMock({ data: { items: [
      { ...MOCK_ITEMS[0], current_status: 'APPROVED' },
    ], total: 1 } });
    rerender(<ReviewPage />);
    expect(receipt).toHaveTextContent(/approved and saved/i);
    expect(screen.getByTestId('review-receipt-server-status')).toHaveTextContent(/server status.*: approved/i);
    expect(receipt).toHaveTextContent(/document processing and health may still be updating/i);
  });

  it('S5 — a 502 after resume does not invite a blind duplicate decision', async () => {
    setupMock();
    const uncertain = Object.assign(new Error('Request failed with status code 502'), {
      response: { status: 502, data: {
        detail: 'Review approved, but resuming the analysis workflow failed',
      } },
    });
    mockApproveMutate.mockRejectedValueOnce(uncertain);
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('approve-item-1'));
    await userEvent.click(screen.getByRole('button', { name: /confirm approve/i }));
    await waitFor(() => expect(screen.getByTestId('review-decision-receipt')).toHaveTextContent(
      /needs verification/i,
    ));
    expect(screen.getByRole('alert')).toHaveTextContent(/resuming the analysis workflow failed/i);
    expect(screen.getByRole('button', { name: /confirm approve/i })).toBeDisabled();
    expect(mockApproveMutate).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(screen.getByTestId('approve-item-1')).toBeDisabled();
    expect(mockRefetch).toHaveBeenCalled();
  });

  it('S5 — rejection is confirmed only after the persisted queue reports REJECTED', async () => {
    setupMock();
    mockRejectMutate.mockResolvedValue({});
    const { rerender } = render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('reject-item-1'));
    await userEvent.type(screen.getByPlaceholderText(/explain why/i), 'Original contract clause contradicts the summary.');
    await userEvent.click(screen.getByRole('button', { name: /confirm reject/i }));
    const receipt = await screen.findByTestId('review-decision-receipt');
    expect(receipt).toHaveTextContent(/rejection was sent, not yet confirmed as saved/i);

    setupMock({ data: { items: [
      { ...MOCK_ITEMS[0], current_status: 'REJECTED' },
    ], total: 1 } });
    rerender(<ReviewPage />);
    expect(receipt).toHaveTextContent(/rejected and saved/i);
    expect(screen.queryByTestId('approve-item-1')).not.toBeInTheDocument();
  });

  it('P0 — counters describe the whole project queue, not the selected status filter', async () => {
    mockUseQueue.mockImplementation(((params: { status?: string }) => ({
      data: params.status === 'APPROVED'
        ? { items: [MOCK_ITEMS[1]], total: 1 }
        : { items: MOCK_ITEMS, total: 3 },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    })) as unknown as typeof useListReviewQueueApiV1HitlQueueGet);
    render(<ReviewPage />);

    await userEvent.click(screen.getByRole('button', { name: /^approved$/i }));

    // The list is filtered to the single approved row, the counters still read the whole queue.
    expect(screen.getAllByTestId(/^review-item-/)).toHaveLength(1);
    expect(screen.getByTestId('stat-pending')).toHaveTextContent('1');
    expect(screen.getByTestId('stat-approved')).toHaveTextContent('1');
    expect(mockUseQueue).toHaveBeenCalledWith(
      expect.not.objectContaining({ status: expect.anything() }),
      expect.anything(),
    );
  });

  it('P0 — "Refresh review status" shows progress and a comprehensible server answer', async () => {
    setupMock();
    mockApproveMutate.mockResolvedValue({ current_status: 'APPROVED' });
    render(<ReviewPage />);

    await userEvent.click(screen.getByTestId('approve-item-1'));
    await userEvent.click(screen.getByRole('button', { name: /confirm approve/i }));
    await screen.findByTestId('review-decision-receipt');

    await userEvent.click(screen.getByTestId('review-refresh-status'));
    await waitFor(() =>
      expect(screen.getByTestId('review-receipt-server-status')).toHaveTextContent(
        /server status at .*: pending/i,
      ),
    );
    expect(screen.getByTestId('review-decision-receipt')).not.toHaveTextContent(/approved and saved/i);
  });

  it('P0 — says out loud (not only in a tooltip) why the decision buttons are disabled', () => {
    setupMock();
    mockCapabilities.mockReturnValue({ approve_candidate: false });
    render(<ReviewPage />);

    expect(screen.getByTestId('actions-blocked-item-1')).toHaveTextContent(/do not have permission/i);
    expect(screen.getByTestId('approve-item-1')).toBeDisabled();
  });

  it('renders one card per deduped queue item (no duplicate legacy rows shown)', () => {
    setupMock();
    render(<ReviewPage />);
    // MOCK_ITEMS has 3 distinct item_ids; the backend queue list already
    // dedups legacy duplicates, so the page must render exactly one card
    // per item_id it receives, never more.
    expect(screen.getAllByTestId(/^review-item-/)).toHaveLength(3);
  });
});
