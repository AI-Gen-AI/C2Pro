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
