/**
 * Test Suite ID: TS-FRT-HITL-QUEUE-001
 */
'use client';

import Link from 'next/link';
import {
  AlertTriangle,
  ArrowUpCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { ReviewItemResponse } from '@/lib/api/generated/models';
import { ReviewStatus } from '@/lib/api/generated/models/reviewStatus';

import { statusToToken, severityToToken } from '@/lib/ui/severity-tokens';

type ReviewItemCardProps = {
  item: ReviewItemResponse;
  projectId: string;
  reviewerIdentityReady: boolean;
  onApprove: (item: ReviewItemResponse) => void;
  onReject: (item: ReviewItemResponse) => void;
};

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
  return statusToToken(status);
}

function impactColor(impact: string): string {
  return severityToToken(impact);
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

function formatDate(dateStr: string | null | undefined): string | null {
  if (!dateStr) return null;
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

function getString(data: ReviewItemResponse['item_data'], key: string): string | null {
  const value = data?.[key];
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : null;
}

function firstString(data: ReviewItemResponse['item_data'], keys: string[]): string | null {
  for (const key of keys) {
    const value = getString(data, key);
    if (value) return value;
  }
  return null;
}

function hasData(data: ReviewItemResponse['item_data']): boolean {
  return Boolean(data && Object.keys(data).length > 0);
}

export function ReviewItemCard({
  item,
  projectId,
  reviewerIdentityReady,
  onApprove,
  onReject,
}: ReviewItemCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [rawOpen, setRawOpen] = useState(false);
  const overdue = isOverdue(item.sla_due_date);
  const isPending =
    item.current_status === ReviewStatus.PENDING_REVIEW_REQUIRED ||
    item.current_status === ReviewStatus.PENDING_REVIEW_CONDITIONAL;
  const title =
    firstString(item.item_data, ['title', 'summary', 'message', 'description', 'category']) ??
    item.item_type;
  const summary = firstString(item.item_data, ['summary', 'message', 'description']);
  const category = getString(item.item_data, 'category');
  const documentId = firstString(item.item_data, [
    'document_id',
    'documentId',
    'source_document_id',
    'evidence_document_id',
  ]);
  const createdAt = formatDate(item.created_at);
  const slaDueDate = formatDate(item.sla_due_date);
  const reviewedAt = formatDate(item.approved_at);

  return (
    <div className="rounded-lg border bg-card" data-testid={`review-item-${item.item_id}`}>
      <div className="flex items-start gap-4 p-4">
        <StatusIcon status={item.current_status} />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{title}</span>
            <Badge className={statusColor(item.current_status)}>
              {statusLabel(item.current_status)}
            </Badge>
            <Badge className={impactColor(item.impact_level)}>{item.impact_level}</Badge>
            <Badge variant="outline">Confidence {(item.confidence * 100).toFixed(0)}%</Badge>
            {overdue && isPending ? <Badge variant="destructive">Overdue</Badge> : null}
          </div>

          {summary && summary !== title ? (
            <p className="mt-1 text-sm text-muted-foreground">{summary}</p>
          ) : null}

          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            {category ? <span>Category: {category}</span> : null}
            {slaDueDate ? <span>SLA: {slaDueDate}</span> : null}
            {createdAt ? <span>Created: {createdAt}</span> : null}
            {item.approved_by ? <span>Reviewer: {item.approved_by}</span> : null}
            {reviewedAt ? <span>Reviewed: {reviewedAt}</span> : null}
            {documentId ? (
              <Link
                className="font-medium text-primary underline-offset-4 hover:underline"
                href={`/projects/${projectId}/evidence?documentId=${encodeURIComponent(documentId)}`}
              >
                View evidence
              </Link>
            ) : null}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {isPending ? (
            <>
              <Button
                size="sm"
                variant="outline"
                className="text-green-600 hover:bg-green-50"
                disabled={!reviewerIdentityReady}
                title={!reviewerIdentityReady ? 'Loading your identity...' : undefined}
                onClick={() => onApprove(item)}
                data-testid={`approve-${item.item_id}`}
              >
                Approve
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="text-red-600 hover:bg-red-50"
                disabled={!reviewerIdentityReady}
                title={!reviewerIdentityReady ? 'Loading your identity...' : undefined}
                onClick={() => onReject(item)}
                data-testid={`reject-${item.item_id}`}
              >
                Reject
              </Button>
            </>
          ) : null}
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setExpanded((current) => !current)}
            data-testid={`expand-${item.item_id}`}
            aria-label={expanded ? 'Collapse review item' : 'Expand review item'}
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      {expanded ? (
        <div className="border-t px-4 py-3 text-sm" data-testid={`detail-${item.item_id}`}>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <span className="font-medium text-muted-foreground">Item ID:</span>{' '}
              <code className="text-xs">{item.item_id}</code>
            </div>
            <div>
              <span className="font-medium text-muted-foreground">Item Type:</span> {item.item_type}
            </div>
            <div>
              <span className="font-medium text-muted-foreground">Impact:</span> {item.impact_level}
            </div>
            <div>
              <span className="font-medium text-muted-foreground">Confidence:</span>{' '}
              {(item.confidence * 100).toFixed(1)}%
            </div>
          </div>

          {hasData(item.item_data) ? (
            <div className="mt-4">
              <button
                type="button"
                className="text-sm font-medium text-muted-foreground underline-offset-4 hover:underline"
                onClick={() => setRawOpen((current) => !current)}
              >
                Raw data
              </button>
              {rawOpen ? (
                <pre className="mt-2 max-h-48 overflow-auto rounded bg-muted p-3 text-xs">
                  {JSON.stringify(item.item_data, null, 2)}
                </pre>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

