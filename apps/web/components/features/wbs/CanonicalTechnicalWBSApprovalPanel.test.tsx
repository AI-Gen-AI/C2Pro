/** ACC-01 S7: explicit canonical approval is separate from durable audit. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { TechnicalWBSReviewHistoryEntry } from "@/lib/api/generated/models";
import { CanonicalTechnicalWBSApprovalPanel } from "./CanonicalTechnicalWBSApprovalPanel";

const post = vi.fn();
vi.mock("@/lib/api/client", () => ({
  orvalApiClient: (...args: unknown[]) => post(...args),
}));

const audit: TechnicalWBSReviewHistoryEntry = {
  event_id: "11111111-1111-1111-1111-111111111111",
  occurred_at: "2026-10-29T15:00:00Z",
  decision: "CONFIRMED_FOR_REVIEW",
  technical_document_id: "22222222-2222-2222-2222-222222222222",
  technical_revision_id: "33333333-3333-3333-3333-333333333333",
  source_clause_id: "44444444-4444-4444-4444-444444444444",
  source_section: "4.1",
  proposed_wbs_baseline_id: "55555555-5555-5555-5555-555555555555",
  proposed_wbs_node_id: "66666666-6666-6666-6666-666666666666",
  reason: "Reviewed independently",
  state: "HISTORICAL_AUDIT_ONLY",
  authority: "AUDIT_ONLY_NOT_CANONICAL_LINK",
  approved_canonical_link: false,
  technical_assessment: "NOT_ASSESSED",
};

const reply = {
  event_id: "77777777-7777-7777-7777-777777777777",
  replayed: false,
  technical_document_id: audit.technical_document_id,
  technical_revision_id: audit.technical_revision_id,
  source_clause_id: audit.source_clause_id,
  wbs_baseline_id: audit.proposed_wbs_baseline_id,
  wbs_node_id: audit.proposed_wbs_node_id,
  authority: "EXPLICIT_HUMAN_CANONICAL_LINK",
  approved_canonical_link: true,
  technical_assessment: "NOT_ASSESSED",
} as const;

function configureApproval() {
  fireEvent.change(screen.getByLabelText("Reason for final approval"), {
    target: { value: "I verified the approved source and baseline." },
  });
  fireEvent.click(screen.getByLabelText("Confirm explicit canonical approval"));
}

describe("CanonicalTechnicalWBSApprovalPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("crypto", { randomUUID: () => "canonical-s7-key-0000001" });
  });

  it("does not turn an audit-only review into approval without a separate human confirmation", () => {
    render(<CanonicalTechnicalWBSApprovalPanel projectId="project-1" audit={audit} />);
    const button = screen.getByTestId("technical-wbs-canonical-submit");
    expect(button).toBeDisabled();
    expect(screen.getByText(/earlier audit did not/i)).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
    configureApproval();
    expect(button).toBeEnabled();
  });

  it("POSTs only exact audit, baseline, node and explicit human approval, and validates receipt", async () => {
    post.mockResolvedValue(reply);
    render(<CanonicalTechnicalWBSApprovalPanel projectId="project-1" audit={audit} />);
    configureApproval();
    fireEvent.click(screen.getByTestId("technical-wbs-canonical-submit"));
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post).toHaveBeenCalledWith({
      method: "POST",
      url: "/api/v1/projects/project-1/technical-wbs/canonical-links",
      data: {
        review_event_id: audit.event_id,
        expected_wbs_baseline_id: audit.proposed_wbs_baseline_id,
        expected_wbs_node_id: audit.proposed_wbs_node_id,
        approval: "APPROVE_CANONICAL_LINK",
        idempotency_key: "canonical-s7-key-0000001",
        reason: "I verified the approved source and baseline.",
      },
    });
    const receipt = await screen.findByTestId("technical-wbs-canonical-receipt");
    expect(receipt).toHaveTextContent("Canonical association approved and recorded.");
    expect(receipt).toHaveTextContent("NOT ASSESSED");
    expect(screen.getByTestId("technical-wbs-canonical-submit")).toBeDisabled();
  });

  it("never offers the final approval action for rejected or noncanonical audit authorities", () => {
    const { rerender } = render(
      <CanonicalTechnicalWBSApprovalPanel projectId="project-1" audit={{ ...audit, decision: "REJECTED" }} />,
    );
    configureApproval();
    expect(screen.getByTestId("technical-wbs-canonical-submit")).toBeDisabled();
    rerender(
      <CanonicalTechnicalWBSApprovalPanel projectId="project-1" audit={{
        ...audit, decision: "CONFIRMED_FOR_REVIEW", authority: "EXPLICIT_HUMAN_CANONICAL_LINK" as typeof audit.authority,
      }} />,
    );
    expect(screen.getByTestId("technical-wbs-canonical-submit")).toBeDisabled();
    expect(post).not.toHaveBeenCalled();
  });

  it("fails closed when server receipt mismatches exact technical revision or WBS node", async () => {
    post.mockResolvedValue({ ...reply, wbs_node_id: "other-node" });
    render(<CanonicalTechnicalWBSApprovalPanel projectId="project-1" audit={audit} />);
    configureApproval();
    fireEvent.click(screen.getByTestId("technical-wbs-canonical-submit"));
    await waitFor(() =>
      expect(screen.getByTestId("technical-wbs-canonical-error")).toHaveTextContent(
        /approval outcome needs verification/i,
      ),
    );
    expect(screen.queryByTestId("technical-wbs-canonical-receipt")).not.toBeInTheDocument();
    expect(screen.getByTestId("technical-wbs-canonical-submit")).toBeDisabled();
  });

  it("does not blindly repeat a possibly committed event after 502", async () => {
    post.mockRejectedValue(new Error("502 after commit"));
    render(<CanonicalTechnicalWBSApprovalPanel projectId="project-1" audit={audit} />);
    configureApproval();
    fireEvent.click(screen.getByTestId("technical-wbs-canonical-submit"));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/do not submit this decision again/i));
    expect(screen.getByTestId("technical-wbs-canonical-submit")).toBeDisabled();
    expect(post).toHaveBeenCalledTimes(1);
  });
});
