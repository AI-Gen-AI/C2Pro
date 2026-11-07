'use client';

import { useEffect, useMemo, useRef, useState, type ComponentProps } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useUser } from '@clerk/nextjs';
import { useParams, useSearchParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { severityToToken } from '@/lib/ui/severity-tokens';
import { Button } from '@/components/ui/button';
import { ReviewFindingsPanel } from '@/components/features/review/ReviewFindingsPanel';
import { useReviewCapabilities } from '@/components/features/review/useReviewCapabilities';
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
import { useDecideStructuredSourceTrustApiV1StructuredSourceTrustDecisionsPost } from '@/lib/api/generated/structured-source-trust/structured-source-trust';
import { DecideStructuredSourceTrustBodyDecision } from '@/lib/api/generated/models/decideStructuredSourceTrustBodyDecision';
import { ReviewStatus } from '@/lib/api/generated/models/reviewStatus';
import { getGetProjectHealthApiV1ProjectsProjectIdHealthGetQueryKey } from '@/lib/api/generated/project-health/project-health';
import {
  getGetCoherenceDashboardApiCoherenceDashboardProjectIdGetQueryKey,
  getGetCoherenceDashboardApiV1CoherenceDashboardProjectIdGetQueryKey,
} from '@/lib/api/generated/coherence-dashboard/coherence-dashboard';

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
  // Axios surfaces HTTP status in error.message, while the API's precise
  // fail-closed reason is in response.data.detail. Preserve that reason so a
  // reviewer can distinguish a not-yet-bound checkpoint from other 400s.
  if (error && typeof error === 'object' && 'response' in error) {
    const response = (error as { response?: { data?: unknown } }).response;
    const data = response?.data;
    if (data && typeof data === 'object' && 'detail' in data) {
      const detail = (data as { detail?: unknown }).detail;
      if (typeof detail === 'string' && detail.trim()) return detail;
    }
  }
  return error instanceof Error && error.message.trim().length > 0
    ? error.message
    : fallback;
}

function outcomeMayAlreadyBeRecorded(error: unknown): boolean {
  // A 502 from HITL resume may occur AFTER the approval row was committed.
  // Never invite a blind second decision on the same immutable review row.
  if (error && typeof error === 'object' && 'response' in error) {
    const response = (error as { response?: { status?: unknown } }).response;
    if (response?.status === 502) return true;
  }
  return error instanceof Error && /\b502\b|review approved, but resuming/i.test(error.message);
}


/** S5-02: asks the server what the caller may do on THIS review's project, and stops offering what would be refused. */
function ReviewItemWithCapabilities(props: ComponentProps<typeof ReviewItemCard>) {
  const capabilities = useReviewCapabilities(props.item.row_id);
  return <ReviewItemCard {...props} finalDecisionNotGranted={capabilities?.approve_candidate === false} />;
}

/** Document + version a review row is about, for receipts (never invented: falls back to the item type). */
function receiptSubject(item: ReviewItemResponse): { documentLabel: string; version: number | null } {
  const data = (item.item_data ?? {}) as Record<string, unknown>;
  const filename = typeof data.document_filename === 'string' ? data.document_filename : null;
  const binding = item.candidate_binding as { artifact_version?: number } | null | undefined;
  return {
    documentLabel: filename ?? String(item.item_type),
    version: typeof binding?.artifact_version === 'number' ? binding.artifact_version : null,
  };
}

