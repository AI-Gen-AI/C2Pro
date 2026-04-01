/**
 * Test Suite ID: TASK-021
 * Service Coverage: dashboard data loaders use fetch-safe API contracts.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getDashboardSummary, listProjects } from "@/lib/api/services/dashboard";

describe("dashboard service contract alignment", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("loads project list items from the frontend proxy and falls back to an empty list", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          items: [
            { id: "proj-1", name: "Project One" },
            { id: "proj-2", name: "Project Two" },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(listProjects()).resolves.toEqual([
      { id: "proj-1", name: "Project One" },
      { id: "proj-2", name: "Project Two" },
    ]);
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/projects", {});

    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({}), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(listProjects()).resolves.toEqual([]);
  });

  it("normalizes dashboard summary fallbacks and numeric maps", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          global_score: "92",
          sub_scores: { scope: "88", legal: 94 },
          weights_used: null,
          alert_count: undefined,
          document_count: "3",
          methodology_version: undefined,
          last_updated: "2026-03-29T00:00:00.000Z",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

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
      last_updated: "2026-03-29T00:00:00.000Z",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/coherence/dashboard/proj-1",
      {},
    );
  });

  it("uses backend URLs when server-side loading is requested", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await listProjects({ server: true });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/projects",
      {},
    );
  });
});
