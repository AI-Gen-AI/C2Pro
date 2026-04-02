/**
 * Test Suite ID: TASK-1467
 * Coverage: project header resolves live project names instead of route ids
 */
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { ProjectHeaderCard } from "./ProjectHeaderCard";

const useProjectMock = vi.fn();

vi.mock("@/hooks/useProject", () => ({
  useProject: (...args: unknown[]) => useProjectMock(...args),
}));

vi.mock("./ProjectTabs", () => ({
  ProjectTabs: ({ projectId }: { projectId: string }) => (
    <div>Tabs for {projectId}</div>
  ),
}));

describe("ProjectHeaderCard", () => {
  it("renders the fetched project name while preserving tab routing by id", () => {
    useProjectMock.mockReturnValue({
      data: {
        id: "proj_real_001",
        name: "Atlas Ridge",
      },
    });

    renderWithProviders(<ProjectHeaderCard projectId="proj_real_001" />);

    expect(screen.getByText("Atlas Ridge")).toBeInTheDocument();
    expect(screen.queryByText("proj_real_001")).not.toBeInTheDocument();
    expect(screen.getByText("Tabs for proj_real_001")).toBeInTheDocument();
  });
});
