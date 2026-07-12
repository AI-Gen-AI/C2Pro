/**
 * Test Suite ID: TASK-FRT-188
 * Audit Report export view coverage.
 */
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import type { AuditReportPayload } from "./report-data";
import { AuditReportView } from "./AuditReportView";

const payload: AuditReportPayload = {
  generatedAt: "2026-07-11T10:00:00Z",
  project: {
    id: "proj-188",
    name: "Hospital North",
    code: "HN-01",
    status: "active",
  },
  score: {
    value: null,
    label: "Pending evidence",
    scoreVersion: "coherence-v2",
    reason: "insufficient_evidence",
  },
  categoriesV2: {
    project_id: "proj-188",
    version: "coherence-v2",
    generated_at: "2026-07-10T10:00:00Z",
    global: {
      coherence_score: null,
      completeness_score: 0.4,
      technical_reliability_index: 0.8,
      status: "partial",
      score_reason: "insufficient_evidence",
      active_weight: 0.6,
    },
    categories: [
      {
        category: "BUDGET",
        status: "insufficient_evidence",
        coherence_score: null,
        evidence_coverage: 0.2,
        technical_reliability: 0.9,
        evidence_freshness: 0.8,
        applicability_reason: null,
        score_explanation: null,
        missing_evidence: ["Approved BOQ"],
        detected_conflicts: [],
      },
    ],
  },
  alertGroups: {
    open: [
      {
        id: "alert-open",
        category: "BUDGET",
        severity: "high",
        status: "open",
        message: "Budget mismatch requires review.",
        evidenceReferences: ["Budget.xlsx", "Page 12"],
        createdAt: "2026-07-10T09:00:00Z",
      },
    ],
    approved: [],
    rejected: [],
  },
  documents: [
    {
      id: "doc-budget",
      name: "Budget.xlsx",
      type: "budget",
      uploadedAt: "2026-07-09T12:00:00.000Z",
      status: "parsed",
    },
  ],
  reviewDecisions: [],
  reviewDecisionSource: "not_project_scoped",
};

describe("AuditReportView", () => {
  it("renders honest report sections and triggers browser print export", async () => {
    const user = userEvent.setup();
    const onDownloadJson = vi.fn();
    const onPrint = vi.fn();

    renderWithProviders(
      <AuditReportView
        payload={payload}
        includeOpenFindings
        includeRejectedFindings={false}
        onIncludeOpenFindingsChange={() => undefined}
        onIncludeRejectedFindingsChange={() => undefined}
        onDownloadJson={onDownloadJson}
        onPrint={onPrint}
      />,
    );

    expect(screen.getByRole("heading", { name: /audit report/i })).toBeInTheDocument();
    expect(screen.getByText("Hospital North")).toBeInTheDocument();
    expect(screen.getByText("Pending evidence")).toBeInTheDocument();
    expect(screen.getByText("coherence-v2")).toBeInTheDocument();
    expect(screen.getByText("Budget mismatch requires review.")).toBeInTheDocument();
    expect(screen.getByText("Budget.xlsx")).toBeInTheDocument();
    expect(screen.getByText(/HITL decisions require a project-scoped queue/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /export report/i }));
    expect(onPrint).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: /download json/i }));
    expect(onDownloadJson).toHaveBeenCalledTimes(1);
  });

  it("omits open and rejected findings when the controls exclude them", () => {
    renderWithProviders(
      <AuditReportView
        payload={{
          ...payload,
          alertGroups: {
            open: payload.alertGroups.open,
            approved: [],
            rejected: [
              {
                id: "alert-rejected",
                category: "LEGAL",
                severity: "low",
                status: "rejected",
                message: "Rejected legal finding.",
                evidenceReferences: [],
                createdAt: "2026-07-10T09:00:00Z",
              },
            ],
          },
        }}
        includeOpenFindings={false}
        includeRejectedFindings={false}
        onIncludeOpenFindingsChange={() => undefined}
        onIncludeRejectedFindingsChange={() => undefined}
        onDownloadJson={() => undefined}
        onPrint={() => undefined}
      />,
    );

    expect(screen.queryByText("Budget mismatch requires review.")).not.toBeInTheDocument();
    expect(screen.queryByText("Rejected legal finding.")).not.toBeInTheDocument();
    expect(screen.getByText(/No findings selected for this report/i)).toBeInTheDocument();
  });
});
