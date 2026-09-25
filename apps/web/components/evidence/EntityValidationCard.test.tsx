import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EntityValidationCard, type ExtractedEntity } from "./EntityValidationCard";

const clause: ExtractedEntity = {
  id: "clause-b",
  type: "payment",
  text: "The total contract price is 2,650,000.00 EUR.",
  confidence: 0.9,
  page: 1,
};

describe("EntityValidationCard — active evidence is observable", () => {
  it("exposes the entity id and marks the active card", () => {
    render(<EntityValidationCard entity={clause} onApprove={vi.fn()} onReject={vi.fn()} isActive />);

    const card = screen.getByTestId("evidence-entity-card");
    expect(card).toHaveAttribute("data-entity-id", "clause-b");
    expect(card).toHaveAttribute("data-active", "true");
  });

  it("does not mark an inactive card as active", () => {
    render(<EntityValidationCard entity={clause} onApprove={vi.fn()} onReject={vi.fn()} />);

    expect(screen.getByTestId("evidence-entity-card")).toHaveAttribute("data-active", "false");
  });
});
