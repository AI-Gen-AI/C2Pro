/**
 * Test Suite ID: TASK-1347
 * Route Coverage: Stakeholders real backend project selector
 */
import {
  createMockSearchParams,
  fireEvent,
  renderWithProviders,
  screen,
} from "@/src/tests/test-utils";
import { describe, expect, it, vi } from "vitest";
import StakeholdersPage from "./page";

const useProjectsMock = vi.fn();
const stakeholderMatrixMock = vi.fn();
const searchParamsMock = vi.fn();

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParamsMock(),
}));

vi.mock("@/hooks/useProjects", () => ({
  useProjects: (...args: unknown[]) => useProjectsMock(...args),
}));

vi.mock("@/components/stakeholders/StakeholderMatrix", () => ({
  StakeholderMatrix: ({ projectId }: { projectId?: string }) => {
    stakeholderMatrixMock(projectId);
    return <div>Stakeholder matrix for {projectId ?? "none"}</div>;
  },
}));

vi.mock("@/components/ui/select", () => ({
  Select: ({
    value,
    onValueChange,
    children,
  }: {
    value: string;
    onValueChange: (value: string) => void;
    children: React.ReactNode;
  }) => (
    <div>
      <label htmlFor="stakeholder-project-filter">Project Filter</label>
      <select
        id="stakeholder-project-filter"
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
      >
        {children}
      </select>
    </div>
  ),
  SelectTrigger: ({ children }: { children: React.ReactNode }) => children,
  SelectValue: ({ placeholder }: { placeholder?: string }) => <>{placeholder}</>,
  SelectContent: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  SelectItem: ({
    value,
    children,
  }: {
    value: string;
    children: React.ReactNode;
  }) => <option value={value}>{children}</option>,
}));

describe("StakeholdersPage backend project integration", () => {
  it("loads project options from the backend and routes the selected project into the matrix", () => {
    searchParamsMock.mockReturnValue(createMockSearchParams());
    useProjectsMock.mockReturnValue({
      data: [
        { id: "proj-1", name: "Hospital Central" },
        { id: "proj-2", name: "Port Expansion" },
      ],
      isLoading: false,
      error: null,
    });

    renderWithProviders(<StakeholdersPage />);

    expect(screen.getByRole("option", { name: /hospital central/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /port expansion/i })).toBeInTheDocument();
    expect(screen.getByText(/stakeholder matrix for none/i)).toBeInTheDocument();
    expect(stakeholderMatrixMock).toHaveBeenLastCalledWith(undefined);

    fireEvent.change(screen.getByLabelText(/project filter/i), {
      target: { value: "proj-2" },
    });

    expect(screen.getByText(/stakeholder matrix for proj-2/i)).toBeInTheDocument();
    expect(stakeholderMatrixMock).toHaveBeenLastCalledWith("proj-2");
  });
});
