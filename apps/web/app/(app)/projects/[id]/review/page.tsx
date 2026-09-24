'use client';

import { useMemo, useRef, useState } from 'react';
import { useUser } from '@clerk/nextjs';
import { useParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { severityToToken } from '@/lib/ui/severity-tokens';
import { Button } from '@/components/ui/button';
import { ReviewItemCard } from '@/components/features/review/ReviewItemCard';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useProject } from '@/hooks/useProject';
import { showToast } from '@/lib/ui/toast';
import {
  useListReviewQueueApiV1HitlQueueGet,
  useApproveItemApiV1HitlQueueItemIdApprovePost,
  useRejectItemApiV1HitlQueueItemIdRejectPost,
} from '@/lib/api/generated/hitl/hitl';
import type { ReviewItemResponse } from '@/lib/api/generated/models';
import { ReviewStatus } from '@/lib/api/generated/models/reviewStatus';

const PAGE_LIMIT_STEP = 50;
const MAX_PAGE_LIMIT = 200;

type ModalState =
  | { kind: 'none' }
  | { kind: 'approve'; item: ReviewItemResponse }
  | { kind: 'reject'; item: ReviewItemResponse };

function statusLabel(status: string): string {
  switch (status) {
    case ReviewStatus.DRAFT:
      return 'Draft';
    case ReviewStatus.PENDING_REVIEW_REQUIRED:
      return 'Pending Review';
    case ReviewStatus.PENDING_REVIEW_CONDITIONAL:
      return 'Conditional Review';
    case ReviewStatus.APPROVED:
      return 'Approved';
    case ReviewStatus.REJECTED:
      return 'Rejected';
    case ReviewStatus.ESCALATED:
      return 'Escalated';
    case ReviewStatus.CLOSED:
      return 'Closed';
    default:
      return status;
  }
}

function impactColor(impact: string): string {
  return severityToToken(impact);
}

// The exact row a decision was submitted for. row_id when the API provides
// it, so a later re-review of the same item_id (a new row) stays actionable.
function decisionKey(item: ReviewItemResponse): string {
  return item.row_id ?? item.item_id;
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message.trim().length > 0
    ? error.message
    : fallback;
}

