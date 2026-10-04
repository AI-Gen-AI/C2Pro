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

function detail(changes: Array<Record<string, unknown>>, state = "ready", extra: Record<string, unknown> = {}) {
  apiClientGetMock.mockResolvedValue({
    data: {
      state,
      change_cause: "BUSINESS_STATE_CHANGED",
      confidence: state === "ready" ? 1 : 0.82,
      evidence_refs: [],
      changes,
      ...extra,
    },
  });
}

const modified = {
  change_type: "modified",
  anchor: "3",
  semantic_summary: "clause 3 text modified",
  before: { full_text: "3. Penalties are 0.5% per day." },
  after: { full_text: "3. Penalties are 1.0% per day." },
  needs_review: false,
  match_basis: "source_identifier",
};

function impact(assessment: Record<string, unknown>) {
  return {
    change_index: 0,
    change_type: "modified",
    source: { entity_type: "clause", entity_id: "c-1", document_id: "doc_1", revision_id: "rev_1", evidence: [] },
    assessment,
  };
}

function target(entity_type: string, potentially_stale: boolean | null = null) {
  return { entity_type, entity_id: `${entity_type}-1`, label: entity_type, status: null, potentially_stale };
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

  it("labels impact status and counts potentially stale alerts without changing them", async () => {
    detail([modified], "ready", {
      impacts: [
        impact({
          status: "CONFIRMED",
          confidence: 1,
          reason: null,
          items: [
            { target: target("alert", true), relationship: { kind: "direct", via: "alerts.source_clause_id" }, status: "CONFIRMED", confidence: 1 },
            { target: target("wbs_node"), relationship: { kind: "indirect", via: "raci" }, status: "CANDIDATE", confidence: null },
          ],
        }),
      ],
    });

    render(<ChangeDetailPage />);

    const change = within(await screen.findByTestId("change-0"));
    expect(change.getByTestId("change-impact-0")).toHaveTextContent("Confirmed impact");
    expect(change.getByTestId("change-impact-0")).toHaveTextContent("2 linked entities");
    expect(change.getByTestId("change-impact-0")).toHaveTextContent("1 alert may be stale");
  });

  it("states an unknown impact with its reason and no fabricated targets", async () => {
    detail([modified], "ready", {
      impacts: [impact({ status: "UNKNOWN", confidence: null, reason: "no persisted relationship to any project entity", items: [] })],
    });

    render(<ChangeDetailPage />);

    const panel = within(await screen.findByTestId("change-impact-0"));
    expect(panel.getByText("Impact unknown")).toBeInTheDocument();
    expect(panel.getByText(/no persisted relationship/)).toBeInTheDocument();
    expect(panel.queryByText(/linked entit/)).not.toBeInTheDocument();
  });

  it("labels the revision projection as provisional and never as the trusted score", async () => {
    detail([modified], "ready", {
      projection: {
        basis: "projected",
        status: "provisional",
        trusted_score: 70,
        projected_score: 64,
        projected_delta: -6,
        qualification: "provisional_unverified_temporal_identity",
        confidence: null,
      },
    });

    render(<ChangeDetailPage />);

    const projection = await screen.findByTestId("change-detail-projection");
    expect(projection).toHaveTextContent("Projected Coherence (provisional)");
    expect(projection).toHaveTextContent("64");
    expect(projection).toHaveTextContent("unverified temporal identity");
  });

  it("explains a legacy-matcher comparison", async () => {
    detail([{ ...modified, match_basis: undefined }], "needs_review", {
      legacy_matcher: true,
      matcher_status: "legacy",
      qualification_reason: "Compared by an older matcher (p0c-structural-l1-v1).",
    });

    render(<ChangeDetailPage />);

    expect(await screen.findByTestId("change-detail-qualification")).toHaveTextContent(/older matcher/i);
  });
});
