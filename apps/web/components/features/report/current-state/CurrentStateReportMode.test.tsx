/**
 * Test Suite ID: TS-P0D-REPORT-UI-002
 * Current State Report container: loading, error, not-found and data states.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { CurrentStateReportMode } from "./CurrentStateReportMode";
import { buildCurrentStateReport } from "./current-state-report.fixture";

const currentStateMock = vi.fn();
const downloadMock = vi.fn();

vi.mock("@/lib/api/generated/project-reports/project-reports", () => ({
  useGetCurrentStateReportApiV1ProjectsProjectIdReportsCurrentStateGet: (...args: unknown[]) =>
    currentStateMock(...args),
}));

vi.mock("./current-state-export", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./current-state-export")>();
  return { ...actual, downloadTextFile: (...args: unknown[]) => downloadMock(...args) };
});

const baseQuery = {
  data: undefined,
  error: null,
  isLoading: false,
  isError: false,
  isFetching: false,
  refetch: vi.fn(),
};

describe("CurrentStateReportMode", () => {
  beforeEach(() => {
    currentStateMock.mockReset();
    downloadMock.mockReset();
  });

  it("requests the report for the given project", () => {
    currentStateMock.mockReturnValue({ ...baseQuery, isLoading: true });
    renderWithProviders(<CurrentStateReportMode projectId="proj-42" />);
    expect(currentStateMock).toHaveBeenCalledWith("proj-42", expect.anything());
  });

  it("shows a loading state while the report is generated", () => {
    currentStateMock.mockReturnValue({ ...baseQuery, isLoading: true });
    renderWithProviders(<CurrentStateReportMode projectId="proj-42" />);
    expect(screen.getByTestId("current-state-loading")).toHaveTextContent("Generating current state report");
  });

  it("shows a not-found state for a 404", () => {
    currentStateMock.mockReturnValue({
      ...baseQuery,
      isError: true,
      error: { response: { status: 404 }, message: "Request failed with status code 404" },
    });
    renderWithProviders(<CurrentStateReportMode projectId="proj-42" />);
    expect(screen.getByTestId("current-state-error")).toHaveTextContent(
      "This project was not found, or you do not have access to it.",
    );
  });

  it("shows a retryable error for other failures without leaking internals", async () => {
    const refetch = vi.fn();
    currentStateMock.mockReturnValue({
      ...baseQuery,
      isError: true,
      refetch,
      error: { response: { status: 500 }, message: "Request failed with status code 500" },
    });
    renderWithProviders(<CurrentStateReportMode projectId="proj-42" />);
    const error = screen.getByTestId("current-state-error");
    expect(error).toHaveTextContent("The current state report could not be generated.");
    expect(error).not.toHaveTextContent("500");
    screen.getByRole("button", { name: "Try again" }).click();
    expect(refetch).toHaveBeenCalled();
  });

  it("renders the report when data is available", () => {
    currentStateMock.mockReturnValue({ ...baseQuery, data: buildCurrentStateReport() });
    renderWithProviders(<CurrentStateReportMode projectId="proj-42" />);
    expect(screen.getByTestId("report-header")).toHaveTextContent("Hospital North");
  });

  it("lets the user regenerate the report", () => {
    const refetch = vi.fn();
    currentStateMock.mockReturnValue({ ...baseQuery, data: buildCurrentStateReport(), refetch });
    renderWithProviders(<CurrentStateReportMode projectId="proj-42" />);
    screen.getByRole("button", { name: "Regenerate" }).click();
    expect(refetch).toHaveBeenCalled();
  });

  it("downloads the exact report shown as JSON and CSV", () => {
    const report = buildCurrentStateReport();
    currentStateMock.mockReturnValue({ ...baseQuery, data: report });
    renderWithProviders(<CurrentStateReportMode projectId="proj-42" />);

    screen.getByRole("button", { name: "Download JSON" }).click();
    expect(downloadMock).toHaveBeenCalledWith(
      "current-state-report-HN-01-20260913T120000Z.json",
      JSON.stringify(report, null, 2),
      "application/json;charset=utf-8",
    );

    screen.getByRole("button", { name: "Download CSV" }).click();
    const [filename, content, mime] = downloadMock.mock.calls[1];
    expect(filename).toBe("current-state-report-HN-01-20260913T120000Z.csv");
    expect(content.startsWith("report_schema_version,")).toBe(true);
    expect(mime).toBe("text/csv;charset=utf-8");
  });

  it("never regenerates the report on its own", () => {
    currentStateMock.mockReturnValue({ ...baseQuery, isLoading: true });
    renderWithProviders(<CurrentStateReportMode projectId="proj-42" />);
    expect(currentStateMock).toHaveBeenCalledWith(
      "proj-42",
      expect.objectContaining({
        query: expect.objectContaining({
          enabled: true,
          staleTime: Infinity,
          refetchOnWindowFocus: false,
          refetchOnReconnect: false,
        }),
      }),
    );
  });

  it("keeps showing the last report when regeneration fails", () => {
    currentStateMock.mockReturnValue({
      ...baseQuery,
      data: buildCurrentStateReport(),
      isError: true,
      error: { response: { status: 500 } },
    });
    renderWithProviders(<CurrentStateReportMode projectId="proj-42" />);
    expect(screen.getByTestId("report-header")).toHaveTextContent("Hospital North");
    expect(screen.getByTestId("regenerate-failed")).toHaveTextContent(
      "Could not regenerate the report; showing the report generated",
    );
    expect(screen.queryByTestId("current-state-error")).toBeNull();
  });

  it("announces loading and errors to assistive technology", () => {
    currentStateMock.mockReturnValue({ ...baseQuery, isLoading: true });
    const { unmount } = renderWithProviders(<CurrentStateReportMode projectId="proj-42" />);
    expect(screen.getByRole("status")).toHaveTextContent("Generating current state report");
    unmount();
    currentStateMock.mockReturnValue({ ...baseQuery, isError: true, error: { response: { status: 500 } } });
    renderWithProviders(<CurrentStateReportMode projectId="proj-42" />);
    expect(screen.getByRole("alert")).toHaveTextContent("The current state report could not be generated.");
  });

  it("says so when there is no project to report on", () => {
    currentStateMock.mockReturnValue({ ...baseQuery });
    renderWithProviders(<CurrentStateReportMode projectId="" />);
    expect(currentStateMock).toHaveBeenCalledWith(
      "",
      expect.objectContaining({ query: expect.objectContaining({ enabled: false }) }),
    );
    expect(screen.getByTestId("current-state-no-project")).toHaveTextContent("No project selected.");
  });

  it("does not offer downloads before a report exists", () => {
    currentStateMock.mockReturnValue({ ...baseQuery, isLoading: true });
    renderWithProviders(<CurrentStateReportMode projectId="proj-42" />);
    expect(screen.queryByRole("button", { name: "Download CSV" })).toBeNull();
  });
});
