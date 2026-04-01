/**
 * Test Suite ID: TASK-021
 * Service Coverage: documents page loaders use fetch-safe API contracts.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { listProjectDocumentGroups } from "@/lib/api/services/documents";

describe("documents service contract alignment", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("aggregates project document groups through the frontend proxy", async () => {
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            items: [
              { id: "proj-1", name: "Hospital Central" },
              { id: "proj-2", name: "Port Expansion" },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            items: [{ id: "doc-1", filename: "Contract.pdf", status: "parsed" }],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ items: [] }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );

    await expect(listProjectDocumentGroups()).resolves.toEqual([
      {
        projectId: "proj-1",
        projectName: "Hospital Central",
        documents: [
          {
            id: "doc-1",
            filename: "Contract.pdf",
            status: "parsed",
            project_id: "proj-1",
          },
        ],
      },
    ]);

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/v1/projects", {});
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/projects/proj-1/documents",
      {},
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/v1/projects/proj-2/documents",
      {},
    );
  });
});
