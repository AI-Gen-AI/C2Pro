/**
 * TS-TASK-013-PROJECT-CRUD-003: dashboard service normalization coverage for project list and summary payloads.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const { listProjectsApiMock, getDashboardSummaryApiMock } = vi.hoisted(() => ({
  listProjectsApiMock: vi.fn(),
  getDashboardSummaryApiMock: vi.fn(),
}));

vi.mock("@/lib/api/generated/projects/projects", () => ({
  listProjectsApiV1ProjectsGet: listProjectsApiMock,
}));

vi.mock("@/lib/api/generated/coherence-dashboard/coherence-dashboard", () => ({
  getCoherenceDashboardApiCoherenceDashboardProjectIdGet:
    getDashboardSummaryApiMock,
}));

import { getDashboardSummary, listProjects } from "@/lib/api/services/dashboard";

describe("dashboard service contract alignment", () => {
  beforeEach(() => {
    listProjectsApiMock.mockReset();
    getDashboardSummaryApiMock.mockReset();
  });

  it("unwraps project list items and falls back to an empty list", async () => {
    listProjectsApiMock.mockResolvedValueOnce({
      items: [
        { id: "proj-1", name: "Project One" },
        { id: "proj-2", name: "Project Two" },
      ],
    });

    await expect(listProjects()).resolves.toEqual([
      { id: "proj-1", name: "Project One" },
      { id: "proj-2", name: "Project Two" },
    ]);

    listProjectsApiMock.mockResolvedValueOnce({});
    await expect(listProjects()).resolves.toEqual([]);
  });

  it("normalizes dashboard summary fallbacks and numeric maps", async () => {
    getDashboardSummaryApiMock.mockResolvedValueOnce({
      global_score: "92",
      sub_scores: { scope: "88", legal: 94 },
      weights_used: null,
      alert_count: undefined,
      document_count: "3",
      methodology_version: undefined,
      last_updated: new Date("2026-03-29T00:00:00.000Z"),
    });

    await expect(getDashboardSummary("proj-1")).resolves.toEqual({
      project_id: "proj-1",
      tenant_id: "",
      coherence_score: 92,
      global_score: 92,
      sub_scores: { scope: 88, legal: 94 },
      weights_used: {},
      alert_count: 0,
      document_count: 3,
      methodology_version: "unknown",
      last_updated: null,
    });
  });
});
