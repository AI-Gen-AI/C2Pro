/**
 * Test Suite ID: TASK-FRT-188
 * Audit Report export composition coverage.
 */
import { describe, expect, it } from "vitest";
import type { AlertResponse, ReviewItemResponse } from "@/lib/api/generated/models";
import type { DashboardSummary } from "@/lib/api/contracts";
import type { DocumentInfo } from "@/types/document";
import { composeAuditReport, groupReportAlerts } from "./report-data";

const dashboard: DashboardSummary = {
  project_id: "proj-188",
  tenant_id: "tenant-188",
  coherence_score: null,
  global_score: null,
  sub_scores: {},
  weights_used: {},
  alert_count: 2,
  document_count: 2,
  methodology_version: "v2",
  score_version: "coherence-v2",
  score_reason: "insufficient_evidence",
  score_missing_dimensions: ["budget"],
  last_updated: "2026-07-10T10:00:00Z",
  categories_v2: {
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
        recommendation: "Upload the approved BOQ.",
      },
    ],
  },
};

const alerts: AlertResponse[] = [
  {
    id: "alert-open",
    project_id: "proj-188",
    tenant_id: "tenant-188",
    rule_code: "DET-BUD-SUM",
    category: "BUDGET",
    severity: "high",
    message: "Budget mismatch requires review.",
    status: "open",
    affected_entities: {
      document_name: "Budget.xlsx",
      page: 12,
      clause: "BOQ-4.2",
    },
    reviewed_by: null,
    reviewed_at: null,
    created_at: "2026-07-10T09:00:00Z",
  },
  {
    id: "alert-approved",
    project_id: "proj-188",
    tenant_id: "tenant-188",
    rule_code: "DET-SCH-001",
    category: "TIME",
    severity: "medium",
    message: "Schedule finding accepted.",
    status: "approved",
    reviewed_by: "jane@acme.com",
    reviewed_at: "2026-07-10T11:00:00Z",
    created_at: "2026-07-10T08:00:00Z",
  },
];

const documents: DocumentInfo[] = [
  {
    id: "doc-budget",
    name: "Budget.xlsx",
    type: "budget",
    extension: "xlsx",
    url: "",
    uploadedAt: new Date("2026-07-09T12:00:00Z"),
    status: "parsed",
  },
];

describe("audit report composition", () => {
  it("keeps null scores pending and groups alerts without fabricating counts", () => {
    const payload = composeAuditReport({
      project: {
        id: "proj-188",
        name: "Hospital North",
        code: "HN-01",
        status: "active",
      },
      dashboard,
      alerts,
      documents,
      reviewItems: undefined,
      generatedAt: "2026-07-11T10:00:00Z",
    });

    expect(payload.score.value).toBeNull();
    expect(payload.score.label).toBe("Pending evidence");
    expect(payload.score.scoreVersion).toBe("coherence-v2");
    expect(payload.alertGroups.open).toHaveLength(1);
    expect(payload.alertGroups.approved).toHaveLength(1);
    expect(payload.alertGroups.rejected).toHaveLength(0);
    expect(payload.alertGroups.open[0]?.evidenceReferences).toEqual([
      "Budget.xlsx",
      "Page 12",
      "Clause BOQ-4.2",
    ]);
    expect(payload.reviewDecisions).toEqual([]);
    expect(payload.reviewDecisionSource).toBe("not_project_scoped");
  });

  it("uses project-scoped HITL decisions only when supplied by a project-scoped source", () => {
    const reviewItems = [
      {
        item_id: "hitl-1",
        item_type: "alert",
        current_status: "APPROVED",
        confidence: 0.9,
        impact_level: "MEDIUM",
        approved_by: "reviewer@acme.com",
        approved_at: "2026-07-10T12:00:00Z",
        sla_due_date: "2026-07-12T00:00:00Z",
        created_at: "2026-07-10T09:00:00Z",
        item_data: { summary: "Accepted budget exception" },
      },
    ] satisfies ReviewItemResponse[];

    const payload = composeAuditReport({
      project: {
        id: "proj-188",
        name: "Hospital North",
        status: "active",
      },
      dashboard,
      alerts: [],
      documents: [],
      reviewItems,
      reviewItemsProjectScoped: true,
      generatedAt: "2026-07-11T10:00:00Z",
    });

    expect(payload.reviewDecisionSource).toBe("project_scoped");
    expect(payload.reviewDecisions).toEqual([
      expect.objectContaining({
        id: "hitl-1",
        status: "APPROVED",
        reviewer: "reviewer@acme.com",
        summary: "Accepted budget exception",
      }),
    ]);
  });

  it("classifies rejected and closed alerts into the report status buckets", () => {
    expect(
      groupReportAlerts([
        { ...alerts[0], id: "r", status: "rejected" },
        { ...alerts[0], id: "c", status: "closed" },
      ]),
    ).toMatchObject({
      open: [{ id: "c" }],
      approved: [],
      rejected: [{ id: "r" }],
    });
  });
});
