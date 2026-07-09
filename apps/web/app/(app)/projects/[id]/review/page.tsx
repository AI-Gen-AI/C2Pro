'use client';

import { useMemo, useState } from 'react';
import { useUser } from '@clerk/nextjs';
import { useParams } from 'next/navigation';
import {
  CheckCircle2,
  Clock,
  AlertTriangle,
  XCircle,
  ArrowUpCircle,
  ChevronDown,
  ChevronUp,
  Loader2,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useProject } from '@/hooks/useProject';
import {
  useListReviewQueueApiV1HitlQueueGet,
  useApproveItemApiV1HitlQueueItemIdApprovePost,
  useRejectItemApiV1HitlQueueItemIdRejectPost,
} from '@/lib/api/generated/hitl/hitl';
import type { ReviewItemResponse } from '@/lib/api/generated/models';
import { ReviewStatus } from '@/lib/api/generated/models/reviewStatus';
import { ImpactLevel } from '@/lib/api/generated/models/impactLevel';

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

function statusColor(status: string): string {
  switch (status) {
    case ReviewStatus.APPROVED:
      return 'bg-green-100 text-green-700 border-green-200';
    case ReviewStatus.REJECTED:
      return 'bg-red-100 text-red-700 border-red-200';
    case ReviewStatus.ESCALATED:
      return 'bg-orange-100 text-orange-700 border-orange-200';
    case ReviewStatus.PENDING_REVIEW_REQUIRED:
    case ReviewStatus.PENDING_REVIEW_CONDITIONAL:
      return 'bg-yellow-100 text-yellow-700 border-yellow-200';
    case ReviewStatus.CLOSED:
      return 'bg-gray-100 text-gray-500 border-gray-200';
    default:
      return 'bg-blue-100 text-blue-700 border-blue-200';
  }
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case ReviewStatus.APPROVED:
      return <CheckCircle2 className="h-4 w-4 text-green-600" />;
    case ReviewStatus.REJECTED:
      return <XCircle className="h-4 w-4 text-red-600" />;
    case ReviewStatus.ESCALATED:
      return <ArrowUpCircle className="h-4 w-4 text-orange-600" />;
    case ReviewStatus.PENDING_REVIEW_REQUIRED:
    case ReviewStatus.PENDING_REVIEW_CONDITIONAL:
      return <Clock className="h-4 w-4 text-yellow-600" />;
    default:
      return <AlertTriangle className="h-4 w-4 text-gray-400" />;
  }
}

