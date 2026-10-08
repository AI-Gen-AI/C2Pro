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
