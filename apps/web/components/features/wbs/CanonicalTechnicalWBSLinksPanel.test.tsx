/** S7 canonical approvals persisted across sessions, never inferred from audits. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CanonicalTechnicalWBSLinksPanel } from "./CanonicalTechnicalWBSLinksPanel";

const { query, request, auth, refetch } = vi.hoisted(() => ({
  query: vi.fn(),
  request: vi.fn(),
  refetch: vi.fn(),
  auth: { orgId: "org-1", userId: "clerk-user-1", isLoaded: true },
}));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth }));
vi.mock("@tanstack/react-query", () => ({ useQuery: (args: unknown) => query(args) }));
vi.mock("@/lib/api/client", () => ({
  orvalApiClient: (args: unknown) => request(args),
}));

const approved = {
  event_id: "approval-1",
  review_event_id: "audit-1",
  approved_at: "2026-10-29T15:00:00Z",
  technical_document_id: "doc-a",
  technical_revision_id: "rev-a",
  source_clause_id: "clause-a",
  source_section: "4.1",
  source_blob_hash: "a".repeat(64),
  wbs_baseline_id: "baseline-1",
  wbs_node_id: "node-1",
  wbs_code: "1.1",
  wbs_name: "Concrete",
  state: "CURRENT" as const,
  authority: "EXPLICIT_HUMAN_CANONICAL_LINK" as const,
  approved_canonical_link: true as const,
  technical_assessment: "NOT_ASSESSED" as const,
};

function mockRows(rows: object[]) {
  query.mockReturnValue({
    data: rows, isSuccess: true, isLoading: false,
    isFetching: false, isError: false, refetch,
  });
}

describe("CanonicalTechnicalWBSLinksPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    auth.orgId = "org-1";
    auth.userId = "clerk-user-1";
    auth.isLoaded = true;
    mockRows([]);
  });

  it("renders persisted CURRENT approved source, WBS and exact revision evidence", async () => {
    mockRows([approved]);
    render(<CanonicalTechnicalWBSLinksPanel projectId="proj-1" />);
    expect(screen.getByTestId("s7-current-links-count")).toHaveTextContent(
      "1 currently authoritative technical links",
    );
    const row = screen.getByTestId("s7-current-canonical-link");
    expect(row).toHaveTextContent("Current approved link");
    expect(row).toHaveTextContent("1.1 — Concrete");
    expect(row).toHaveTextContent("Technical compliance: NOT ASSESSED");
    expect(screen.queryByTestId("s7-historical-canonical-link")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /inspect original approved source revision/i }))
      .toHaveAttribute("href", "/projects/proj-1/evidence?documentId=doc-a&revisionId=rev-a&highlightId=clause-a");
    const options = query.mock.calls[0][0];
    expect(options.queryKey).toEqual([
      "technical-wbs-canonical-links", "org-1", "clerk-user-1", "proj-1",
    ]);
    expect(options.refetchOnMount).toBe("always");
    expect(options.staleTime).toBe(0);
    request.mockResolvedValue([approved]);
    await expect(options.queryFn()).resolves.toEqual([approved]);
    expect(request).toHaveBeenCalledWith({
      url: "/api/v1/projects/proj-1/technical-wbs/canonical-links",
      method: "GET",
    });
  });

  it("never presents historical approved events as current or approved scope", () => {
    mockRows([
      { ...approved, event_id: "approval-old", state: "STALE_WBS", wbs_code: null, wbs_name: null },
      { ...approved, event_id: "approval-stale-source", state: "STALE_SOURCE" },
    ]);
    render(<CanonicalTechnicalWBSLinksPanel projectId="proj-1" />);
    expect(screen.getByTestId("s7-current-links-count")).toHaveTextContent(
      "0 currently authoritative technical links",
    );
    expect(screen.queryByTestId("s7-current-canonical-link")).not.toBeInTheDocument();
    const rows = screen.getAllByTestId("s7-historical-canonical-link");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("not currently authoritative");
    expect(rows[0]).toHaveTextContent(/baseline or node has changed/i);
    expect(rows[1]).toHaveTextContent(/no longer has verified trusted-current authority/i);
    expect(rows[0]).not.toHaveTextContent("1.1 — Concrete");
  });

  it("does not claim zero/current approvals when the authenticated GET failed", () => {
    query.mockReturnValue({
      isSuccess: false, isLoading: false, isError: true,
      isFetching: false, refetch,
    });
    render(<CanonicalTechnicalWBSLinksPanel projectId="proj-1" />);
    expect(screen.getByTestId("s7-canonical-links-error")).toHaveTextContent(
      "No current links are claimed",
    );
    expect(screen.queryByTestId("s7-current-links-count")).not.toBeInTheDocument();
  });

  it("does not substitute audit-only records for a missing canonical GET", () => {
    mockRows([]);
    render(<CanonicalTechnicalWBSLinksPanel projectId="proj-1" />);
    expect(screen.getByText("No canonical Technical → WBS approvals recorded.")).toBeInTheDocument();
    expect(screen.queryByTestId("s7-current-canonical-link")).not.toBeInTheDocument();
  });

  it("separates cache identity across Clerk users and organizations and permits explicit refresh", async () => {
    mockRows([approved]);
    const { rerender } = render(<CanonicalTechnicalWBSLinksPanel projectId="proj-1" />);
    fireEvent.click(screen.getByRole("button", { name: /refresh canonical status/i }));
    await waitFor(() => expect(refetch).toHaveBeenCalledTimes(1));
    auth.orgId = "org-2";
    auth.userId = "clerk-user-2";
    rerender(<CanonicalTechnicalWBSLinksPanel projectId="proj-1" />);
    expect(query.mock.calls.at(-1)?.[0].queryKey).toEqual([
      "technical-wbs-canonical-links", "org-2", "clerk-user-2", "proj-1",
    ]);
    auth.isLoaded = false;
    rerender(<CanonicalTechnicalWBSLinksPanel projectId="proj-1" />);
    expect(query.mock.calls.at(-1)?.[0].enabled).toBe(false);
  });
});
