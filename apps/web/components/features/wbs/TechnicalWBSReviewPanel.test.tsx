/**
 * ACC-01 S7 · Technical→WBS human review UI anti-authority regression.
 * Test Suite ID: TS-ACC01-S7-TECH-UI-001
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, renderWithProviders, screen, waitFor } from "@/src/tests/test-utils";
import type { ProjectWBSAuthority } from "@/lib/api/generated/models";
import { eligibleTechnicalClauses, TechnicalWBSReviewPanel } from "./TechnicalWBSReviewPanel";

const { mocks } = vi.hoisted(() => ({
  mocks: {
    post: vi.fn(),
    documents: [
      {
        id: "doc-technical",
        name: "technical.docx",
        type: "specification",
        extension: "docx",
      },
    ],
    revisions: [] as Array<Record<string, unknown>>,
    detail: null as Record<string, unknown> | null,
    baseline: null as Record<string, unknown> | null,
  },
}));

vi.mock("@/hooks/useProjectDocuments", () => ({
  useProjectDocuments: () => ({
    documents: mocks.documents,
    loading: false,
    error: null,
  }),
}));
vi.mock("@/lib/api/generated/documents/documents", () => ({
  useListDocumentRevisionStatusesEndpointApiV1DocumentsDocumentIdRevisionsGet: () => ({
    data: mocks.revisions,
    isLoading: false,
    isError: false,
  }),
  useGetDocumentEndpointApiV1DocumentsDocumentIdGet: () => ({
    data: mocks.detail,
    isLoading: false,
    isError: false,
  }),
}));
vi.mock("@/lib/api/generated/wbs-governance/wbs-governance", () => ({
  useGetWbsBaselineApiV1ProjectsProjectIdWbsGovernanceBaselinesBaselineNoGet: () => ({
    data: mocks.baseline,
    isLoading: false,
    isError: false,
  }),
}));
vi.mock("@/lib/api/client", () => ({
  apiClient: { post: mocks.post },
  normalizeGeneratedApiUrl: (url: string) => url.replace(/^\/api\/v1/, ""),
}));

const authority: ProjectWBSAuthority = {
  state: "APPROVED_BASELINE",
  display_state: "APPROVED_BASELINE",
  approved: true,
  scope_label: "Approved WBS Baseline #2",
  baseline_id: "baseline-2",
  baseline_no: 2,
  draft_exists: false,
  dates_schedule_authority: false,
  budget_cost_authority: false,
};

const SHA = "a".repeat(64);
const REV = "revision-1";
const CLAUSE = {
  id: "clause-1",
  clause_code: "4.1",
  title: "Compressive strength",
  full_text: "Section 4.1: concrete shall exceed 35 MPa.",
  revision_id: REV,
  text_start_offset: 0,
  text_end_offset: 43,
  extraction_model: "deterministic-technical-section-v1",
  extracted_entities: { technical_requirement: { source_section: "4.1" } },
};

function validFixtures() {
  mocks.revisions = [{
    status: "available", revision_id: REV, trust_state: "trusted",
    is_current: true, current_basis: "trusted",
  }];
  mocks.detail = {
    id: "doc-technical", project_id: "project-1",
    document_type: "technical_spec", revision_id: REV,
    file_hash: SHA, clauses: [CLAUSE],
  };
  mocks.baseline = {
    id: "baseline-2", baseline_no: 2, digest_verified: true,
    self_approved: false,
    nodes: [{ node_id: "node-11", code: "1.1", name: "Concrete" }],
  };
}

describe("eligibleTechnicalClauses", () => {
  it("requires revision-pinned deterministic literal source and valid offsets", () => {
    expect(eligibleTechnicalClauses([CLAUSE], REV)).toEqual([CLAUSE]);
    expect(eligibleTechnicalClauses([CLAUSE], "older")).toEqual([]);
    expect(eligibleTechnicalClauses([{ ...CLAUSE, text_end_offset: 0 }], REV)).toEqual([]);
    expect(eligibleTechnicalClauses([{ ...CLAUSE, extraction_model: "AI" }], REV)).toEqual([]);
    expect(eligibleTechnicalClauses([{ ...CLAUSE, extracted_entities: {} }], REV)).toEqual([]);
  });
});

describe("TechnicalWBSReviewPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.revisions = [];
    mocks.detail = null;
    mocks.baseline = null;
    vi.stubGlobal("crypto", { randomUUID: () => "idempotency-key-00000001" });
  });

  it("never offers an actionable review without an approved baseline", () => {
    validFixtures();
    renderWithProviders(
      <TechnicalWBSReviewPanel
        projectId="project-1"
        authority={{ ...authority, approved: false, baseline_id: null }}
      />,
    );
    expect(screen.getByTestId("technical-wbs-no-baseline")).toBeInTheDocument();
    expect(screen.getByTestId("technical-wbs-review-submit")).toBeDisabled();
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it("does not accept PROPOSED or ambiguous trusted-current revisions", () => {
    validFixtures();
    mocks.revisions = [{ status: "available", revision_id: REV, trust_state: "proposed", is_current: true }];
    renderWithProviders(<TechnicalWBSReviewPanel projectId="project-1" authority={authority} />);
    fireEvent.change(screen.getByLabelText("Technical specification"), { target: { value: "doc-technical" } });
    expect(screen.getByTestId("technical-wbs-untrusted")).toBeInTheDocument();
    expect(screen.getByTestId("technical-wbs-review-submit")).toBeDisabled();
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it("POSTs exact revision, baseline, clause, actor-free payload and audit-only receipt", async () => {
    validFixtures();
    mocks.post.mockResolvedValue({
      status: 201,
      data: {
        event_id: "event-1",
        decision: "CONFIRMED_FOR_REVIEW",
        replayed: false,
        authority: "AUDIT_ONLY_NOT_CANONICAL_LINK",
        approved_canonical_link: false,
        technical_assessment: "NOT_ASSESSED",
      },
    });
    renderWithProviders(<TechnicalWBSReviewPanel projectId="project-1" authority={authority} />);
    fireEvent.change(screen.getByLabelText("Technical specification"), { target: { value: "doc-technical" } });
    fireEvent.change(screen.getByLabelText("Source requirement"), { target: { value: "clause-1" } });
    fireEvent.change(screen.getByLabelText("Approved WBS node"), { target: { value: "node-11" } });
    expect(screen.getByTestId("technical-wbs-review-submit")).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reviewer reason"), {
      target: { value: "Verified against source and approved scope." },
    });
    fireEvent.click(screen.getByTestId("technical-wbs-review-submit"));
    await waitFor(() => expect(mocks.post).toHaveBeenCalledTimes(1));
    expect(mocks.post).toHaveBeenCalledWith(
      "/projects/project-1/technical-wbs/reviews",
      {
        clause_id: "clause-1",
        expected_revision_id: REV,
        expected_blob_hash: SHA,
        expected_wbs_baseline_id: "baseline-2",
        proposed_wbs_node_id: "node-11",
        decision: "CONFIRMED_FOR_REVIEW",
        idempotency_key: "idempotency-key-00000001",
        reason: "Verified against source and approved scope.",
      },
    );
    expect(screen.getByTestId("technical-wbs-review-receipt")).toHaveTextContent(
      "Not a canonical link; technical compliance not assessed.",
    );
  });

  it("refuses a response that pretends the audit created canonical authority", async () => {
    validFixtures();
    mocks.post.mockResolvedValue({
      status: 201,
      data: {
        event_id: "event-2", authority: "CANONICAL_LINK_APPROVED",
        approved_canonical_link: true,
      },
    });
    renderWithProviders(<TechnicalWBSReviewPanel projectId="project-1" authority={authority} />);
    fireEvent.change(screen.getByLabelText("Technical specification"), { target: { value: "doc-technical" } });
    fireEvent.change(screen.getByLabelText("Source requirement"), { target: { value: "clause-1" } });
    fireEvent.change(screen.getByLabelText("Approved WBS node"), { target: { value: "node-11" } });
    fireEvent.change(screen.getByLabelText("Reviewer reason"), { target: { value: "Review carefully" } });
    fireEvent.click(screen.getByTestId("technical-wbs-review-submit"));
    await waitFor(() => expect(screen.getByTestId("technical-wbs-review-error")).toBeInTheDocument());
    expect(screen.queryByTestId("technical-wbs-review-receipt")).not.toBeInTheDocument();
  });
});
