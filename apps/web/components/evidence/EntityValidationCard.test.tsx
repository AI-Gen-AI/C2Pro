import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

  it("shows unmeasured confidence without inventing a percentage", () => {
    render(
      <EntityValidationCard
        entity={{ ...clause, confidence: null, page: null }}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText("Not measured")).toBeInTheDocument();
    expect(screen.getByText("Exact location unavailable")).toBeInTheDocument();
    expect(screen.queryByText(/100% - High/)).not.toBeInTheDocument();
  });

  it("shows source section without claiming technical verification", () => {
    render(
      <EntityValidationCard
        entity={{
          ...clause,
          technicalSourceSection: "4.1.2",
          technicalSourceUnverified: true,
          confidence: null,
          page: null,
        }}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    expect(screen.getByText("Source section 4.1.2")).toBeInTheDocument();
    expect(screen.getByText("Technical requirement not verified")).toBeInTheDocument();
    expect(screen.getByText("Not measured")).toBeInTheDocument();
  });

  it("does not mark an inactive card as active", () => {
    render(<EntityValidationCard entity={clause} onApprove={vi.fn()} onReject={vi.fn()} />);

    expect(screen.getByTestId("evidence-entity-card")).toHaveAttribute("data-active", "false");
  });
});

describe("EntityValidationCard — only persistable decisions are actionable", () => {
  const supported: ExtractedEntity = { ...clause, confidence: 95, approvalResourceType: "stakeholders" };

  it("a clause (no approval resource) is inspection only: no Approve/Reject, no false 'validated' wording", () => {
    render(<EntityValidationCard entity={{ ...clause, confidence: 65, approvalResourceType: null }} onApprove={vi.fn()} onReject={vi.fn()} />);

    expect(screen.queryByRole("button", { name: /^approve$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^reject$/i })).not.toBeInTheDocument();
    expect(screen.getByTestId("entity-inspection-only")).toBeInTheDocument();
    expect(screen.getByTestId("entity-inspection-note")).toHaveTextContent(/nothing is saved from here/i);
    expect(screen.queryByText(/pending review/i)).not.toBeInTheDocument();
  });

  it("a supported entity uses ONE confirmation, calls the handler once and closes only after it resolves", async () => {
    const onApprove = vi.fn().mockResolvedValue(undefined);
    render(<EntityValidationCard entity={supported} onApprove={onApprove} onReject={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /^approve$/i }));
    expect(onApprove).not.toHaveBeenCalled();
    expect(screen.getByText(/shown as approved only after the server/i)).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("entity-approve-confirm"));

    await waitFor(() => expect(onApprove).toHaveBeenCalledTimes(1));
    expect(onApprove).toHaveBeenCalledWith("clause-b", undefined);
    await waitFor(() => expect(screen.queryByTestId("entity-approve-confirm")).not.toBeInTheDocument());
  });

  it("keeps the dialog open and shows the reason when the server did not save the decision", async () => {
    const onApprove = vi.fn().mockRejectedValue(new Error("The server did not save the decision. Nothing was changed; try again."));
    render(<EntityValidationCard entity={supported} onApprove={onApprove} onReject={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /^approve$/i }));
    await userEvent.click(screen.getByTestId("entity-approve-confirm"));

    expect(await screen.findByTestId("entity-decision-error")).toHaveTextContent(/did not save the decision/i);
    expect(screen.getByTestId("entity-approve-confirm")).toBeInTheDocument();
  });

  it("requires a validation note below 90% confidence and sends it", async () => {
    const onApprove = vi.fn().mockResolvedValue(undefined);
    render(<EntityValidationCard entity={{ ...supported, confidence: 65 }} onApprove={onApprove} onReject={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /^approve$/i }));
    expect(screen.getByTestId("entity-approve-confirm")).toBeDisabled();
    await userEvent.type(screen.getByTestId("entity-approval-note"), "Checked against the source.");
    await userEvent.click(screen.getByTestId("entity-approve-confirm"));

    await waitFor(() => expect(onApprove).toHaveBeenCalledWith("clause-b", "Checked against the source."));
  });
});
