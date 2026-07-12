/**
 * TS-AI-LANGSMITH-VALIDATION-UNIT
 * TASK-AI-025: UsageMetricsTable component unit tests
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { UsageMetricsTable } from "./UsageMetricsTable";
import type { AIUsageMetric } from "@/lib/api/contracts";

const createMockMetrics = (): AIUsageMetric[] => [
  {
    id: "1",
    timestamp: "2026-05-01T10:00:00Z",
    model: "claude-3-5-sonnet",
    prompt_version: "v2026.04.20",
    input_tokens: 1000,
    output_tokens: 500,
    total_tokens: 1500,
    cost: 0.0125,
    latency_ms: 350,
    trace_url: "https://smith.langchain.com/o/c2pro/traces/abc123",
  },
  {
    id: "2",
    timestamp: "2026-05-01T08:00:00Z",
    model: "gpt-4o",
    prompt_version: "v2026.04.15",
    input_tokens: 2000,
    output_tokens: 800,
    total_tokens: 2800,
    cost: 0.025,
    latency_ms: 450,
    trace_url: null,
  },
  {
    id: "3",
    timestamp: "2026-05-01T06:00:00Z",
    model: "claude-3-opus",
    prompt_version: "v2026.04.20",
    input_tokens: 5000,
    output_tokens: 2000,
    total_tokens: 7000,
    cost: 0.085,
    latency_ms: 800,
    trace_url: "https://smith.langchain.com/o/c2pro/traces/xyz789",
  },
];

function dataRows() {
  return screen
    .getAllByRole("row")
    .filter((row) => row.querySelectorAll("td").length > 0);
}

describe("UsageMetricsTable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    HTMLCanvasElement.prototype.getContext = vi.fn();
    HTMLCanvasElement.prototype.toDataURL = vi.fn();
  });

  it("renders loading state", () => {
    render(<UsageMetricsTable metrics={[]} loading={true} error={null} />);
    expect(screen.getByText(/Loading usage metrics/)).toBeInTheDocument();
  });

  it("renders error state", () => {
    render(<UsageMetricsTable metrics={[]} loading={false} error="Failed to load" />);
    expect(screen.getByText("Failed to load")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    render(<UsageMetricsTable metrics={[]} loading={false} error={null} />);
    expect(screen.getByText("No usage metrics available.")).toBeInTheDocument();
  });

  it("renders metrics table with data", () => {
    const metrics = createMockMetrics();
    render(<UsageMetricsTable metrics={metrics} loading={false} error={null} />);

    expect(screen.getByText("Usage Metrics")).toBeInTheDocument();
    expect(screen.getByText("Export CSV")).toBeInTheDocument();
    expect(screen.getByText("claude-3-5-sonnet")).toBeInTheDocument();
    expect(screen.getByText("gpt-4o")).toBeInTheDocument();
  });

  it("sorts by timestamp ascending", () => {
    const metrics = createMockMetrics();
    render(<UsageMetricsTable metrics={metrics} loading={false} error={null} />);

    const timestampHeader = screen.getByText(/Timestamp/);
    fireEvent.click(timestampHeader);

    const rows = dataRows();
    expect(rows[0]).toHaveTextContent("claude-3-opus");
    expect(rows[2]).toHaveTextContent("claude-3-5-sonnet");
  });

  it("sorts by model descending", () => {
    const metrics = createMockMetrics();
    render(<UsageMetricsTable metrics={metrics} loading={false} error={null} />);

    const modelHeader = screen.getByText(/Model/);
    fireEvent.click(modelHeader);
    fireEvent.click(modelHeader);

    const rows = dataRows();
    expect(rows[0]).toHaveTextContent("gpt-4o");
  });

  it("sorts by total_tokens", () => {
    const metrics = createMockMetrics();
    render(<UsageMetricsTable metrics={metrics} loading={false} error={null} />);

    const tokensHeader = screen.getByText(/Tokens/);
    fireEvent.click(tokensHeader);
    fireEvent.click(tokensHeader);

    const rows = dataRows();
    expect(rows[0]).toHaveTextContent("7000");
  });

  it("sorts by cost", () => {
    const metrics = createMockMetrics();
    render(<UsageMetricsTable metrics={metrics} loading={false} error={null} />);

    const costHeader = screen.getByText(/Cost/);
    fireEvent.click(costHeader);
    fireEvent.click(costHeader);

    const rows = dataRows();
    expect(rows[0]).toHaveTextContent("$0.0850");
  });

  it("renders trace_url links", () => {
    const metrics = createMockMetrics();
    render(<UsageMetricsTable metrics={metrics} loading={false} error={null} />);

    const traceLinks = screen.getAllByText("View Trace");
    expect(traceLinks).toHaveLength(2);
    expect(traceLinks[0]).toHaveAttribute("href", "https://smith.langchain.com/o/c2pro/traces/abc123");
  });

  it("handles null trace_url", () => {
    const metrics = [
      {
        id: "1",
        timestamp: "2026-05-01T10:00:00Z",
        model: "test-model",
        prompt_version: "v1",
        input_tokens: 100,
        output_tokens: 50,
        total_tokens: 150,
        cost: 0.001,
        latency_ms: 100,
        trace_url: null,
      },
    ];
    render(<UsageMetricsTable metrics={metrics} loading={false} error={null} />);

    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("exports CSV with correct data", () => {
    const metrics = createMockMetrics();
    const originalCreateElement = document.createElement;
    const mockAppendChild = vi.fn();
    const mockRemoveChild = vi.fn();

    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      const element = originalCreateElement.call(document, tag);
      if (tag === "a") {
        vi.spyOn(element, "click");
        vi.spyOn(element, "appendChild").mockImplementation(mockAppendChild);
        vi.spyOn(element, "removeChild").mockImplementation(mockRemoveChild);
      }
      return element as unknown as HTMLElement;
    });

    const originalCreateObjectURL = URL.createObjectURL;
    const originalRevokeObjectURL = URL.revokeObjectURL;
    vi.spyOn(URL, "createObjectURL").mockImplementation(() => "blob:http://test");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});

    render(<UsageMetricsTable metrics={metrics} loading={false} error={null} />);

    const exportButton = screen.getByText("Export CSV");
    fireEvent.click(exportButton);

    expect(document.createElement).toHaveBeenCalledWith("a");
    expect(URL.createObjectURL).toHaveBeenCalled();

    vi.mocked(URL.createObjectURL).mockRestore();
    vi.mocked(URL.revokeObjectURL).mockRestore();
  });
});
