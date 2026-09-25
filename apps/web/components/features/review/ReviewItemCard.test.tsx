/**
 * Test Suite ID: TS-FRT-HITL-QUEUE-001
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReviewItemCard } from './ReviewItemCard';
import type { ReviewItemResponse } from '@/lib/api/generated/models';
import { ImpactLevel } from '@/lib/api/generated/models/impactLevel';
import { ReviewStatus } from '@/lib/api/generated/models/reviewStatus';

const item: ReviewItemResponse = {
  item_id: 'item-1',
  item_type: 'coherence_alert',
  current_status: ReviewStatus.PENDING_REVIEW_REQUIRED,
  confidence: 0.85,
  impact_level: ImpactLevel.HIGH,
  approved_by: null,
  approved_at: null,
  sla_due_date: '2026-12-31T00:00:00Z',
  created_at: '2026-04-09T10:00:00Z',
  item_data: {
    title: 'Budget mismatch requires review',
    summary: 'The detected budget evidence does not match the schedule package.',
    category: 'BUDGET',
    document_id: 'doc-123',
  },
};

describe('ReviewItemCard', () => {
  it('renders a human-readable summary and keeps raw JSON collapsed by default', () => {
    render(
      <ReviewItemCard
        item={item}
        projectId="project-1"
        reviewerIdentityReady
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText('Budget mismatch requires review')).toBeInTheDocument();
    expect(screen.getByText(/detected budget evidence/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View evidence' })).toHaveAttribute(
      'href',
      '/projects/project-1/evidence?documentId=doc-123',
    );
    expect(screen.queryByText(/"document_id"/)).not.toBeInTheDocument();
  });

  it('reveals raw data only from the disclosure', async () => {
    render(
      <ReviewItemCard
        item={item}
        projectId="project-1"
        reviewerIdentityReady
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByTestId('expand-item-1'));
    await userEvent.click(screen.getByText('Raw data'));

    expect(screen.getByText(/"document_id"/)).toBeInTheDocument();
  });
});

// C2PRO P0b HITL review UX hotfix: an analysis_critique review (a real
// LangGraph-gated HITL pause) must show a real decision title, the reason a
// human is in the loop, what the model concluded, and what each action
// means -- not just technical metadata. Object D #5.
const graphGatedItem: ReviewItemResponse = {
  item_id: 'doc-456',
  row_id: 'row-789',
  item_type: 'contract',
  current_status: ReviewStatus.PENDING_REVIEW_REQUIRED,
  confidence: 0,
  impact_level: ImpactLevel.HIGH,
  approved_by: null,
  approved_at: null,
  sla_due_date: '2026-12-31T00:00:00Z',
  created_at: '2026-04-09T10:00:00Z',
  resumable: true,
  item_data: {
    project_id: 'proj-1',
    document_id: 'doc-456',
    document_filename: 'contract_english_only.pdf',
    doc_type: 'contract',
    critique_notes: 'The extracted risk register omits a termination-for-convenience clause.',
    reason:
      'This document was flagged as high impact and requires human review before the analysis can complete.',
    approve_meaning:
      'Continue the analysis using this reviewed result. The document will be marked ANALYZED once processing completes.',
    reject_meaning:
      'Reject this result. The document will require correction or re-analysis before it can be marked ANALYZED.',
  },
};

describe('ReviewItemCard - graph-gated HITL review', () => {
  it('shows a real decision title, reason, model conclusion, and outcome meanings', () => {
    render(
      <ReviewItemCard
        item={graphGatedItem}
        projectId="project-1"
        reviewerIdentityReady
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(
      screen.getByText('Approve analysis of contract_english_only.pdf'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/flagged as high impact and requires human review/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/termination-for-convenience clause/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Continue the analysis using this reviewed result/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Reject this result\. The document will require correction/i),
    ).toBeInTheDocument();
  });

  it('never shows a literal 0% confidence as if it were a real score', () => {
    render(
      <ReviewItemCard
        item={graphGatedItem}
        projectId="project-1"
        reviewerIdentityReady
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.queryByText(/Confidence 0%/)).not.toBeInTheDocument();
    expect(screen.getAllByText(/Confidence: not evaluated/i).length).toBeGreaterThan(0);
  });

  it('hides row_id and other identifiers behind Technical details', async () => {
    render(
      <ReviewItemCard
        item={graphGatedItem}
        projectId="project-1"
        reviewerIdentityReady
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.queryByText('row-789')).not.toBeInTheDocument();

    await userEvent.click(screen.getByTestId('expand-doc-456'));

    expect(screen.getByText('row-789')).toBeInTheDocument();
    expect(screen.getByText('Technical details')).toBeInTheDocument();
  });
});
