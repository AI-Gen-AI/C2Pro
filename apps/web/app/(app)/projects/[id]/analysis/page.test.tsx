/**
 * Test Suite ID: TASK-1347, TASK-OPS-DOCFLOW-010
 * Route Coverage: Project analysis backend summary
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import AnalysisPage from "./page";

const getDashboardMock = vi.fn();
const listProjectAlertsMock = vi.fn();
const useProjectDocumentsMock = vi.fn();
const rerunAnalysisMock = vi.fn();
const projectHealthMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "proj-real-7" }),
}));

vi.mock("@/lib/api/generated/coherence-dashboard/coherence-dashboard", () => ({
  useGetCoherenceDashboardApiCoherenceDashboardProjectIdGet: (...args: unknown[]) =>
    getDashboardMock(...args),
}));

vi.mock("@/lib/api/generated/alerts/alerts", () => ({
  useListProjectAlertsApiV1AlertsProjectsProjectIdGet: (...args: unknown[]) =>
    listProjectAlertsMock(...args),
}));

vi.mock("@/lib/api/generated/project-health/project-health", () => ({
  useGetProjectHealthApiV1ProjectsProjectIdHealthGet: (...args: unknown[]) =>
    projectHealthMock(...args),
}));

// Stub only the presentational component; keep the real coherence helper so this page
// test exercises the actual contract logic rather than a convenient double.
vi.mock("@/components/features/health/SingleDocumentHealth", async (importOriginal) => ({
  ...(await importOriginal<
    typeof import("@/components/features/health/SingleDocumentHealth")
  >()),
  SingleDocumentHealth: ({ projectId }: { projectId: string }) => (
    <div data-testid="single-document-health">health for {projectId}</div>
  ),
}));

vi.mock("@/components/features/analysis/AnalysisProgressTracker", () => ({
  AnalysisProgressTracker: ({ projectId }: { projectId: string }) => (
    <div>Reading documents for {projectId}</div>
  ),
}));

vi.mock("@/hooks/useProjectDocuments", () => ({
  useProjectDocuments: (...args: unknown[]) => useProjectDocumentsMock(...args),
}));

vi.mock("@/hooks/useProjectCoherenceActions", () => ({
  useProjectCoherenceActions: () => ({
    rerunAnalysis: rerunAnalysisMock,
    evaluateCoherence: vi.fn(),
    isRerunningAnalysis: false,
    isEvaluating: false,
  }),
}));

describe("Project analysis page real-data boundary", () => {
  beforeEach(() => {
    useProjectDocumentsMock.mockReset();
    rerunAnalysisMock.mockReset();
    projectHealthMock.mockReset();
    projectHealthMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    });
    useProjectDocumentsMock.mockReturnValue({
      documents: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  it("renders real backend-shaped coherence metadata and alert payloads", () => {
    getDashboardMock.mockReturnValue({
      data: {
        project_id: "proj-real-7",
        tenant_id: "tenant-1",
        coherence_score: 51,
        global_score: 51,
        sub_scores: { SCOPE: 80, TIME: 51 },
        weights_used: { SCOPE: 0.5, TIME: 0.5 },
        alert_count: 1,
        document_count: 1,
        methodology_version: "3.0",
        score_version: "v1_exponential_decay",
        score_reason: null,
        score_missing_dimensions: ["schedule", "budget"],
        last_updated: "2026-05-07T16:35:41Z",
      },
      isLoading: false,
      error: null,
    });
    listProjectAlertsMock.mockReturnValue({
      data: {
        items: [
          {
            id: "alert-real-time",
            category: "TIME",
            severity: "medium",
            status: "open",
            message: "Schedule coherence alert from real document",
          },
        ],
      },
      isLoading: false,
      error: null,
    });
    renderWithProviders(<AnalysisPage />);

    expect(screen.getByText(/v1 exponential decay/i)).toBeInTheDocument();
    expect(screen.getByText(/missing evidence: schedule, budget/i)).toBeInTheDocument();
    expect(screen.getByText(/schedule coherence alert from real document/i)).toBeInTheDocument();
    expect(screen.getByText(/medium/i)).toBeInTheDocument();
  });

  it("renders backend-backed analysis metrics instead of the placeholder card", () => {
    // The Coherence metric now renders only on positive Health evidence that a subscore
    // was incorporated (INV-COH), so this multi-document case must supply it.
    projectHealthMock.mockReturnValue({
      data: {
        project_id: "proj-real-7",
        tenant_id: "tenant-1",
        dimensions: [
          {
            dimension: "contract",
            band: "unknown",
            confidence: 0.5,
            score: null,
            evidence: [
              {
                ref_id: "project-coherence-subscore",
                source: "project_coherence",
                tier: "weak",
                locator: "overall_score",
              },
            ],
            missing_data: [],
          },
        ],
      },
      isLoading: false,
      isError: false,
    });
    getDashboardMock.mockReturnValue({
      data: {
        coherence_score: 84,
        sub_scores: { BUDGET: 59 },
        alert_count: 3,
        document_count: 9,
      },
      isLoading: false,
      error: null,
    });
    listProjectAlertsMock.mockReturnValue({
      data: {
        items: [
          {
            id: "alert-1",
            severity: "critical",
            status: "open",
            message: "Date mismatch",
          },
          {
            id: "alert-2",
            severity: "high",
            status: "open",
            message: "Budget drift",
          },
          {
            id: "alert-3",
            severity: "low",
            status: "resolved",
            message: "Closed signal",
          },
        ],
      },
      isLoading: false,
      error: null,
    });
    renderWithProviders(<AnalysisPage />);

    expect(getDashboardMock).toHaveBeenCalledWith("proj-real-7");
    expect(listProjectAlertsMock).toHaveBeenCalledWith("proj-real-7", undefined);
    expect(screen.getByText(/analysis summary/i)).toBeInTheDocument();
    expect(screen.getAllByText("84").length).toBeGreaterThan(0);
    expect(screen.getAllByText("2").length).toBeGreaterThan(0);
    expect(screen.getAllByText("9").length).toBeGreaterThan(0);
    expect(screen.getByText("Budget coherence")).toBeInTheDocument();
    expect(screen.getByText("59")).toBeInTheDocument();
    expect(screen.queryByText("41%")).not.toBeInTheDocument();
    expect(screen.getByText(/date mismatch/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /open processing stream/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /process\/stream/i })).not.toBeInTheDocument();
    expect(screen.getByText(/reading documents/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/centro de alertas, riesgos y hallazgos automatizados/i),
    ).not.toBeInTheDocument();
  });

  it("renders an honest budget coherence placeholder when budget evidence is missing", () => {
    getDashboardMock.mockReturnValue({
      data: {
        coherence_score: 84,
        sub_scores: { SCOPE: 80 },
        alert_count: 0,
        document_count: 2,
      },
      isLoading: false,
      error: null,
    });
    listProjectAlertsMock.mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    });
    renderWithProviders(<AnalysisPage />);

    expect(screen.getByText("Budget coherence")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByTitle("Requires budget document")).toBeInTheDocument();
    expect(screen.queryByText("Budget Pressure")).not.toBeInTheDocument();
  });

  it("disables re-run analysis until the triplet is complete", () => {
    getDashboardMock.mockReturnValue({
      data: {
        coherence_score: 84,
        sub_scores: { BUDGET: 59 },
        alert_count: 0,
        document_count: 1,
      },
      isLoading: false,
      error: null,
    });
    listProjectAlertsMock.mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    });
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        {
          id: "contract",
          name: "Contract.pdf",
          type: "contract",
          status: "parsed",
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    renderWithProviders(<AnalysisPage />);

    expect(screen.getByRole("button", { name: /re-run analysis/i })).toBeDisabled();
    expect(screen.getByText(/upload contract, budget, and schedule/i)).toBeInTheDocument();
  });
});

describe("P0b-L4-5 — Health surface placement and Coherence suppression", () => {
  // Models the real contract: coherence_subscore is not a HealthVector field; the
  // CONTRACT dimension carries the project-coherence-subscore evidence ref only when a
  // subscore was actually incorporated.
  function vectorWithCoherence(incorporated: boolean) {
    return {
      project_id: "proj-real-7",
      tenant_id: "tenant-1",
      dimensions: [
        {
          dimension: "contract",
          band: "unknown",
          confidence: 0.5,
          score: null,
          evidence: incorporated
            ? [
                {
                  ref_id: "project-coherence-subscore",
                  source: "project_coherence",
                  tier: "weak",
                  locator: "overall_score",
                },
              ]
            : [],
          missing_data: incorporated ? [] : ["coherence subscore unavailable"],
        },
      ],
    };
  }

  function baseMocks() {
    getDashboardMock.mockReturnValue({
      data: { coherence_score: 62, score_version: "v1_weighted" },
      isLoading: false,
      error: null,
    });
    listProjectAlertsMock.mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    });
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        { id: "contract", name: "Contract.pdf", type: "contract", status: "parsed" },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
  }

  it("mounts the single-document Health surface for this project", () => {
    baseMocks();
    projectHealthMock.mockReturnValue({
      data: vectorWithCoherence(false),
      isLoading: false,
      isError: false,
    });

    renderWithProviders(<AnalysisPage />);

    expect(screen.getByTestId("single-document-health")).toHaveTextContent(
      "proj-real-7",
    );
  });

  function expectNoCoherenceNumber() {
    // Neither readout may show a number, and neither may substitute zero.
    expect(screen.queryByTestId("analysis-coherence-score")).not.toBeInTheDocument();
    expect(screen.queryByText("Coherence Score")).not.toBeInTheDocument();
    const note = screen.getByTestId("analysis-coherence-unavailable");
    expect(note.textContent).not.toMatch(/\b0\b/);
    expect(note.textContent).not.toMatch(/\b62\b/);
    return note;
  }

  it("1 — while Health is loading, shows no Coherence number", () => {
    // Not-yet-known is not permission to show the legacy dashboard number.
    baseMocks();
    projectHealthMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    renderWithProviders(<AnalysisPage />);

    expect(expectNoCoherenceNumber()).toHaveAttribute("data-reason", "loading");
  });

  it("2 — when the Health request errors, shows no Coherence number", () => {
    // And does NOT infer "single document" from a failed request: that would turn an
    // infrastructure failure into a product finding.
    baseMocks();
    projectHealthMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: { response: { status: 500 } },
    });

    renderWithProviders(<AnalysisPage />);

    const note = expectNoCoherenceNumber();
    expect(note).toHaveAttribute("data-reason", "unverified");
    expect(note).not.toHaveTextContent(/at least\s+two/i);
  });

  it("3 — loaded with no subscore evidence, explains it as insufficient evidence", () => {
    // Only a LOADED vector lacking the evidence licenses the single-document claim.
    baseMocks();
    projectHealthMock.mockReturnValue({
      data: vectorWithCoherence(false),
      isLoading: false,
      isError: false,
    });

    renderWithProviders(<AnalysisPage />);

    const note = expectNoCoherenceNumber();
    expect(note).toHaveAttribute("data-reason", "insufficient_evidence");
    expect(note).toHaveTextContent(/reconcilable evidence/i);
    // Document count is not the eligibility predicate.
    expect(note).not.toHaveTextContent(/at least\s+two|second document/i);
  });

  it("4 — with positive subscore evidence, renders the Coherence readouts unchanged", () => {
    baseMocks();
    projectHealthMock.mockReturnValue({
      data: vectorWithCoherence(true),
      isLoading: false,
      isError: false,
    });

    renderWithProviders(<AnalysisPage />);

    expect(screen.getByTestId("analysis-coherence-score")).toHaveTextContent("62");
    expect(screen.getByText("Coherence Score")).toBeInTheDocument();
    expect(
      screen.queryByTestId("analysis-coherence-unavailable"),
    ).not.toBeInTheDocument();
  });
});
