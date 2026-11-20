import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@/src/tests/test-utils";

const { apiGet, useParams } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  useParams: vi.fn(() => ({ id: "project-vs1", documentId: "doc-vs1" })),
}));

vi.mock("next/navigation", () => ({ useParams }));
vi.mock("@/lib/api/client", () => ({ apiClient: { get: apiGet } }));

import N4FindingsPage from "./page";

const proposed = (index: number, exact = true) => ({
  finding_key: `risk-${index}`,
  window_ordinal: index % 2,
  title: `Risk ${index}`,
  interpretation: `Interpretation ${index}`,
  clause_ref: "2.5",
  source_quote: exact ? `Exact N2 evidence ${index}` : null,
  n2_quote_status: exact ? "N2_EXACT_MATCH" : "NOT_LOCATED",
  severity: "UNASSESSED",
  review_state: "PROPOSED",
});
const response = (status = "PARTIAL_UNASSESSED") => ({
  status,
  total_findings: 4,
  coverage: {
    total: 2, windows_with_result: 2, examined: 1, blocked: 1,
    windows: [
      { ordinal: 0, status: "BLOCKED", blocked_reason: "REFERENCES_UNRESOLVED",
        unresolved_refs: ["Annex C"], has_result: true },
      { ordinal: 1, status: "EXAMINED", blocked_reason: null,
        unresolved_refs: [], has_result: true },
    ],
  },
  findings: [proposed(0), proposed(1, false), proposed(2), proposed(3)],
});

describe("VS-1 provisional N4 evidence UI (no HITL)", () => {
  beforeEach(() => {
    apiGet.mockReset();
    useParams.mockReturnValue({ id: "project-vs1", documentId: "doc-vs1" });
  });
  afterEach(() => vi.clearAllMocks());

  it("shows persisted/blocked coverage and all provisional candidates, with no approval or Retry", async () => {
    apiGet.mockResolvedValue({ data: response() });
    render(<N4FindingsPage />);
    expect(await screen.findByTestId("n4-coverage")).toHaveTextContent(
      "2/2 windows with persisted results",
    );
    expect(screen.getByTestId("n4-coverage")).toHaveTextContent("1 examined");
    expect(screen.getByTestId("n4-coverage")).toHaveTextContent("1 blocked");
    expect(screen.getByTestId("n4-unresolved")).toHaveTextContent("Annex C");
    expect(screen.getAllByTestId("n4-proposed-finding")).toHaveLength(4);
    expect(screen.getByText("Exact N2 evidence 0")).toBeInTheDocument();
    expect(screen.getByText("Interpretation 0", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Citation not located in the N2 text.")).toBeInTheDocument();
    expect(screen.getAllByText("Quote located in N2; original PDF not verified.")).toHaveLength(3);
    expect(screen.queryByRole("button", { name: /approve|reject|retry/i })).not.toBeInTheDocument();
    expect(apiGet).toHaveBeenCalledWith(
      "/projects/project-vs1/documents/doc-vs1/n4-findings",
      { params: { offset: 0, limit: 100 } },
    );
  });

  it("does not misrepresent an unexecuted analysis as zero risk", async () => {
    apiGet.mockResolvedValue({ data: { status: "RESULTS_NOT_AVAILABLE", findings: [],
      total_findings: null, coverage: null } });
    render(<N4FindingsPage />);
    expect(await screen.findByTestId("n4-not-run")).toHaveTextContent(
      "This does not mean zero risks",
    );
    expect(screen.queryByTestId("n4-proposed-finding")).not.toBeInTheDocument();
  });

  it("fails visibly when source revision is superseded or the API denies access", async () => {
    apiGet.mockRejectedValue(new Error("404"));
    render(<N4FindingsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Findings unavailable or document revision superseded",
    );
    expect(screen.queryByRole("button", { name: /retry/i })).not.toBeInTheDocument();
  });

  it("reloads its read-only evidence from the API when remounted", async () => {
    apiGet.mockResolvedValue({ data: response() });
    const first = render(<N4FindingsPage />);
    await screen.findByTestId("n4-coverage");
    first.unmount();
    render(<N4FindingsPage />);
    await screen.findByTestId("n4-coverage");
    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(2));
  });
});
