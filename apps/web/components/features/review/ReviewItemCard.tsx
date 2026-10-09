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
  /** A decision for this row was already submitted; wait for the refreshed queue. */
  actionsLocked?: boolean;
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

// Default outcome copy, used only when the backend didn't supply
// item_data.approve_meaning / reject_meaning (older review rows created
// before this field existed). Never shown for a graph-resumable review,
// whose approve/reject meanings always come from the backend.
const DEFAULT_APPROVE_MEANING = 'Mark this item as approved.';
const DEFAULT_REJECT_MEANING = 'Mark this item as rejected and record the reason given.';

/** Why Approve/Reject are disabled, first reason wins; undefined when enabled. */
function actionsBlockedReason(state: {
  actionsLocked: boolean;
  exactIdentityMissing: boolean;
  candidatePending: boolean;
  reviewerIdentityReady: boolean;
}): string | undefined {
  if (state.actionsLocked) return 'Decision submitted. Refreshing the queue...';
  if (state.exactIdentityMissing) {
    return 'Exact review identity unavailable. Refresh the queue before deciding.';
  }
  if (state.candidatePending) return 'Preparing the analysis candidate for review...';
  if (!state.reviewerIdentityReady) return 'Loading your identity...';
  return undefined;
}

// Presentation-only segmentation of numbered reviewer prose. It does NOT
// convert model claims into verified evidence or per-finding decisions.
function parseCritiqueObservations(notes: string): { number: number; title: string; body: string }[] | null {
  const headers = Array.from(notes.matchAll(/^(\d{1,2})\.\s+([^\n:]{5,120}):[ \t]*/gm));
  if (headers.length < 2) return null;

  return headers.map((match, index) => {
    const start = (match.index ?? 0) + match[0].length;
    const end = headers[index + 1]?.index ?? notes.length;
    return {
      number: Number(match[1]),
      title: match[2].trim(),
      body: notes.slice(start, end).trim(),
    };
  });
}

// Typed, untrusted model observations. A source location is NOT validation of
// the criticism, nor permission to approve an individual finding.
type CritiqueWitnessDisplay = {
  claim: string;
  quote: string;
  witnessStatus: string;
  sourceBasis: string | null;
  revisionId: string | null;
  quoteTruncated: boolean;
};

function sourceCritiqueObservations(
  data: ReviewItemResponse['item_data'],
): CritiqueWitnessDisplay[] {
  const raw = data?.['critique_observations'];
  if (!Array.isArray(raw)) return [];
  return raw.slice(0, 32).flatMap((value): CritiqueWitnessDisplay[] => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return [];
    const observation = value as Record<string, unknown>;
    const claim = observation.claim;
    if (typeof claim !== 'string' || !claim.trim()) return [];
    return [{
      claim: claim.trim(),
      quote: typeof observation.source_quote === 'string' ? observation.source_quote : '',
      witnessStatus: typeof observation.witness_status === 'string'
        ? observation.witness_status : 'UNRESOLVED',
      sourceBasis: typeof observation.source_basis === 'string'
        ? observation.source_basis : null,
      revisionId: typeof observation.document_revision_id === 'string'
        ? observation.document_revision_id : null,
      quoteTruncated: observation.source_quote_truncated === true,
    }];
  });
}

