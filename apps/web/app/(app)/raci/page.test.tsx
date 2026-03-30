/**
 * Test Suite ID: TASK-1347
 * Route Coverage: RACI real backend project filter
 */
import { fireEvent, renderWithProviders, screen } from "@/src/tests/test-utils";
import { describe, expect, it, vi } from "vitest";
import RaciPage from "./page";

const useRaciMock = vi.fn();
const useProjectsMock = vi.fn();

vi.mock("@/hooks/useRaci", () => ({
  useRaci: (...args: unknown[]) => useRaciMock(...args),
}));

vi.mock("@/hooks/useProjects", () => ({
  useProjects: (...args: unknown[]) => useProjectsMock(...args),
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
      <label htmlFor="project-filter">Project Filter</label>
      <select
        id="project-filter"
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

describe("RaciPage backend project integration", () => {
  it("loads project filter options from the backend and refetches the matrix for the selected project", () => {
    useProjectsMock.mockReturnValue({
      data: [
        { id: "proj-real-1", name: "Hospital Central" },
        { id: "proj-real-2", name: "Port Expansion" },
      ],
      isLoading: false,
      error: null,
    });

    useRaciMock.mockImplementation((projectId?: string) => ({
      data:
        projectId === "proj-real-2"
          ? [
              {
                activity: "Approve marine schedule",
                projectManager: "R",
                technicalLead: "A",
                stakeholder: "C",
                contractor: "I",
                projectId,
              },
            ]
          : [
              {
                activity: "Review baseline scope",
                projectManager: "R",
                technicalLead: "A",
                stakeholder: "C",
                contractor: "I",
              },
            ],
      loading: false,
      error: null,
    }));

    renderWithProviders(<RaciPage />);

    expect(screen.getByRole("option", { name: /hospital central/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /port expansion/i })).toBeInTheDocument();
    expect(useRaciMock).toHaveBeenLastCalledWith(undefined);

    fireEvent.change(screen.getByLabelText(/project filter/i), {
      target: { value: "proj-real-2" },
    });

    expect(useRaciMock).toHaveBeenLastCalledWith("proj-real-2");
    expect(screen.getByText(/approve marine schedule/i)).toBeInTheDocument();
  });

  it("opens project-type templates and previews the selected RACI setup", () => {
    useProjectsMock.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });

    useRaciMock.mockReturnValue({
      data: [],
      loading: false,
      error: null,
    });

    renderWithProviders(<RaciPage />);

    fireEvent.click(screen.getByRole("button", { name: "RACI Templates" }));

    expect(
      screen.getByText("Start from a project-type responsibility template"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /EPC Megaproject/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Industrial Retrofit/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Public Infrastructure/ }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Public Infrastructure/ }));

    expect(
      screen.getByRole("heading", { name: "Public Infrastructure" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Deploy a governance-ready RACI model for regulated delivery programs."),
    ).toBeInTheDocument();
    expect(screen.getByText("Permit Control")).toBeInTheDocument();
    expect(screen.getByText("Community Review")).toBeInTheDocument();
  });
});
