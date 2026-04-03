/**
 * Test Suite ID: TASK-1485
 * Route Coverage: nested project stakeholders route uses real project context
 */
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { describe, expect, it, vi } from "vitest";
import ProjectStakeholdersPage from "./page";

const useParamsMock = vi.fn();
const useProjectMock = vi.fn();
const stakeholderMatrixMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => useParamsMock(),
}));

vi.mock("@/hooks/useProject", () => ({
  useProject: (...args: unknown[]) => useProjectMock(...args),
}));

vi.mock("@/components/stakeholders/StakeholderMatrix", () => ({
  StakeholderMatrix: ({ projectId }: { projectId?: string }) => {
    stakeholderMatrixMock(projectId);
    return <div>Stakeholder matrix for {projectId ?? "none"}</div>;
  },
}));

describe("ProjectStakeholdersPage", () => {
  it("uses the route project id and backend project name", () => {
    useParamsMock.mockReturnValue({ id: "proj-real-42" });
    useProjectMock.mockReturnValue({
      data: {
        id: "proj-real-42",
        name: "Atlas Ridge",
      },
    });

    renderWithProviders(<ProjectStakeholdersPage />);

    expect(screen.getByText("Stakeholders")).toBeInTheDocument();
    expect(
      screen.getByText(/live stakeholder matrix for atlas ridge/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/live stakeholder matrix for proj-real-42/i),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/stakeholder matrix for proj-real-42/i)).toBeInTheDocument();
    expect(stakeholderMatrixMock).toHaveBeenLastCalledWith("proj-real-42");
  });
});
