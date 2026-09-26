/**
 * Test Suite ID: TS-FRT-HITL-QUEUE-001
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ReviewPage from './page';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'test-project-id' }),
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
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

vi.mock('@/lib/ui/toast', () => ({
  showToast: (...args: unknown[]) => mockShowToast(...args),
}));

// Import after mocking
import { useListReviewQueueApiV1HitlQueueGet } from '@/lib/api/generated/hitl/hitl';

const mockUseQueue = vi.mocked(useListReviewQueueApiV1HitlQueueGet);

const MOCK_ITEMS = [
  {
    item_id: 'item-1',
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
    );
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

  it('expands item detail on click', async () => {
    setupMock();
    render(<ReviewPage />);
    const expandBtn = screen.getByTestId('expand-item-1');
    await userEvent.click(expandBtn);
    expect(screen.getByTestId('detail-item-1')).toBeInTheDocument();
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
        itemId: 'item-1',
        data: {},
      });
    });
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
        itemId: 'item-1',
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
      );
    });
  });

  it('targets item_id (not row_id) on approve even when a distinct row_id is present -- guards the journey-3-wedge URL contract', async () => {
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
        itemId: 'item-1',
        data: {},
      });
    });
    expect(mockApproveMutate).not.toHaveBeenCalledWith(
      expect.objectContaining({ itemId: 'row-distinct-999' }),
    );
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

  it('renders one card per deduped queue item (no duplicate legacy rows shown)', () => {
    setupMock();
    render(<ReviewPage />);
    // MOCK_ITEMS has 3 distinct item_ids; the backend queue list already
    // dedups legacy duplicates, so the page must render exactly one card
    // per item_id it receives, never more.
    expect(screen.getAllByTestId(/^review-item-/)).toHaveLength(3);
  });
});
