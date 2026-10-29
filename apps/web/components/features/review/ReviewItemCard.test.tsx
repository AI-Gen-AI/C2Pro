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
      '/projects/project-1/evidence?documentId=doc-123&returnReviewItemId=item-1',
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

  it('distinguishes an explicitly assessed zero from unknown confidence', () => {
    render(
      <ReviewItemCard
        item={{
          ...graphGatedItem,
          item_data: { ...graphGatedItem.item_data, confidence_assessed: true },
        }}
        projectId="project-1"
        reviewerIdentityReady
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText('Confidence 0%')).toBeInTheDocument();
    expect(screen.queryByText('Confidence: not evaluated')).not.toBeInTheDocument();
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


describe('ReviewItemCard - progressive disclosure of unverified AI critique', () => {
  it('groups numbered critique notes without inventing proof or individual approval', async () => {
    const notes = [
      '1. MISSING CLAUSE REFERENCES: Clause 5.2 needs traceability.',
      '2. DEFECT RECTIFICATION: The source states Contractor cost within fourteen (14) days.',
    ].join('\n\n');
    render(
      <ReviewItemCard
        item={{
          ...graphGatedItem,
          item_data: { ...graphGatedItem.item_data, critique_notes: notes },
        }}
        projectId="project-1"
        reviewerIdentityReady
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText(/2 unverified AI critique observations/i)).toBeInTheDocument();
    expect(screen.getByText(/MISSING CLAUSE REFERENCES/i)).toBeInTheDocument();
    expect(screen.getByText(/DEFECT RECTIFICATION/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Verified findings$/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Approve full analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/original source evidence/i)).toBeInTheDocument();
  });
});

// C2PRO #714: decisions are offered only for the exact bound candidate, and an
// ESCALATED review is still awaiting a (senior) human decision.
describe('ReviewItemCard #714 decision readiness', () => {
  it('disables approve/reject and says so while the candidate is not bound yet', async () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    render(
      <ReviewItemCard
        item={{ ...graphGatedItem, decision_ready: false }}
        projectId="project-1"
        reviewerIdentityReady
        onApprove={onApprove}
        onReject={onReject}
      />,
    );

    expect(screen.getByTestId('approve-doc-456')).toBeDisabled();
    expect(screen.getByTestId('reject-doc-456')).toBeDisabled();
    expect(screen.getByTestId('candidate-preparing-doc-456')).toHaveTextContent(
      /preparing candidate/i,
    );
    await userEvent.click(screen.getByTestId('approve-doc-456'));
    expect(onApprove).not.toHaveBeenCalled();
  });

  it('offers decisions once the candidate is bound', () => {
    render(
      <ReviewItemCard
        item={{ ...graphGatedItem, decision_ready: true }}
        projectId="project-1"
        reviewerIdentityReady
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    expect(screen.getByTestId('approve-doc-456')).toBeEnabled();
    expect(screen.queryByTestId('candidate-preparing-doc-456')).not.toBeInTheDocument();
  });

  it('keeps an ESCALATED review actionable', () => {
    render(
      <ReviewItemCard
        item={{ ...graphGatedItem, current_status: ReviewStatus.ESCALATED, decision_ready: true }}
        projectId="project-1"
        reviewerIdentityReady
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    expect(screen.getByTestId('approve-doc-456')).toBeEnabled();
    expect(screen.getByTestId('reject-doc-456')).toBeEnabled();
  });
});

describe('PQ-HITL-06 review item source navigation', () => {
  it('renders independent source links only when document, revision and clause IDs exist', () => {
    render(
      <ReviewItemCard
        item={{ ...item, item_data: {
          ...item.item_data,
          source_references: [
            { document_id: 'doc-123', revision_id: 'rev-a', clause_id: 'clause-52', clause_code: '5.2' },
            { document_id: 'doc-123', revision_id: 'rev-a', clause_id: 'clause-13', clause_code: '1.3' },
          ],
        } }}
        projectId="project-1"
        reviewerIdentityReady
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    expect(screen.getByRole('link', { name: 'Inspect cited clause §5.2' })).toHaveAttribute(
      'href', '/projects/project-1/evidence?documentId=doc-123&revisionId=rev-a&highlightId=clause-52&returnReviewItemId=item-1',
    );
    expect(screen.getByRole('link', { name: 'Inspect cited clause §1.3' })).toHaveAttribute(
      'href', '/projects/project-1/evidence?documentId=doc-123&revisionId=rev-a&highlightId=clause-13&returnReviewItemId=item-1',
    );
    expect(screen.getByRole('link', { name: 'View evidence' })).toBeInTheDocument();
  });

  it('preserves three distinct multi-document §6.1/§6.3/§6.4 source addresses', () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    render(
      <ReviewItemCard
        item={{ ...item, item_data: {
          ...item.item_data,
          critique_notes: 'An unverified critique of §6.1 and §6.4.',
          source_references: [
            { document_id: 'doc-a', revision_id: 'rev-a', clause_id: 'a-61', clause_code: '6.1' },
            { document_id: 'doc-a', revision_id: 'rev-a', clause_id: 'a-63', clause_code: '6.3' },
            { document_id: 'doc-b', revision_id: 'rev-b', clause_id: 'b-64', clause_code: '6.4' },
            { document_id: 'doc-a', revision_id: 'rev-a', clause_id: 'a-61', clause_code: '6.1' },
            { document_id: 'doc-b', revision_id: 'rev-b', clause_code: '6.2' },
            { document_id: 'doc-b', clause_id: 'forged-65', clause_code: '6.5' },
          ],
        } }}
        projectId="project-1"
        reviewerIdentityReady
        onApprove={onApprove}
        onReject={onReject}
      />,
    );

    const sourceLinks = screen.getAllByRole('link', { name: /^Inspect cited clause §/ });
    expect(sourceLinks).toHaveLength(3);
    expect(sourceLinks.map((link) => link.getAttribute('href'))).toEqual([
      '/projects/project-1/evidence?documentId=doc-a&revisionId=rev-a&highlightId=a-61&returnReviewItemId=item-1',
      '/projects/project-1/evidence?documentId=doc-a&revisionId=rev-a&highlightId=a-63&returnReviewItemId=item-1',
      '/projects/project-1/evidence?documentId=doc-b&revisionId=rev-b&highlightId=b-64&returnReviewItemId=item-1',
    ]);
    // A source link locates a clause; it never turns the prose into a
    // verified finding or executes an HITL decision on navigation.
    expect(screen.queryByRole('link', { name: /§6\.5/ })).not.toBeInTheDocument();
    expect(onApprove).not.toHaveBeenCalled();
    expect(onReject).not.toHaveBeenCalled();
  });

});
