/**
 * Test Suite ID: TASK-021
 * Route Coverage: top-level documents page uses fetch-safe service loaders
 */
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { describe, expect, it, vi, beforeEach } from "vitest";
import DocumentsPage from "./page";

const listProjectDocumentGroupsMock = vi.fn();

vi.mock("@/lib/api/services/documents", () => ({
  listProjectDocumentGroups: (...args: unknown[]) =>
    listProjectDocumentGroupsMock(...args),
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
    listProjectDocumentGroupsMock.mockReset();
  });

  it("aggregates project document groups through the documents service", async () => {
    listProjectDocumentGroupsMock.mockResolvedValue([
      {
        projectId: "proj-1",
        projectName: "Hospital Central",
        documents: [{ id: "doc-1" }],
      },
    ]);

    renderWithProviders(await DocumentsPage());

    expect(listProjectDocumentGroupsMock).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/documents groups: hospital central/i)).toBeInTheDocument();
  });

  it("shows the backend error banner when project aggregation fails", async () => {
    listProjectDocumentGroupsMock.mockRejectedValue(new Error("documents offline"));

    renderWithProviders(await DocumentsPage());

    expect(screen.getByText(/documents offline/i)).toBeInTheDocument();
    expect(screen.getByText(/verify backend api is running at/i)).toBeInTheDocument();
  });
});
