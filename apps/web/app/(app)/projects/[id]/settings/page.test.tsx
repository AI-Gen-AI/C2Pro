/**
 * Test Suite ID: TASK-1486
 * Route Coverage: nested project settings route uses backend project update flow
 */
import { fireEvent, renderWithProviders, screen, waitFor } from "@/src/tests/test-utils";
import { describe, expect, it, vi } from "vitest";
import ProjectSettingsPage from "./page";

const useParamsMock = vi.fn();
const useProjectMock = vi.fn();
const updateProjectMutateAsyncMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => useParamsMock(),
}));

vi.mock("@/hooks/useProject", () => ({
  useProject: (...args: unknown[]) => useProjectMock(...args),
}));

vi.mock("@/hooks/useUpdateProject", () => ({
  useUpdateProject: () => ({
    mutateAsync: (...args: unknown[]) => updateProjectMutateAsyncMock(...args),
    isPending: false,
    error: null,
  }),
}));

describe("ProjectSettingsPage", () => {
  it("loads backend project fields and saves edits through the project update mutation", async () => {
    useParamsMock.mockReturnValue({ id: "proj-real-77" });
    useProjectMock.mockReturnValue({
      data: {
        id: "proj-real-77",
        name: "Atlas Ridge",
        code: "AR-77",
        description: "Phase 1 EPC project",
        project_type: "epc",
        status: "active",
        estimated_budget: 1250000,
        currency: "EUR",
      },
    });
    updateProjectMutateAsyncMock.mockResolvedValue({
      id: "proj-real-77",
      name: "Atlas Ridge Updated",
    });

    renderWithProviders(<ProjectSettingsPage />);

    expect(screen.getByText("Project Settings")).toBeInTheDocument();
    expect(screen.getByText(/configure atlas ridge/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue("Atlas Ridge")).toBeInTheDocument();
    expect(screen.getByDisplayValue("AR-77")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Phase 1 EPC project")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/project name/i), {
      target: { value: "Atlas Ridge Updated" },
    });
    fireEvent.change(screen.getByLabelText(/estimated budget/i), {
      target: { value: "1500000" },
    });

    fireEvent.click(screen.getByRole("button", { name: /save project settings/i }));

    await waitFor(() => {
      expect(updateProjectMutateAsyncMock).toHaveBeenCalledWith({
        projectId: "proj-real-77",
        data: {
          name: "Atlas Ridge Updated",
          code: "AR-77",
          description: "Phase 1 EPC project",
          project_type: "epc",
          status: "active",
          estimated_budget: 1500000,
          currency: "EUR",
        },
      });
    });

    expect(screen.getByText(/settings saved/i)).toBeInTheDocument();
  });
});
