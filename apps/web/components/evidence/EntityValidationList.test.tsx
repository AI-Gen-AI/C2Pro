/**
 * PQ-HITL-03: no false "nothing extracted" in an unresolved current view.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EntityValidationList } from './EntityValidationList';

describe('EntityValidationList truthful empty state', () => {
  it('does not equate an empty current view with no stored extraction', () => {
    render(
      <EntityValidationList
        entities={[]}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(
      screen.getByText('No clauses available in the current evidence view'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/pending review, or no clauses may have been extracted/i),
    ).toBeInTheDocument();
    expect(screen.queryByText('No entities found')).not.toBeInTheDocument();
    expect(
      screen.queryByText('No extracted entities available for this document.'),
    ).not.toBeInTheDocument();
  });
});

describe('EntityValidationList counters never invent a pending decision', () => {
  const clause = { id: 'c1', type: 'Clause', text: 'Clause text', confidence: 65, page: 1, approvalResourceType: null, validationStatus: 'pending' as const };
  const stakeholder = { id: 's1', type: 'Stakeholder', text: 'Stakeholder text', confidence: 95, page: 1, approvalResourceType: 'stakeholders', validationStatus: 'pending' as const };

  it('clauses are inspection only: not counted as pending and never approved by the counters', () => {
    render(<EntityValidationList entities={[clause]} onApprove={vi.fn()} onReject={vi.fn()} />);
    expect(screen.getByText('0 Pending')).toBeInTheDocument();
    expect(screen.getByText('0 Approved')).toBeInTheDocument();
    expect(screen.getByTestId('stat-inspection-only')).toHaveTextContent('1 Inspection only');
    expect(screen.queryByRole('button', { name: /review next pending/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^approve$/i })).not.toBeInTheDocument();
  });

  it('only entities whose decision can be persisted are pending and actionable', () => {
    render(<EntityValidationList entities={[clause, stakeholder]} onApprove={vi.fn()} onReject={vi.fn()} />);
    expect(screen.getByText('1 Pending')).toBeInTheDocument();
    expect(screen.getByTestId('stat-inspection-only')).toHaveTextContent('1 Inspection only');
    expect(screen.getAllByRole('button', { name: /^approve$/i })).toHaveLength(1);
  });
});
