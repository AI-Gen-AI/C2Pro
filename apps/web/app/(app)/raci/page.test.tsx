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

vi.mock("@/config/env", () => ({
  env: {
    FEATURE_RACI_GENERATION: true,
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
  it("switches to a gantt-style timeline view using API-backed sequence and schedule dates", () => {
    useProjectsMock.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });

    useRaciMock.mockReturnValue({
      data: [
        {
          activity: "Review baseline scope",
          projectManager: "A",
          technicalLead: "R",
          stakeholder: "C",
          contractor: "I",
          sequenceIndex: 2,
          taskCode: "1.2",
          plannedStart: "2026-04-07T00:00:00Z",
          plannedEnd: "2026-04-11T00:00:00Z",
        },
        {
          activity: "Approve marine schedule",
          projectManager: "R",
          technicalLead: "A",
          stakeholder: "C",
          contractor: "I",
          sequenceIndex: 1,
          taskCode: "1.1",
          plannedStart: "2026-04-02T00:00:00Z",
          plannedEnd: "2026-04-05T00:00:00Z",
        },
      ],
      loading: false,
      error: null,
    });

    renderWithProviders(<RaciPage />);

    fireEvent.click(screen.getByRole("button", { name: "Timeline View" }));

    expect(screen.getByText("Gantt Timeline View")).toBeInTheDocument();
    expect(screen.getByText("Review baseline scope")).toBeInTheDocument();
    expect(screen.getByText("Approve marine schedule")).toBeInTheDocument();
    expect(screen.getByText("Sequence 2 · 1.2")).toBeInTheDocument();
    expect(screen.getByText("Sequence 1 · 1.1")).toBeInTheDocument();
    expect(screen.getByText("2026-04-07 to 2026-04-11")).toBeInTheDocument();
    expect(screen.getByText("2026-04-02 to 2026-04-05")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Matrix View" }));

    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("switches to a mobile-optimized list view that groups assignments by activity", () => {
    useProjectsMock.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });

    useRaciMock.mockReturnValue({
      data: [
        {
          activity: "Review baseline scope",
          projectManager: "A",
          technicalLead: "R",
          stakeholder: "C",
          contractor: "I",
        },
      ],
      loading: false,
      error: null,
    });

    renderWithProviders(<RaciPage />);

    fireEvent.click(screen.getByRole("button", { name: "List View" }));

    expect(screen.getByText("Mobile List View")).toBeInTheDocument();
    expect(screen.getByText("Review baseline scope")).toBeInTheDocument();
    expect(screen.getByText("Project Manager · A")).toBeInTheDocument();
    expect(screen.getByText("Technical Lead · R")).toBeInTheDocument();
    expect(screen.getByText("Stakeholder · C")).toBeInTheDocument();
    expect(screen.getByText("Contractor · I")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Matrix View" }));

    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("detects overloaded stakeholder lanes from the workload analysis", () => {
    useProjectsMock.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });

    useRaciMock.mockReturnValue({
      data: [
        {
          activity: "Review baseline scope",
          projectManager: "A",
          technicalLead: "R",
          stakeholder: "C",
          contractor: "I",
        },
        {
          activity: "Approve marine schedule",
          projectManager: "R",
          technicalLead: "A",
          stakeholder: "I",
          contractor: "C",
        },
        {
          activity: "Issue permit package",
          projectManager: "C",
          technicalLead: "R",
          stakeholder: "A",
          contractor: "",
        },
      ],
      loading: false,
      error: null,
    });

    renderWithProviders(<RaciPage />);

    expect(screen.getByText("Conflict Detection")).toBeInTheDocument();
    expect(screen.getByText("1 overloaded stakeholder lane")).toBeInTheDocument();
    expect(
      screen.getByText("Technical Lead exceeds the safe workload threshold with load 10."),
    ).toBeInTheDocument();
    expect(screen.getByText("Focus the next rebalance on Technical Lead assignments.")).toBeInTheDocument();
  });

  it("renders stakeholder workload analysis from the live RACI matrix rows", () => {
    useProjectsMock.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });

    useRaciMock.mockReturnValue({
      data: [
        {
          activity: "Review baseline scope",
          projectManager: "A",
          technicalLead: "R",
          stakeholder: "C",
          contractor: "I",
        },
        {
          activity: "Approve marine schedule",
          projectManager: "R",
          technicalLead: "A",
          stakeholder: "I",
          contractor: "C",
        },
        {
          activity: "Issue permit package",
          projectManager: "C",
          technicalLead: "R",
          stakeholder: "A",
          contractor: "",
        },
      ],
      loading: false,
      error: null,
    });

    renderWithProviders(<RaciPage />);

    expect(screen.getByText("Workload Analysis")).toBeInTheDocument();
    expect(screen.getByText("Busiest lane: Technical Lead")).toBeInTheDocument();
    expect(screen.getByText("3 assignments · load 8")).toBeInTheDocument();
    expect(screen.getByText("3 assignments · load 10")).toBeInTheDocument();
    expect(screen.getByText("3 assignments · load 6")).toBeInTheDocument();
    expect(screen.getByText("2 assignments · load 2")).toBeInTheDocument();
  });

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

  it("opens the AI auto-assign dialog, generates recommendations, and applies them to the matrix", () => {
    useProjectsMock.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });

    useRaciMock.mockReturnValue({
      data: [
        {
          activity: "Review baseline scope",
          projectManager: "R",
          technicalLead: "A",
          stakeholder: "C",
          contractor: "I",
        },
        {
          activity: "Approve marine schedule",
          projectManager: "C",
          technicalLead: "R",
          stakeholder: "I",
          contractor: "",
        },
      ],
      loading: false,
      error: null,
    });

    renderWithProviders(<RaciPage />);

    fireEvent.click(screen.getByRole("button", { name: /auto-assign ai/i }));

    expect(
      screen.getByText(/generate workload-aware responsibility suggestions/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/technical lead is the current rebalance target/i),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /generate suggestions/i }));

    expect(
      screen.getByText(/move accountable ownership for review baseline scope/i),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /apply suggestions/i }));

    expect(
      screen.getByText(/ai suggestions applied to 2 activities/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/ai suggestions applied to 2 activities\. balanced workload reassignment/i),
    ).toBeInTheDocument();
  });
});