export function ReviewItemCard({
  item,
  projectId,
  reviewerIdentityReady,
  actionsLocked = false,
  onApprove,
  onReject,
}: ReviewItemCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [rawOpen, setRawOpen] = useState(false);
  const overdue = isOverdue(item.sla_due_date);
  // C2PRO #714: ESCALATED is still awaiting a (senior) human decision and is
  // decided through the same exact-row resume path.
  const isPending =
    item.current_status === ReviewStatus.PENDING_REVIEW_REQUIRED ||
    item.current_status === ReviewStatus.PENDING_REVIEW_CONDITIONAL ||
    item.current_status === ReviewStatus.ESCALATED;
  // C2PRO #714: the exact analysis candidate is not persisted/bound yet.
  // The backend refuses a decision regardless; never offer one here.
  const candidatePending = item.decision_ready === false;

  // C2PRO P0b HITL review UX hotfix: a reviewer needs a real decision
  // title, the reason a human is in the loop at all, what the model
  // actually concluded, and what each action does -- not a bare item_id.
  // These fields come from item_data when the backend supplied them
  // (human_interrupt_node, for graph-gated reviews); firstString/getString
  // return null when absent, so nothing here is invented -- the card falls
  // back to the generic item_type/summary fields other review producers
  // already populate.
  const documentFilename = getString(item.item_data, 'document_filename');
  const summary = firstString(item.item_data, ['summary', 'message', 'description']);
  const category = getString(item.item_data, 'category');
  const reason = getString(item.item_data, 'reason');
  const modelConclusion = getString(item.item_data, 'critique_notes');
  const critiqueObservations = modelConclusion ? parseCritiqueObservations(modelConclusion) : null;
  const sourceObservations = sourceCritiqueObservations(item.item_data);
  const approveMeaning =
    getString(item.item_data, 'approve_meaning') ??
    (item.resumable ? null : DEFAULT_APPROVE_MEANING);
  const rejectMeaning =
    getString(item.item_data, 'reject_meaning') ??
    (item.resumable ? null : DEFAULT_REJECT_MEANING);

  const title = documentFilename
    ? `Approve analysis of ${documentFilename}`
    : (firstString(item.item_data, ['title', 'summary', 'message', 'description', 'category']) ??
      item.item_type);

  const documentId = firstString(item.item_data, [
    'document_id',
    'documentId',
    'source_document_id',
    'evidence_document_id',
  ]);
  const createdAt = formatDate(item.created_at);
  const slaDueDate = formatDate(item.sla_due_date);
  const reviewedAt = formatDate(item.approved_at);

  // A literal, exact 0% is far more likely to mean "never evaluated for
  // this review type" than a genuine zero out of a continuous confidence
  // distribution -- showing it as a real score would misrepresent it.
  const confidenceIsMeaningful = item.confidence > 0;

  const exactIdentityMissing = !item.row_id;
  const actionsDisabled =
    !reviewerIdentityReady || actionsLocked || candidatePending || exactIdentityMissing;
  const actionsTitle = actionsBlockedReason({
    actionsLocked,
    exactIdentityMissing,
    candidatePending,
    reviewerIdentityReady,
  });

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
            {item.impact_level ? (
              <Badge className={impactColor(item.impact_level)}>{item.impact_level}</Badge>
            ) : null}
            {confidenceIsMeaningful ? (
              <Badge variant="outline">Confidence {(item.confidence * 100).toFixed(0)}%</Badge>
            ) : (
              <Badge variant="outline" title="Not evaluated for this review type">
                Confidence: not evaluated
              </Badge>
            )}
            {overdue && isPending ? <Badge variant="destructive">Overdue</Badge> : null}
          </div>

          {reason ? <p className="mt-1 text-sm">{reason}</p> : null}
          {summary && summary !== title ? (
            <p className="mt-1 text-sm text-muted-foreground">{summary}</p>
          ) : null}

          {sourceObservations.length > 0 ? (
            <section className="mt-3 space-y-2" aria-label="Source-witnessed critique observations">
              <p className="font-medium text-sm">
                {sourceObservations.length} observations requiring human verification
              </p>
              <p className="text-xs text-muted-foreground">
                AI-generated quality concerns, not verified contractual findings.
                A located quotation confirms only matching text in the supplied source excerpt.
                These items cannot be approved individually in this review.
              </p>
              {sourceObservations.map((observation, index) => (
                <div key={index} className="rounded-md border p-3 text-sm">
                  <p className="font-medium">{index + 1}. {observation.claim}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {observation.witnessStatus === 'LOCATED'
                      ? 'Source text located — claim not verified'
                      : `Source witness: ${observation.witnessStatus} — claim not verified`}
                  </p>
                  {observation.quote ? (
                    <blockquote className="mt-2 whitespace-pre-wrap border-l-2 pl-3 text-muted-foreground">
                      {observation.quote}
                      {observation.quoteTruncated ? ' [truncated; not independently verified]' : ''}
                    </blockquote>
                  ) : (
                    <p className="mt-2 text-xs text-muted-foreground">
                      No source quotation supplied.
                    </p>
                  )}
                  {observation.sourceBasis ? (
                    <p className="mt-2 text-xs text-muted-foreground">
                      Source representation: {observation.sourceBasis}
                      {observation.revisionId ? ` · Revision ${observation.revisionId}` : ''}
                    </p>
                  ) : null}
                </div>
              ))}
            </section>
          ) : null}

          {modelConclusion ? (
            <div className="mt-2 rounded-md bg-muted/50 p-3 text-sm">
              {critiqueObservations ? (
                <div className="space-y-2">
                  <p className="font-medium">
                    {critiqueObservations.length} unverified AI critique observations
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Preliminary model comments, not verified findings. Check the original source
                    evidence before approving or rejecting the whole analysis.
                  </p>
                  {critiqueObservations.map((observation) => (
                    <details
                      key={observation.number}
                      className="rounded-md border border-border/70 bg-background/80 p-2"
                    >
                      <summary className="cursor-pointer font-medium">
                        {observation.number}. {observation.title}
                      </summary>
                      <p className="mt-2 whitespace-pre-wrap text-muted-foreground">
                        {observation.body}
                      </p>
                    </details>
                  ))}
                </div>
              ) : (
                <>
                  <span className="font-medium text-muted-foreground">
                    Unverified model critique:{' '}
                  </span>
                  <span className="whitespace-pre-wrap">{modelConclusion}</span>
                </>
              )}
            </div>
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

          {isPending && (approveMeaning || rejectMeaning) ? (
            <div className="mt-2 space-y-0.5 text-xs text-muted-foreground">
              {approveMeaning ? (
                <p>
                  <span className="font-medium text-green-700">Approve:</span> {approveMeaning}
                </p>
              ) : null}
              {rejectMeaning ? (
                <p>
                  <span className="font-medium text-red-700">Reject:</span> {rejectMeaning}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {isPending ? (
            <>
              <Button
                size="sm"
                variant="outline"
                className="text-green-600 hover:bg-green-50"
                disabled={actionsDisabled}
                title={actionsTitle}
                onClick={() => onApprove(item)}
                data-testid={`approve-${item.item_id}`}
              >
                {modelConclusion && item.resumable ? 'Approve full analysis' : 'Approve'}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="text-red-600 hover:bg-red-50"
                disabled={actionsDisabled}
                title={actionsTitle}
                onClick={() => onReject(item)}
                data-testid={`reject-${item.item_id}`}
              >
                Reject
              </Button>
              {candidatePending ? (
                <span
                  className="text-xs text-muted-foreground"
                  data-testid={`candidate-preparing-${item.item_id}`}
                >
                  Preparing candidate…
                </span>
              ) : null}
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
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Technical details
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <span className="font-medium text-muted-foreground">Item ID:</span>{' '}
              <code className="text-xs">{item.item_id}</code>
            </div>
            {item.row_id ? (
              <div>
                <span className="font-medium text-muted-foreground">Review row ID:</span>{' '}
                <code className="text-xs">{item.row_id}</code>
              </div>
            ) : null}
            <div>
              <span className="font-medium text-muted-foreground">Item Type:</span> {item.item_type}
            </div>
            <div>
              <span className="font-medium text-muted-foreground">Impact:</span> {item.impact_level}
            </div>
            <div>
              <span className="font-medium text-muted-foreground">Confidence:</span>{' '}
              {confidenceIsMeaningful ? `${(item.confidence * 100).toFixed(1)}%` : 'Not evaluated'}
            </div>
            <div>
              <span className="font-medium text-muted-foreground">Resumable workflow:</span>{' '}
              {item.resumable ? 'Yes' : 'No'}
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