function impactColor(impact: string): string {
  switch (impact) {
    case ImpactLevel.CRITICAL:
      return 'bg-red-100 text-red-800';
    case ImpactLevel.HIGH:
      return 'bg-orange-100 text-orange-800';
    case ImpactLevel.MEDIUM:
      return 'bg-yellow-100 text-yellow-800';
    case ImpactLevel.LOW:
      return 'bg-green-100 text-green-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function isOverdue(slaDueDate: string): boolean {
  return new Date(slaDueDate) < new Date();
}

export default function ReviewPage() {
  const params = useParams();
  const projectId = params.id as string;
  const { isLoaded: isUserLoaded, user } = useUser();
  const reviewerName = user?.primaryEmailAddress?.emailAddress ?? user?.id;
  const reviewerIdentityReady = isUserLoaded && Boolean(reviewerName);
  const { data: project } = useProject(projectId);
  const projectName = project?.name?.trim() || projectId;

  const { data: queueData, isLoading, error, refetch } =
    useListReviewQueueApiV1HitlQueueGet(undefined);

  const approveMutation = useApproveItemApiV1HitlQueueItemIdApprovePost();
  const rejectMutation = useRejectItemApiV1HitlQueueItemIdRejectPost();

  const [modal, setModal] = useState<ModalState>({ kind: 'none' });
  const [rejectReason, setRejectReason] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [expandedItemId, setExpandedItemId] = useState<string | null>(null);

  const items = useMemo(() => queueData?.items ?? [], [queueData]);

  const filteredItems = useMemo(
    () =>
      statusFilter === 'all'
        ? items
        : items.filter((item) => item.current_status === statusFilter),
    [items, statusFilter],
  );

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
  };

  const handleApprove = async () => {
    if (modal.kind !== 'approve' || !reviewerName) return;
    try {
      await approveMutation.mutateAsync({
        itemId: modal.item.item_id,
        data: { reviewer_name: reviewerName },
      });
      closeModal();
      refetch();
    } catch {
      // Error handled by mutation state
    }
  };

  const handleReject = async () => {
    if (modal.kind !== 'reject' || rejectReason.trim().length === 0 || !reviewerName) return;
    try {
      await rejectMutation.mutateAsync({
        itemId: modal.item.item_id,
        data: {
          reviewer_name: reviewerName,
          reason: rejectReason.trim(),
        },
      });
      closeModal();
      refetch();
    } catch {
      // Error handled by mutation state
    }
  };

  const toggleExpand = (itemId: string) => {
    setExpandedItemId((prev) => (prev === itemId ? null : itemId));
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
        <h1 className="text-2xl font-bold tracking-tight">HITL Review Queue</h1>
        <p className="text-sm text-muted-foreground">
          Human-in-the-loop review for {projectName} - approve or reject analysis findings
        </p>
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
              onClick={() => setStatusFilter(filter)}
            >
              {filter === 'all' ? 'All' : statusLabel(filter)}
            </Button>
          ),
        )}
      </div>

      {/* Queue List */}
      {filteredItems.length === 0 ? (
        <div className="rounded-lg border bg-card p-12 text-center text-muted-foreground" data-testid="review-empty">
          No review items found
        </div>
      ) : (
        <div className="space-y-3" data-testid="review-queue">
          {filteredItems.map((item) => {
            const overdue = isOverdue(item.sla_due_date);
            const expanded = expandedItemId === item.item_id;
            const isPending =
              item.current_status === ReviewStatus.PENDING_REVIEW_REQUIRED ||
              item.current_status === ReviewStatus.PENDING_REVIEW_CONDITIONAL;

            return (
              <div
                key={item.item_id}
                className="rounded-lg border bg-card"
                data-testid={`review-item-${item.item_id}`}
              >
                {/* Main row */}
                <div className="flex items-center gap-4 p-4">
                  <StatusIcon status={item.current_status} />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium truncate">
                        {item.item_type}
                      </span>
                      <Badge className={statusColor(item.current_status)}>
                        {statusLabel(item.current_status)}
                      </Badge>
                      <Badge className={impactColor(item.impact_level)}>
                        {item.impact_level}
                      </Badge>
                      {overdue && isPending && (
                        <Badge variant="destructive">Overdue</Badge>
                      )}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      Confidence: {(item.confidence * 100).toFixed(0)}% | SLA:{' '}
                      {formatDate(item.sla_due_date)} | Created:{' '}
                      {formatDate(item.created_at)}
                      {item.approved_by && (
                        <> | Reviewed by: {item.approved_by} at {formatDate(item.approved_at)}</>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    {isPending && (
                      <>
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-green-600 hover:bg-green-50"
                          disabled={!reviewerIdentityReady}
                          title={!reviewerIdentityReady ? 'Loading your identity…' : undefined}
                          onClick={() => setModal({ kind: 'approve', item })}
                          data-testid={`approve-${item.item_id}`}
                        >
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-red-600 hover:bg-red-50"
                          disabled={!reviewerIdentityReady}
                          title={!reviewerIdentityReady ? 'Loading your identity…' : undefined}
                          onClick={() => setModal({ kind: 'reject', item })}
                          data-testid={`reject-${item.item_id}`}
                        >
                          Reject
                        </Button>
                      </>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => toggleExpand(item.item_id)}
                      data-testid={`expand-${item.item_id}`}
                    >
                      {expanded ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>

                {/* Expanded detail */}
                {expanded && (
                  <div className="border-t px-4 py-3 text-sm" data-testid={`detail-${item.item_id}`}>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <span className="font-medium text-muted-foreground">Item ID:</span>{' '}
                        <code className="text-xs">{item.item_id}</code>
                      </div>
                      <div>
                        <span className="font-medium text-muted-foreground">Item Type:</span>{' '}
                        {item.item_type}
                      </div>
                      <div>
                        <span className="font-medium text-muted-foreground">Confidence:</span>{' '}
                        {(item.confidence * 100).toFixed(1)}%
                      </div>
                      <div>
                        <span className="font-medium text-muted-foreground">Impact Level:</span>{' '}
                        {item.impact_level}
                      </div>
                    </div>

                    {/* Review history timeline */}
                    <div className="mt-4">
                      <h4 className="font-medium text-muted-foreground mb-2">Review Timeline</h4>
                      <div className="space-y-2 border-l-2 border-muted pl-4">
                        <div className="relative">
                          <div className="absolute -left-[1.3rem] top-1 h-2.5 w-2.5 rounded-full bg-blue-500" />
                          <div className="text-xs text-muted-foreground">
                            {formatDate(item.created_at)}
                          </div>
                          <div>Item created and queued for review</div>
                        </div>
                        {item.approved_by && (
                          <div className="relative">
                            <div
                              className={`absolute -left-[1.3rem] top-1 h-2.5 w-2.5 rounded-full ${
                                item.current_status === ReviewStatus.APPROVED
                                  ? 'bg-green-500'
                                  : 'bg-red-500'
                              }`}
                            />
                            <div className="text-xs text-muted-foreground">
                              {formatDate(item.approved_at)}
                            </div>
                            <div>
                              {item.current_status === ReviewStatus.APPROVED
                                ? `Approved by ${item.approved_by}`
                                : `Rejected by ${item.approved_by}`}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Item data if available */}
                    {item.item_data && (
                      <div className="mt-4">
                        <h4 className="font-medium text-muted-foreground mb-2">Item Data</h4>
                        <pre className="rounded bg-muted p-3 text-xs overflow-auto max-h-48">
                          {JSON.stringify(item.item_data, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Approve Dialog */}
      <Dialog
        open={modal.kind === 'approve'}
        onOpenChange={(open) => { if (!open) closeModal(); }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Approve Review Item</DialogTitle>
            <DialogDescription>
              Confirm approval for this {modal.kind === 'approve' ? modal.item.item_type : ''} item.
              This will resume the analysis workflow with an approved state.
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
          <DialogFooter>
            <Button variant="outline" onClick={closeModal}>
              Cancel
            </Button>
            <Button
              onClick={handleApprove}
              disabled={approveMutation.isPending || !reviewerIdentityReady}
              title={!reviewerIdentityReady ? 'Loading your identity…' : undefined}
              className="bg-green-600 hover:bg-green-700"
            >
              {approveMutation.isPending ? (
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
        onOpenChange={(open) => { if (!open) closeModal(); }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Review Item</DialogTitle>
            <DialogDescription>
              Provide a reason for rejecting this item. This will terminate the analysis workflow.
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
          <DialogFooter>
            <Button variant="outline" onClick={closeModal}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleReject}
              disabled={
                rejectMutation.isPending ||
                rejectReason.trim().length === 0 ||
                !reviewerIdentityReady
              }
              title={!reviewerIdentityReady ? 'Loading your identity…' : undefined}
            >
              {rejectMutation.isPending ? (
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