export default function ReviewPage() {
  const params = useParams();
  const projectId = params.id as string;
  // #712: the Documents page links here with ?itemId=<review_item_id> when a
  // document has exactly one pending review, so the reviewer lands on the
  // right card instead of having to find it in the full queue.
  const searchParams = useSearchParams();
  const targetItemId = searchParams.get('itemId');
  const { isLoaded: isUserLoaded, user } = useUser();
  const reviewerName = user?.primaryEmailAddress?.emailAddress ?? user?.id;
  const reviewerIdentityReady = isUserLoaded && Boolean(reviewerName);
  const { data: project } = useProject(projectId);
  const projectName = project?.name?.trim();

  const queryClient = useQueryClient();
  // A review decision changes the document's lifecycle (it resumes or needs changes). The Documents
  // list is cached for minutes and stops polling on a "review required" row, so without this it
  // keeps showing the pre-decision state until a manual reload.
  // HITL can change trusted document lifecycle AND Health/Coherence. Keep all
  // three views synchronized after the server records a decision; no automatic
  // Score or analysis-complete claim is made by these cache invalidations.
  const refreshProjectAfterDecision = () => {
    void queryClient.invalidateQueries({ queryKey: ['project-documents', projectId] });
    void queryClient.invalidateQueries({
      queryKey: getGetProjectHealthApiV1ProjectsProjectIdHealthGetQueryKey(projectId),
    });
    void queryClient.invalidateQueries({
      queryKey: getGetCoherenceDashboardApiCoherenceDashboardProjectIdGetQueryKey(projectId),
    });
    void queryClient.invalidateQueries({
      queryKey: getGetCoherenceDashboardApiV1CoherenceDashboardProjectIdGetQueryKey(projectId),
    });
  };

  const approveMutation = useApproveItemApiV1HitlQueueItemIdApprovePost();
  const rejectMutation = useRejectItemApiV1HitlQueueItemIdRejectPost();
  // ADR-032: a Budget/Schedule trust candidate is decided ONLY here, bound to the exact
  // id/version/hash the reviewer sees. The legacy approve/reject routes answer 409 for it.
  const structuredDecisionMutation =
    useDecideStructuredSourceTrustApiV1StructuredSourceTrustDecisionsPost();

  const [modal, setModal] = useState<ModalState>({ kind: 'none' });
  const [rejectReason, setRejectReason] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  // A Documents→Review deep link must actually find the item even if it
  // is not among the default first 50. The backend caps this at 200.
  const [pageLimit, setPageLimit] = useState(
    targetItemId ? MAX_PAGE_LIMIT : PAGE_LIMIT_STEP,
  );
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
  const [decisionReceipt, setDecisionReceipt] = useState<{
    rowId: string;
    action: 'approve' | 'reject';
    /** A 5xx may occur after the server durably records the decision. */
    uncertain: boolean;
    /** What the reviewer decided on, captured at click time (the row may later fall outside the filter). */
    documentLabel: string;
    version: number | null;
  } | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

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
    // A new revision of an already-reviewed document opens a NEW review row. The queue is cached for
    // minutes, so opening the page must always ask the server instead of showing the previous
    // (already decided) queue with nothing left to approve.
    useListReviewQueueApiV1HitlQueueGet(queueParams, { query: { refetchOnMount: 'always' } });

  // Counters describe the whole project queue, never the list filter: a separate unfiltered read.
  const statsParams = useMemo(
    () => ({ skip: 0, limit: MAX_PAGE_LIMIT, project_id: projectId }),
    [projectId],
  );
  const { data: statsData, refetch: refetchStats } =
    useListReviewQueueApiV1HitlQueueGet(statsParams, { query: { refetchOnMount: 'always' } });
  const statsItems = useMemo(() => statsData?.items ?? [], [statsData]);
  const statsTruncated = (statsData?.total ?? 0) > statsItems.length;

  const items = useMemo(() => queueData?.items ?? [], [queueData]);

  const refreshQueue = async () => {
    setRefreshing(true);
    try {
      await Promise.all([refetch(), refetchStats()]);
      setLastChecked(new Date());
    } finally {
      setRefreshing(false);
    }
  };
  useEffect(() => {
    if (targetItemId) setPageLimit(MAX_PAGE_LIMIT);
  }, [targetItemId]);
  const targetIsMissing = Boolean(
    targetItemId && pageLimit === MAX_PAGE_LIMIT &&
    !items.some((item) => item.item_id === targetItemId),
  );
  const receiptRow = decisionReceipt
    ? statsItems.find((item) => item.row_id === decisionReceipt.rowId)
    : undefined;
  const confirmedDecision = Boolean(
    receiptRow && decisionReceipt &&
    receiptRow.current_status === (decisionReceipt.action === 'approve'
      ? ReviewStatus.APPROVED : ReviewStatus.REJECTED),
  );
  const canLoadMore = items.length === pageLimit && pageLimit < MAX_PAGE_LIMIT;

  useEffect(() => {
    if (!targetItemId) return;
    if (!items.some((item) => item.item_id === targetItemId)) return;
    document
      .getElementById(`review-item-${targetItemId}`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [targetItemId, items]);

  const pendingCount = statsItems.filter(
    (i) =>
      i.current_status === ReviewStatus.PENDING_REVIEW_REQUIRED ||
      i.current_status === ReviewStatus.PENDING_REVIEW_CONDITIONAL,
  ).length;
  const approvedCount = statsItems.filter(
    (i) => i.current_status === ReviewStatus.APPROVED,
  ).length;
  const rejectedCount = statsItems.filter(
    (i) => i.current_status === ReviewStatus.REJECTED,
  ).length;
  const escalatedCount = statsItems.filter(
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

  const decideStructuredSource = async (
    item: ReviewItemResponse,
    reviewRowId: string,
    decision: DecideStructuredSourceTrustBodyDecision,
    reason: string,
  ) => {
    const binding = item.candidate_binding as
      | { artifact_id?: string; artifact_version?: number; artifact_hash?: string }
      | null
      | undefined;
    if (!binding?.artifact_id || !binding.artifact_version || !binding.artifact_hash) {
      throw new Error('The exact candidate is unavailable. Refresh the queue before deciding.');
    }
    await structuredDecisionMutation.mutateAsync({
      data: {
        review_row_id: reviewRowId,
        artifact_id: binding.artifact_id,
        artifact_version: binding.artifact_version,
        artifact_hash: binding.artifact_hash,
        decision,
        // Deterministic per review row + decision: a retried request is an idempotent replay.
        idempotency_key: `ui-${decision.toLowerCase()}-${reviewRowId}`,
        reason,
      },
    });
  };

  const handleApprove = async () => {
    if (modal.kind !== 'approve' || !reviewerName) return;
    if (!beginSubmit('approve')) return;
    try {
      const reviewRowId = modal.item.row_id;
      if (!reviewRowId) {
        throw new Error(
          'Exact review identity is unavailable. Refresh the queue before deciding.',
        );
      }
      // #714: decisions from the user-facing queue target the immutable
      // review row, never the reusable business item_id. A stale V1 modal
      // therefore reaches V1 (now CLOSED) and fails closed instead of
      // resolving onto an unseen V2 review for the same document.
      if (modal.item.trust_kind === 'structured_source') {
        await decideStructuredSource(
          modal.item,
          reviewRowId,
          DecideStructuredSourceTrustBodyDecision.APPROVE,
          'Human approval of the exact structured source (id, version and hash shown in the review).',
        );
      } else {
        await approveMutation.mutateAsync({
          itemId: reviewRowId,
          data: {},
        });
      }
      markDecided(modal.item);
      setDecisionReceipt({ rowId: reviewRowId, action: 'approve', uncertain: false, ...receiptSubject(modal.item) });
      closeModal();
      void refreshQueue();
      refreshProjectAfterDecision();
    } catch (error) {
      const message = errorMessage(error, 'Failed to approve review item');
      if (outcomeMayAlreadyBeRecorded(error) && modal.kind === 'approve' && modal.item.row_id) {
        markDecided(modal.item);
        setDecisionReceipt({ rowId: modal.item.row_id, action: 'approve', uncertain: true, ...receiptSubject(modal.item) });
        void refreshQueue();
        refreshProjectAfterDecision();
      }
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
      const reviewRowId = modal.item.row_id;
      if (!reviewRowId) {
        throw new Error(
          'Exact review identity is unavailable. Refresh the queue before deciding.',
        );
      }
      if (modal.item.trust_kind === 'structured_source') {
        await decideStructuredSource(
          modal.item,
          reviewRowId,
          DecideStructuredSourceTrustBodyDecision.REJECT,
          rejectReason.trim(),
        );
      } else {
        await rejectMutation.mutateAsync({
          itemId: reviewRowId,
          data: {
            reason: rejectReason.trim(),
          },
        });
      }
      markDecided(modal.item);
      setDecisionReceipt({ rowId: reviewRowId, action: 'reject', uncertain: false, ...receiptSubject(modal.item) });
      closeModal();
      void refreshQueue();
      refreshProjectAfterDecision();
    } catch (error) {
      const message = errorMessage(error, 'Failed to reject review item');
      if (outcomeMayAlreadyBeRecorded(error) && modal.kind === 'reject' && modal.item.row_id) {
        markDecided(modal.item);
        setDecisionReceipt({ rowId: modal.item.row_id, action: 'reject', uncertain: true, ...receiptSubject(modal.item) });
        void refreshQueue();
        refreshProjectAfterDecision();
      }
      setActionError(message);
      showToast(message);
    } finally {
      endSubmit();
    }
  };

  const approving =
    submitting === 'approve' || approveMutation.isPending || structuredDecisionMutation.isPending;
  const rejecting =
    submitting === 'reject' || rejectMutation.isPending || structuredDecisionMutation.isPending;

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

      {targetIsMissing ? (
        <div data-testid="review-target-unavailable" role="status"
             className="rounded-lg border bg-muted/40 p-4 text-sm">
          This linked review item is not in the current project queue (up to 200 items).
          It may have moved or no longer be available. No other review was selected.
        </div>
      ) : null}

      {decisionReceipt ? (() => {
        const verb = decisionReceipt.action === 'approve' ? 'approval' : 'rejection';
        const doneWord = decisionReceipt.action === 'approve' ? 'Approved' : 'Rejected';
        const subject = `${decisionReceipt.documentLabel}${decisionReceipt.version !== null ? ` · version ${decisionReceipt.version}` : ''}`;
        const serverStatus = receiptRow ? statusLabel(receiptRow.current_status) : null;
        return (
          <div data-testid="review-decision-receipt" role="status"
               className="flex flex-col gap-3 rounded-lg border bg-card p-4 text-sm sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0 break-words">
              <p className="font-medium" data-testid="review-receipt-title">
                {confirmedDecision
                  ? `${doneWord} and saved: ${subject}`
                  : decisionReceipt.uncertain
                    ? `Outcome of your ${verb} needs verification: ${subject}`
                    : `Your ${verb} was sent, NOT yet confirmed as saved: ${subject}`}
              </p>
              <p className="text-muted-foreground">
                {confirmedDecision
                  ? 'The server now shows this review as decided. Document processing and Health may still be updating.'
                  : decisionReceipt.uncertain
                    ? 'The workflow reported an error after the request. The decision may already be stored; refresh the status before deciding again.'
                    : 'Press "Refresh review status" to read the saved state. Do not treat the document as analyzed until it shows as decided.'}
              </p>
              <p className="mt-1 text-xs text-muted-foreground" data-testid="review-receipt-server-status">
                {lastChecked
                  ? serverStatus
                    ? `Server status at ${lastChecked.toLocaleTimeString()}: ${serverStatus}.`
                    : `Checked at ${lastChecked.toLocaleTimeString()}: this review row was not found in the project queue.`
                  : serverStatus
                    ? `Server status: ${serverStatus}.`
                    : 'Not checked yet.'}
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="self-start sm:self-center"
              disabled={refreshing}
              onClick={() => void refreshQueue()}
              data-testid="review-refresh-status"
            >
              {refreshing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Refresh review status
            </Button>
          </div>
        );
      })() : null}

      {/* Stats Cards: whole project queue, independent of the list filter below */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4" data-testid="review-stats">
        <div className="rounded-lg border bg-card p-3 sm:p-4" data-testid="stat-pending">
          <div className="text-sm text-muted-foreground">Pending</div>
          <div className="mt-1 text-2xl font-bold text-yellow-600">{pendingCount}</div>
        </div>
        <div className="rounded-lg border bg-card p-3 sm:p-4" data-testid="stat-approved">
          <div className="text-sm text-muted-foreground">Approved</div>
          <div className="mt-1 text-2xl font-bold text-green-600">{approvedCount}</div>
        </div>
        <div className="rounded-lg border bg-card p-3 sm:p-4" data-testid="stat-rejected">
          <div className="text-sm text-muted-foreground">Rejected</div>
          <div className="mt-1 text-2xl font-bold text-red-600">{rejectedCount}</div>
        </div>
        <div className="rounded-lg border bg-card p-3 sm:p-4" data-testid="stat-escalated">
          <div className="text-sm text-muted-foreground">Escalated</div>
          <div className="mt-1 text-2xl font-bold text-orange-600">{escalatedCount}</div>
        </div>
      </div>
      {statsTruncated ? (
        <p className="text-xs text-muted-foreground" data-testid="stats-truncated">
          Counts cover the {statsItems.length} most recent of {statsData?.total} review items.
        </p>
      ) : null}

      {/* Filter: wraps on phones */}
      <div className="flex flex-wrap gap-2" data-testid="review-filters">
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
            <div
              // item_id is reusable across revisions; a new row must remount
              // fresh controls rather than inherit the previous row's UI state.
              key={decisionKey(item)}
              id={`review-item-${item.item_id}`}
              className={
                targetItemId === item.item_id
                  ? 'rounded-lg ring-2 ring-primary ring-offset-2'
                  : undefined
              }
            >
            <ReviewItemWithCapabilities
              item={item}
              projectId={projectId}
              reviewerIdentityReady={reviewerIdentityReady}
              actionsLocked={decidedKeys.has(decisionKey(item))}
              renderFindings={(reviewItem) =>
                reviewItem.row_id ? <ReviewFindingsPanel reviewRowId={reviewItem.row_id} /> : null
              }
              onApprove={(reviewItem) => {
                setActionError(null);
                setModal({ kind: 'approve', item: reviewItem });
              }}
              onReject={(reviewItem) => {
                setActionError(null);
                setModal({ kind: 'reject', item: reviewItem });
              }}
            />
            </div>
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
                <span className="font-medium">Extraction confidence:</span>{' '}
                {modal.item.item_data?.['confidence_assessed'] === true ||
                (modal.item.item_data?.['confidence_assessed'] !== false && modal.item.confidence > 0)
                  ? (modal.item.confidence * 100).toFixed(1) + '%'
                  : 'Not evaluated'}
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
              disabled={approving || !reviewerIdentityReady ||
                Boolean(decisionReceipt?.uncertain && modal.kind === 'approve' &&
                  decisionReceipt.rowId === modal.item.row_id)}
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
                !reviewerIdentityReady ||
                Boolean(decisionReceipt?.uncertain && modal.kind === 'reject' &&
                  decisionReceipt.rowId === modal.item.row_id)
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
