import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@/src/tests/test-utils";

const { apiGet, useParams } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  useParams: vi.fn(() => ({ id: "project-synthetic", documentId: "document-synthetic" })),
}));

vi.mock("next/navigation", () => ({ useParams }));
vi.mock("@/lib/api/client", () => ({ apiClient: { get: apiGet } }));

import N4FindingsPage from "./page";

const proposed = (index: number, exact = true) => ({
  finding_key: "synthetic-risk-" + index,
  window_ordinal: index % 2,
  title: "Risk " + index,
  interpretation: "This is a synthetic contract analysis " + index + ". " + "More detailed context. ".repeat(12),
  clause_ref: "2.5",
  source_quote: exact ? "Exact N2 evidence " + index : "Unverified candidate text",
  n2_quote_status: exact ? "N2_EXACT_MATCH" : "NOT_LOCATED",
  severity: "UNASSESSED",
  review_state: "PROPOSED",
  dimension: index % 2 === 0 ? "SCHEDULE" : "BUDGET",
  consequences: "Possible contractual consequences " + index,
  page_number: index === 0 ? 12 : null,
});
const response = (status = "PARTIAL_UNASSESSED") => ({
  status,
  total_findings: 4,
  coverage: {
    total: 2, windows_with_result: 2, examined: 1, blocked: 1,
    windows: [
      { ordinal: 0, status: "BLOCKED", blocked_reason: "REFERENCES_UNRESOLVED",
        unresolved_refs: ["Synthetic Annex C"], has_result: true },
      { ordinal: 1, status: "EXAMINED", blocked_reason: null,
        unresolved_refs: [], has_result: true },
    ],
  },
  findings: [proposed(0), proposed(1, false), proposed(2), proposed(3)],
});

describe("JV1-A21 business-facing provisional findings (synthetic; no HITL)", () => {
  beforeEach(() => {
    apiGet.mockReset();
    useParams.mockReturnValue({ id: "project-synthetic", documentId: "document-synthetic" });
  });
  afterEach(() => vi.clearAllMocks());

  it("groups proposed findings by business area, without claiming severity or approvals", async () => {
    apiGet.mockResolvedValue({ data: response() });
    render(<N4FindingsPage />);
    expect(await screen.findAllByTestId("n4-proposed-finding")).toHaveLength(4);
    expect(screen.getByRole("heading", { name: /schedule/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /budget/i })).toBeInTheDocument();
    expect(screen.getAllByText(/severity not evaluated/i)).toHaveLength(4);
    expect(screen.queryByRole("button", { name: /approve|reject/i })).not.toBeInTheDocument();
    expect(apiGet).toHaveBeenCalledWith(
      "/projects/project-synthetic/documents/document-synthetic/n4-findings",
      { params: { offset: 0, limit: 100 } },
    );
  });

  it("exposes gaps clearly and never offers a fictitious retry or manual closure", async () => {
    apiGet.mockResolvedValue({ data: response() });
    render(<N4FindingsPage />);
    const banner = await screen.findByTestId("n4-coverage");
    expect(banner).toHaveTextContent(/1 section.*blocked/i);
    expect(screen.getByTestId("n4-unresolved")).toHaveTextContent("Synthetic Annex C");
    expect(screen.getByRole("button", { name: /retry failed sections/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /close gap manually/i })).toBeDisabled();
    expect(screen.getByText(/these actions require a verified server workflow/i)).toBeInTheDocument();
    expect(apiGet).toHaveBeenCalledTimes(1);
  });

  it("lists a BLOCKED section even without a reason or reference metadata", async () => {
    const incomplete = response();
    incomplete.coverage.windows[0] = {
      ordinal: 0, status: "BLOCKED", blocked_reason: null,
      unresolved_refs: [], has_result: true,
    };
    apiGet.mockResolvedValue({ data: incomplete });
    render(<N4FindingsPage />);

    const banner = await screen.findByTestId("n4-coverage");
    expect(banner).toHaveTextContent(/1 section.*blocked/i);
    const pending = screen.getAllByTestId("n4-unresolved");
    expect(pending).toHaveLength(1);
    expect(pending[0]).toHaveTextContent("Section 1: Analysis blocked");
    expect(pending[0]).toHaveTextContent(/details not available/i);
    expect(screen.getByRole("button", { name: /retry failed sections/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /close gap manually/i })).toBeDisabled();
  });

  it("puts source and full interpretation behind disclosure, and labels page as unverified", async () => {
    apiGet.mockResolvedValue({ data: response() });
    render(<N4FindingsPage />);
    const cards = await screen.findAllByTestId("n4-proposed-finding");
    // Group order is alphabetical; locate by synthetic title rather than relying on response order.
    const scheduled = cards.find((card) => card.textContent?.includes("Risk 0"))!;
    const budget = cards.find((card) => card.textContent?.includes("Risk 1"))!;
    expect(scheduled).toHaveTextContent("Page 12");
    expect(scheduled).toHaveTextContent(/not independently verified/i);
    expect(budget).toHaveTextContent(/page not established/i);
    expect(budget).toHaveTextContent(/consequences/i);
    const evidence = scheduled.querySelector("details")!;
    expect(evidence).not.toHaveAttribute("open");
    fireEvent.click(evidence.querySelector("summary")!);
    expect(evidence).toHaveAttribute("open");
    expect(screen.getByText("Exact N2 evidence 0")).toBeInTheDocument();
    fireEvent.click(budget.querySelector("summary")!);
    expect(screen.queryByText("Unverified candidate text")).not.toBeInTheDocument();
    expect(budget).toHaveTextContent(/quotation not verified/i);
  });

  it("does not misrepresent absent results as zero contractual risks", async () => {
    apiGet.mockResolvedValue({ data: { status: "RESULTS_NOT_AVAILABLE", findings: [],
      total_findings: null, coverage: null } });
    render(<N4FindingsPage />);
    expect(await screen.findByTestId("n4-not-run")).toHaveTextContent(/does not mean zero risks/i);
    expect(screen.queryByTestId("n4-proposed-finding")).not.toBeInTheDocument();
  });

  it("fails closed on a superseded revision or denied tenant access", async () => {
    apiGet.mockRejectedValue(new Error("404"));
    render(<N4FindingsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable or document revision superseded/i);
    expect(screen.queryByRole("button", { name: /approve|reject/i })).not.toBeInTheDocument();
  });

  it("reloads the read-only evidence on remount, preserving server authority", async () => {
    apiGet.mockResolvedValue({ data: response() });
    const first = render(<N4FindingsPage />);
    await screen.findByTestId("n4-coverage");
    first.unmount();
    render(<N4FindingsPage />);
    await screen.findByTestId("n4-coverage");
    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(2));
  });
});
