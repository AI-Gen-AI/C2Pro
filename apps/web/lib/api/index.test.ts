/**
 * Test Suite ID: TS-FRT-COV-002
 * Backlog: TASK-FRT-132..135
 * Purpose: Coverage-improvement tests for frontend API highlight helpers.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Alert } from "@/types/project";

import { reviewResourceApiV1ApprovalsResourceTypeResourceIdPatch } from "@/lib/api/generated/approvals/approvals";
import { apiClient } from "./client";
import {
  bulkResolveAlerts,
  createHighlightsFromAlerts,
  createHighlightsFromEntities,
  deleteDocument,
  extractEvidenceLocation,
  getAlertWorkspaceSettings,
  getDocumentAlerts,
  getDocumentDownloadUrl,
  getDocumentEntities,
  getDocumentHistory,
  getDocumentRelationshipExplanation,
  getProjectDocuments,
  parseEvidenceLocation,
  resolveAlert,
  reviewAlert,
  reviewApprovalResource,
  saveAlertWorkspaceSettings,
  severityToColor,
  type ProcessedEntity,
  updateBOMItem,
  updateStakeholder,
  updateWBSItem,
} from "./index";

vi.mock("./client", () => ({
  apiClient: {
    defaults: {},
    delete: vi.fn(),
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
  handleAuthErrorStatus: vi.fn(),
}));

vi.mock("@/config/env", () => ({
  env: {
    API_BASE_URL: "https://api.example.com/api/v1",
  },
}));

vi.mock("@/lib/api/generated/approvals/approvals", () => ({
  reviewResourceApiV1ApprovalsResourceTypeResourceIdPatch: vi.fn(),
}));

const mockedApiClient = vi.mocked(apiClient);
const mockedReviewApproval = vi.mocked(
  reviewResourceApiV1ApprovalsResourceTypeResourceIdPatch,
);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("API highlight helper contracts", () => {
  it("maps alert severity to stable PDF highlight colors", () => {
    expect(severityToColor("critical")).toBe("red");
    expect(severityToColor("HIGH")).toBe("orange");
    expect(severityToColor("Medium")).toBe("yellow");
    expect(severityToColor("low")).toBe("blue");
  });

  it("extracts direct evidence locations before nested evidence JSON", () => {
    const alert = {
      id: "alert-1",
      severity: "high",
      title: "Scope gap",
      evidence_location: {
        bbox: [0.1, 0.2, 0.3, 0.4],
        page_number: 3,
        normalized: true,
      },
      evidence_json: {
        evidence_location: {
          bbox: [0.8, 0.8, 0.9, 0.9],
          page_number: 99,
        },
      },
    } as unknown as Alert;

    expect(extractEvidenceLocation(alert)).toEqual({
      bbox: [0.1, 0.2, 0.3, 0.4],
      page_number: 3,
      normalized: true,
    });
  });

  it("creates alert highlights and skips alerts without usable evidence", () => {
    const alerts = [
      {
        id: "alert-1",
        severity: "critical",
        title: "Missing schedule",
        evidence_json: {
          evidence_location: {
            bbox: [0.15, 0.25, 0.35, 0.45],
            page_number: 7,
          },
        },
      },
      {
        id: "alert-2",
        severity: "medium",
        title: "No evidence",
      },
    ] as unknown as Alert[];

    expect(createHighlightsFromAlerts(alerts)).toEqual([
      {
        id: "highlight-alert-1",
        entityId: "alert-1",
        page: 7,
        color: "red",
        label: "Missing schedule",
        rects: [
          {
            left: 0.15,
            top: 0.25,
            width: 0.35,
            height: 0.45,
            normalized: true,
          },
        ],
      },
    ]);
  });

  it("parses valid entity evidence locations and rejects malformed ones", () => {
    expect(
      parseEvidenceLocation({
        bbox: [1, 2, 3, 4],
        page_number: 4,
        normalized: false,
      }),
    ).toEqual({
      bbox: [1, 2, 3, 4],
      page_number: 4,
      normalized: false,
    });

    expect(parseEvidenceLocation(null)).toBeNull();
    expect(parseEvidenceLocation({ bbox: [1, 2, 3] })).toBeNull();
    expect(parseEvidenceLocation({ bbox: [1, "2", 3, 4] })).toBeNull();
  });

  it("creates entity highlights using confidence-based colors", () => {
    const entities: ProcessedEntity[] = [
      {
        id: "entity-1",
        type: "clause",
        text: "Retention clause",
        page: 5,
        confidence: 0.96,
        metadata: {
          evidence_location: {
            bbox: [0.2, 0.3, 0.4, 0.5],
            normalized: true,
          },
        },
      },
      {
        id: "entity-2",
        type: "stakeholder",
        text: "Missing evidence",
        page: 2,
        confidence: 0.5,
      },
    ];

    expect(createHighlightsFromEntities(entities)).toEqual([
      {
        id: "highlight-entity-1",
        entityId: "entity-1",
        page: 5,
        color: "green",
        label: "Retention clause",
        rects: [
          {
            left: 0.2,
            top: 0.3,
            width: 0.4,
            height: 0.5,
            normalized: true,
          },
        ],
      },
    ]);
  });
});

describe("API wrapper contracts", () => {
  it("fetches document-scoped alerts through the alerts endpoint", async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        items: [{ id: "alert-1" }],
        total: 1,
      },
    });

    await expect(getDocumentAlerts("doc-1")).resolves.toEqual([
      { id: "alert-1" },
    ]);
    expect(mockedApiClient.get).toHaveBeenCalledWith("/alerts", {
      params: { document_id: "doc-1" },
    });
  });

  it("fetches document entities and project documents from their canonical routes", async () => {
    mockedApiClient.get
      .mockResolvedValueOnce({ data: [{ id: "entity-1" }] })
      .mockResolvedValueOnce({
        data: {
          items: [{ id: "document-1" }],
          total_count: 1,
          skip: 0,
          limit: 20,
        },
      });

    await expect(getDocumentEntities("doc-1")).resolves.toEqual([
      { id: "entity-1" },
    ]);
    await expect(getProjectDocuments("project-1")).resolves.toEqual([
      { id: "document-1" },
    ]);
    expect(mockedApiClient.get).toHaveBeenNthCalledWith(
      1,
      "/documents/doc-1/entities",
    );
    expect(mockedApiClient.get).toHaveBeenNthCalledWith(
      2,
      "/projects/project-1/documents",
    );
  });

  it("builds direct document download URLs from the configured API base", () => {
    expect(getDocumentDownloadUrl("doc-1")).toBe(
      "https://api.example.com/api/v1/documents/doc-1/download",
    );
  });

  it("maps document history and relationship explanation response fields", async () => {
    mockedApiClient.get
      .mockResolvedValueOnce({
        data: {
          document_id: "doc-1",
          items: [
            {
              id: "history-1",
              title: "Uploaded",
              detail: "Document uploaded",
              occurred_at: "2026-05-06T00:00:00Z",
              source_type: "document",
              source_id: "doc-1",
            },
          ],
        },
      })
      .mockResolvedValueOnce({
        data: {
          document_id: "doc-1",
          summary: "Related clauses",
          strongest_cluster: "budget",
          review_priority: "high",
          latest_signal: "new-alert",
          citations: [
            {
              clause_id: "clause-1",
              clause_code: "C-1",
              label: "Budget",
              page: 2,
              reason: "Mismatch",
            },
          ],
        },
      });

    await expect(getDocumentHistory("doc-1")).resolves.toEqual([
      {
        id: "history-1",
        title: "Uploaded",
        detail: "Document uploaded",
        occurredAt: "2026-05-06T00:00:00Z",
        sourceType: "document",
        sourceId: "doc-1",
      },
    ]);
    await expect(getDocumentRelationshipExplanation("doc-1")).resolves.toEqual({
      summary: "Related clauses",
      strongestCluster: "budget",
      reviewPriority: "high",
      latestSignal: "new-alert",
      citations: [
        {
          clauseId: "clause-1",
          clauseCode: "C-1",
          label: "Budget",
          page: 2,
          reason: "Mismatch",
        },
      ],
    });
  });

  it("persists alert review, resolution, workspace settings, and bulk resolution payloads", async () => {
    mockedApiClient.post
      .mockResolvedValueOnce({ data: { id: "alert-1", status: "approved" } })
      .mockResolvedValueOnce({ data: { id: "alert-1", status: "resolved" } })
      .mockResolvedValueOnce({
        data: {
          processed_count: 2,
          status: "resolved",
          alert_ids: ["a1", "a2"],
        },
      });
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        rules: [{ id: "rule-1" }],
        subscriptions: null,
      },
    });
    mockedApiClient.put.mockResolvedValueOnce({
      data: {
        rules: [],
        subscriptions: { emailEnabled: false },
      },
    });

    await expect(reviewAlert("alert-1", "approve", "ok")).resolves.toEqual({
      id: "alert-1",
      status: "approved",
    });
    await expect(
      resolveAlert("alert-1", "Fixed", "user-1", "Bad source"),
    ).resolves.toEqual({ id: "alert-1", status: "resolved" });
    await expect(getAlertWorkspaceSettings()).resolves.toEqual({
      rules: [{ id: "rule-1" }],
      subscriptions: null,
    });
    await expect(
      saveAlertWorkspaceSettings({
        rules: [],
        subscriptions: null,
      }),
    ).resolves.toEqual({
      rules: [],
      subscriptions: { emailEnabled: false },
    });
    await expect(
      bulkResolveAlerts({
        alertIds: ["a1", "a2"],
        resolution: "Fixed",
        rootCause: "Bad source",
      }),
    ).resolves.toEqual({
      processedCount: 2,
      status: "resolved",
      alertIds: ["a1", "a2"],
    });

    expect(mockedApiClient.post).toHaveBeenNthCalledWith(
      1,
      "/alerts/alert-1/review",
      { decision: "approve", comment: "ok" },
    );
    expect(mockedApiClient.post).toHaveBeenNthCalledWith(
      2,
      "/alerts/alert-1/resolve",
      {
        resolution: "Fixed",
        resolved_by: "user-1",
        root_cause: "Bad source",
      },
    );
    expect(mockedApiClient.post).toHaveBeenNthCalledWith(
      3,
      "/alerts/bulk-resolve",
      {
        alert_ids: ["a1", "a2"],
        resolution: "Fixed",
        root_cause: "Bad source",
      },
    );
  });

  it("delegates approval resource reviews and CRUD helpers to generated/API clients", async () => {
    mockedReviewApproval.mockResolvedValueOnce({
      resource_id: "alert-1",
      status: "approved",
    });
    mockedApiClient.delete.mockResolvedValueOnce({ data: undefined });
    mockedApiClient.patch.mockResolvedValueOnce({ data: { id: "stakeholder-1" } });
    mockedApiClient.put
      .mockResolvedValueOnce({ data: { id: "wbs-1" } })
      .mockResolvedValueOnce({ data: { id: "bom-1" } });

    await expect(
      reviewApprovalResource("alert", "alert-1", "approved", {
        correctionData: { field: "value" },
        feedbackComment: "approved",
      }),
    ).resolves.toEqual({ resource_id: "alert-1", status: "approved" });
    await expect(deleteDocument("doc-1")).resolves.toBeUndefined();
    await expect(
      updateStakeholder("stakeholder-1", { name: "ACME" }),
    ).resolves.toEqual({ id: "stakeholder-1" });
    await expect(updateWBSItem("wbs-1", { status: "done" })).resolves.toEqual({
      id: "wbs-1",
    });
    await expect(updateBOMItem("bom-1", { quantity: 2 })).resolves.toEqual({
      id: "bom-1",
    });

    expect(mockedReviewApproval).toHaveBeenCalledWith("alert", "alert-1", {
      status: "approved",
      correction_data: { field: "value" },
      feedback_comment: "approved",
    });
    expect(mockedApiClient.delete).toHaveBeenCalledWith("/documents/doc-1");
    expect(mockedApiClient.patch).toHaveBeenCalledWith(
      "/stakeholders/stakeholder-1",
      { name: "ACME" },
    );
    expect(mockedApiClient.put).toHaveBeenNthCalledWith(
      1,
      "/procurement/wbs/wbs-1",
      { status: "done" },
    );
    expect(mockedApiClient.put).toHaveBeenNthCalledWith(
      2,
      "/procurement/bom/bom-1",
      { quantity: 2 },
    );
  });
});