export default function ReviewPage() {
  const params = useParams();
  const projectId = params.id as string;
  const { isLoaded: isUserLoaded, user } = useUser();
  const reviewerName = user?.primaryEmailAddress?.emailAddress ?? user?.id;
  const reviewerIdentityReady = isUserLoaded && Boolean(reviewerName);
  const { data: project } = useProject(projectId);
  const projectName = project?.name?.trim();

  const approveMutation = useApproveItemApiV1HitlQueueItemIdApprovePost();
  const rejectMutation = useRejectItemApiV1HitlQueueItemIdRejectPost();

  const [modal, setModal] = useState<ModalState>({ kind: 'none' });
  const [rejectReason, setRejectReason] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [pageLimit, setPageLimit] = useState(PAGE_LIMIT_STEP);
  const [actionError, setActionError] = useState<string | null>(null);
  // C2PRO #649: one human decision -> one request. The ref closes the gap
  // before React re-renders the disabled state (rapid clicks land in the
  // same frame); `submitting` drives what the reviewer sees. The backend is
  // independently idempotent -- this is not a substitute for it.
  const inFlightRef = useRef(false);
  const [submitting, setSubmitting] = useState<'approve' | 'reject' | null>(null);
  // Rows decided in this session stay non-actionable until the refreshed
  // queue shows their new status, so a stale PENDING card cannot be
  // approved a second time.
  const [decidedKeys, setDecidedKeys] = useState<ReadonlySet<string>>(() => new Set());

  const queueParams = useMemo(
    () => ({
      skip: 0,
      limit: pageLimit,
      project_id: projectId,
      ...(statusFilter === 'all' ? {} : { status: statusFilter as ReviewStatus }),
    }),
    [projectId, pageLimit, statusFilter],
  );

  const { data: queueData, isLoading, error, refetch } =
    useListReviewQueueApiV1HitlQueueGet(queueParams);

  const items = useMemo(() => queueData?.items ?? [], [queueData]);
  const canLoadMore = items.length === pageLimit && pageLimit < MAX_PAGE_LIMIT;

  const pendingCount = items.filter(
    (i) =>
      i.current_status === ReviewStatus.PENDING_REVIEW_REQUIRED ||
      i.current_status === ReviewStatus.PENDING_REVIEW_CONDITIONAL,
  ).length;
  const approvedCount = items.filter(
    (i) => i.current_status === ReviewStatus.APPROVED,
  ).length;
  const rejectedCount = items.filter(
    (i) => i.current_status === ReviewStatus.REJECTED,
  ).length;
  const escalatedCount = items.filter(
    (i) => i.current_status === ReviewStatus.ESCALATED,
  ).length;

  const closeModal = () => {
    setModal({ kind: 'none' });
    setRejectReason('');
    setActionError(null);
  };

  const dismissModal = () => {
    if (inFlightRef.current) return;
    closeModal();
  };

  const beginSubmit = (kind: 'approve' | 'reject'): boolean => {
    if (inFlightRef.current) return false;
    inFlightRef.current = true;
    setSubmitting(kind);
    setActionError(null);
    return true;
  };

  const endSubmit = () => {
    inFlightRef.current = false;
    setSubmitting(null);
  };

  const markDecided = (item: ReviewItemResponse) => {
    setDecidedKeys((current) => new Set(current).add(decisionKey(item)));
  };

  const handleApprove = async () => {
    if (modal.kind !== 'approve' || !reviewerName) return;
    if (!beginSubmit('approve')) return;
    try {
      await approveMutation.mutateAsync({
        // The queue list already collapses legacy item_id duplicates to one
        // canonical (resumable, most-recent) row -- see
        // SqlAlchemyReviewQueueRepository.list_by_status -- so the card the
        // user is looking at and the row item_id resolves to on the backend
        // are always the same one. Keep the URL contract as item_id (not
        // row_id): callers/tests outside this page still address reviews by
        // item_id, and get_review_item() already resolves it exactly.
        itemId: modal.item.item_id,
        data: {},
      });
      markDecided(modal.item);
      closeModal();
      void refetch();
    } catch (error) {
      const message = errorMessage(error, 'Failed to approve review item');
      setActionError(message);
      showToast(message);
    } finally {
      endSubmit();
    }
  };

  const handleReject = async () => {
    if (modal.kind !== 'reject' || rejectReason.trim().length === 0 || !reviewerName) return;
    if (!beginSubmit('reject')) return;
    try {
      await rejectMutation.mutateAsync({
        itemId: modal.item.item_id,
        data: {
          reason: rejectReason.trim(),
        },
      });
      markDecided(modal.item);
      closeModal();
      void refetch();
    } catch (error) {
      const message = errorMessage(error, 'Failed to reject review item');
      setActionError(message);
      showToast(message);
    } finally {
      endSubmit();
    }
  };

  const approving = submitting === 'approve' || approveMutation.isPending;
  const rejecting = submitting === 'reject' || rejectMutation.isPending;

  const setFilter = (filter: string) => {
    setStatusFilter(filter);
    setPageLimit(PAGE_LIMIT_STEP);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground" data-testid="review-loading">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading review queue...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-24 text-destructive" data-testid="review-error">
        {error instanceof Error ? error.message : 'Failed to load review queue'}
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="review-page">
      {/* Header */}
      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">Review queue</h1>
        {projectName ? (
          <p className="text-sm text-muted-foreground">
            Human-in-the-loop review for {projectName}. Items requiring manual inspection and approval.
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">
            Human-in-the-loop review queue. Inspect and approve or reject flagged items.
          </p>
        )}
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border bg-card p-4" data-testid="stat-pending">
          <div className="text-sm text-muted-foreground">Pending</div>
          <div className="mt-1 text-2xl font-bold text-yellow-600">{pendingCount}</div>
        </div>
        <div className="rounded-lg border bg-card p-4" data-testid="stat-approved">
          <div className="text-sm text-muted-foreground">Approved</div>
          <div className="mt-1 text-2xl font-bold text-green-600">{approvedCount}</div>
        </div>
        <div className="rounded-lg border bg-card p-4" data-testid="stat-rejected">
          <div className="text-sm text-muted-foreground">Rejected</div>
          <div className="mt-1 text-2xl font-bold text-red-600">{rejectedCount}</div>
        </div>
        <div className="rounded-lg border bg-card p-4" data-testid="stat-escalated">
          <div className="text-sm text-muted-foreground">Escalated</div>
          <div className="mt-1 text-2xl font-bold text-orange-600">{escalatedCount}</div>
        </div>
      </div>

      {/* Filter */}
      <div className="flex gap-2">
        {['all', ReviewStatus.PENDING_REVIEW_REQUIRED, ReviewStatus.APPROVED, ReviewStatus.REJECTED, ReviewStatus.ESCALATED].map(
          (filter) => (
            <Button
              key={filter}
              variant={statusFilter === filter ? 'default' : 'outline'}
              size="sm"
              onClick={() => setFilter(filter)}
            >
              {filter === 'all' ? 'All' : statusLabel(filter)}
            </Button>
          ),
        )}
      </div>

      {/* Queue List */}
      {items.length === 0 ? (
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground" data-testid="review-empty">
          No review items found
        </div>
      ) : (
        <div className="space-y-3" data-testid="review-queue">
          {items.map((item) => (
            <ReviewItemCard
              key={item.item_id}
              item={item}
              projectId={projectId}
              reviewerIdentityReady={reviewerIdentityReady}
              actionsLocked={decidedKeys.has(decisionKey(item))}
              onApprove={(reviewItem) => {
                setActionError(null);
                setModal({ kind: 'approve', item: reviewItem });
              }}
              onReject={(reviewItem) => {
                setActionError(null);
                setModal({ kind: 'reject', item: reviewItem });
              }}
            />
          ))}
          {canLoadMore ? (
            <div className="flex justify-center pt-2">
              <Button
                variant="outline"
                onClick={() => setPageLimit((current) => Math.min(current + PAGE_LIMIT_STEP, MAX_PAGE_LIMIT))}
              >
                Load more
              </Button>
            </div>
          ) : null}
        </div>
      )}

      {/* Approve Dialog */}
      <Dialog
        open={modal.kind === 'approve'}
        onOpenChange={(open) => { if (!open) dismissModal(); }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Approve Review Item</DialogTitle>
            <DialogDescription>
              Confirm approval for this {modal.kind === 'approve' ? modal.item.item_type : ''} item.
              {modal.kind === 'approve' && modal.item.resumable
                ? ' This will resume the analysis workflow with an approved state.'
                : ' This will mark the item as approved.'}
            </DialogDescription>
          </DialogHeader>
          {modal.kind === 'approve' && (
            <div className="space-y-3 text-sm">
              <div>
                <span className="font-medium">Impact:</span>{' '}
                <Badge className={impactColor(modal.item.impact_level)}>
                  {modal.item.impact_level}
                </Badge>
              </div>
              <div>
                <span className="font-medium">Confidence:</span>{' '}
                {(modal.item.confidence * 100).toFixed(1)}%
              </div>
            </div>
          )}
          {approving ? (
            <p role="status" className="text-sm text-muted-foreground">
              Approving… resuming the analysis can take a minute. Keep this window open.
            </p>
          ) : null}
          {actionError ? (
            <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {actionError}
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={dismissModal} disabled={approving}>
              Cancel
            </Button>
            <Button
              onClick={handleApprove}
              disabled={approving || !reviewerIdentityReady}
              aria-busy={approving}
              title={!reviewerIdentityReady ? 'Loading your identity…' : undefined}
              className="bg-green-600 hover:bg-green-700"
            >
              {approving ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Confirm Approve
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject Dialog */}
      <Dialog
        open={modal.kind === 'reject'}
        onOpenChange={(open) => { if (!open) dismissModal(); }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Review Item</DialogTitle>
            <DialogDescription>
              Provide a reason for rejecting this item.
              {modal.kind === 'reject' && modal.item.resumable
                ? ' This will terminate the analysis workflow.'
                : ' This will mark the item as rejected.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <label htmlFor="reject-reason" className="text-sm font-medium">
              Rejection Reason
            </label>
            <textarea
              id="reject-reason"
              className="w-full rounded-md border bg-background px-3 py-2 text-sm min-h-[100px]"
              placeholder="Explain why this item is being rejected..."
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              maxLength={2000}
            />
            <div className="text-xs text-muted-foreground text-right">
              {rejectReason.length}/2000
            </div>
          </div>
          {rejecting ? (
            <p role="status" className="text-sm text-muted-foreground">
              Rejecting… this can take a moment. Keep this window open.
            </p>
          ) : null}
          {actionError ? (
            <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {actionError}
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={dismissModal} disabled={rejecting}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleReject}
              aria-busy={rejecting}
              disabled={
                rejecting ||
                rejectReason.trim().length === 0 ||
                !reviewerIdentityReady
              }
              title={!reviewerIdentityReady ? 'Loading your identity…' : undefined}
            >
              {rejecting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Confirm Reject
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
