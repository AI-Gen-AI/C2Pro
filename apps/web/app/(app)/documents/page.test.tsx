/**
 * Test Suite ID: TASK-1347
 * Route Coverage: Top-level documents page uses generated backend clients
 */
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { describe, expect, it, vi, beforeEach } from "vitest";
import DocumentsPage from "./page";

const listProjectsMock = vi.fn();
const listDocumentsForProjectMock = vi.fn();

vi.mock("@/lib/api/generated/projects/projects", () => ({
  listProjectsApiV1ProjectsGet: (...args: unknown[]) => listProjectsMock(...args),
}));

vi.mock("@/lib/api/generated/documents/documents", () => ({
  listDocumentsForProjectApiV1ProjectsProjectIdDocumentsGet: (...args: unknown[]) =>
    listDocumentsForProjectMock(...args),
}));

vi.mock("@/components/features/documents/DocumentsListClient", () => ({
  DocumentsListClient: ({
    groups,
  }: {
    groups: Array<{ projectName: string; documents: Array<{ id: string }> }>;
  }) => <div>Documents groups: {groups.map((group) => group.projectName).join(", ")}</div>,
}));

describe("DocumentsPage backend aggregation", () => {
  beforeEach(() => {
    listProjectsMock.mockReset();
    listDocumentsForProjectMock.mockReset();
  });

  it("aggregates project document groups through generated backend clients", async () => {
    listProjectsMock.mockResolvedValue({
      items: [
        { id: "proj-1", name: "Hospital Central" },
        { id: "proj-2", name: "Port Expansion" },
      ],
      total: 2,
    });

    listDocumentsForProjectMock.mockImplementation((projectId: string) =>
      Promise.resolve({
        items:
          projectId === "proj-1"
            ? [
                {
                  id: "doc-1",
                  filename: "Contract.pdf",
                  status: "parsed",
                },
              ]
            : [],
        total_count: projectId === "proj-1" ? 1 : 0,
        skip: 0,
        limit: 50,
      }),
    );

    renderWithProviders(await DocumentsPage());

    expect(listProjectsMock).toHaveBeenCalledTimes(1);
    expect(listDocumentsForProjectMock).toHaveBeenCalledWith("proj-1");
    expect(listDocumentsForProjectMock).toHaveBeenCalledWith("proj-2");
    expect(screen.getByText(/documents groups: hospital central/i)).toBeInTheDocument();
  });

  it("shows the backend error banner when project aggregation fails", async () => {
    listProjectsMock.mockRejectedValue(new Error("documents offline"));

    renderWithProviders(await DocumentsPage());

    expect(screen.getByText(/documents offline/i)).toBeInTheDocument();
    expect(screen.getByText(/verify backend api is running at/i)).toBeInTheDocument();
  });
});
