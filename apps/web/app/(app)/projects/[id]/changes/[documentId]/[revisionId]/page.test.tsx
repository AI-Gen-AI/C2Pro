/**
 * Test Suite ID: TS-P0C-WHAT-CHANGED-UI-002
 * Change evidence never presents an inferred or ambiguous clause pairing as an established
 * modification: a change that needs review says so, with the reason the pairing was proposed.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@/src/tests/test-utils";

const apiClientGetMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "proj_1", documentId: "doc_1", revisionId: "rev_2" }),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: (...args: unknown[]) => apiClientGetMock(...args),
  },
}));

import ChangeDetailPage from "./page";

function detail(changes: Array<Record<string, unknown>>, state = "ready") {
  apiClientGetMock.mockResolvedValue({
    data: {
      state,
      change_cause: "BUSINESS_STATE_CHANGED",
      confidence: state === "ready" ? 1 : 0.82,
      evidence_refs: [],
      changes,
    },
  });
}

describe("ChangeDetailPage — trust state of each change", () => {
  beforeEach(() => {
    apiClientGetMock.mockReset();
  });

  it("marks a similarity-proposed pairing as needing review and explains why", async () => {
    detail(
      [
        {
          change_type: "modified",
          anchor: "AUTO-003",
          semantic_summary: "clause AUTO-003 text modified",
          before: { full_text: "Delay penalties are 0.5% per day." },
          after: { full_text: "Delay penalties are 1.0% per day." },
          needs_review: true,
          match_basis: "similarity_candidate",
          match_rationale: "proposed by text similarity 0.82; identity is not established",
        },
      ],
      "needs_review",
    );

    render(<ChangeDetailPage />);

    const change = within(await screen.findByTestId("change-0"));
    expect(change.getByText("Needs review")).toBeInTheDocument();
    expect(change.getByText(/identity is not established/)).toBeInTheDocument();
    expect(screen.getByTestId("change-detail-state")).toHaveTextContent("Needs review");
  });

  it("does not flag a deterministic change", async () => {
    detail([
      {
        change_type: "modified",
        anchor: "3",
        semantic_summary: "clause 3 text modified",
        before: { full_text: "3. Penalties are 0.5% per day." },
        after: { full_text: "3. Penalties are 1.0% per day." },
        needs_review: false,
        match_basis: "source_identifier",
        match_rationale: "source identifier 3 appears once in each revision",
      },
    ]);

    render(<ChangeDetailPage />);

    const change = within(await screen.findByTestId("change-0"));
    expect(change.queryByText("Needs review")).not.toBeInTheDocument();
    expect(screen.queryByTestId("change-detail-state")).not.toBeInTheDocument();
  });
});
