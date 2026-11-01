/** S7: persisted Budget/Schedule links, re-verified by the API; history is never shown as current. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { CanonicalStructuredWBSLinksPanel } from "./CanonicalStructuredWBSLinksPanel";

const { query, auth, refetch } = vi.hoisted(() => ({
  query: vi.fn(),
  refetch: vi.fn(),
  auth: { orgId: "org-1", userId: "user-1", isLoaded: true },
}));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth }));
vi.mock("@tanstack/react-query", () => ({ useQuery: (args: unknown) => query(args) }));
vi.mock("@/lib/api/client", () => ({ orvalApiClient: vi.fn() }));

const link = (over: object = {}) => ({
  event_id: "ev-1",
  family: "budget",
  approved_at: "2026-11-01T09:31:00Z",
  source_document_id: "doc-b",
  source_revision_id: "rev-b",
  source_locator: "Presupuesto!2",
  source_blob_hash: "a".repeat(64),
  wbs_baseline_id: "base-1",
  wbs_node_id: "node-1",
  state: "CURRENT",
  authority: "EXPLICIT_HUMAN_CANONICAL_LINK",
  source_assessment: "NOT_ASSESSED",
  ...over,
});
const rows = (data: object[]) =>
  query.mockReturnValue({ data, isSuccess: true, isLoading: false, isFetching: false, isError: false, refetch });

describe("CanonicalStructuredWBSLinksPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    auth.userId = "user-1";
    rows([]);
  });

  it("shows a CURRENT link with its exact locator, revision, SHA-256 and a link to the original revision", () => {
    rows([link(), link({ event_id: "ev-2", family: "schedule", source_locator: "Plan!4", source_document_id: "doc-s", source_revision_id: "rev-s" })]);
    render(<CanonicalStructuredWBSLinksPanel projectId="proj-1" />);
    expect(screen.getByTestId("s7-current-structured-links-count")).toHaveTextContent("2 currently authoritative");
    const budget = screen.getByTestId("s7-current-structured-link-budget");
    expect(budget).toHaveTextContent("Presupuesto!2");
    expect(budget).toHaveTextContent("rev-b");
    expect(budget).toHaveTextContent("a".repeat(64));
    expect(budget).toHaveTextContent("Source content: NOT ASSESSED");
    expect(budget.querySelector("a")).toHaveAttribute("href", "/projects/proj-1/evidence?documentId=doc-b&revisionId=rev-b");
    expect(screen.getByTestId("s7-current-structured-link-schedule")).toHaveTextContent("Plan!4");
  });

  it("never presents a stale event as current and says why", () => {
    rows([link({ state: "STALE_SOURCE" })]);
    render(<CanonicalStructuredWBSLinksPanel projectId="proj-1" />);
    expect(screen.getByTestId("s7-current-structured-links-count")).toHaveTextContent("0 currently authoritative");
    expect(screen.queryByTestId("s7-current-structured-link-budget")).not.toBeInTheDocument();
    expect(screen.getByTestId("s7-historical-structured-link-budget")).toHaveTextContent("not currently authoritative");
    expect(screen.getByTestId("s7-structured-stale-reason")).toBeInTheDocument();
  });

  it("cannot address an event that lacks its document or revision, and claims nothing on error", () => {
    rows([link({ source_revision_id: null })]);
    const { unmount } = render(<CanonicalStructuredWBSLinksPanel projectId="proj-1" />);
    expect(screen.getByText(/cannot be addressed/i)).toBeInTheDocument();
    unmount();
    query.mockReturnValue({ data: undefined, isSuccess: false, isLoading: false, isFetching: false, isError: true, refetch });
    render(<CanonicalStructuredWBSLinksPanel projectId="proj-1" />);
    expect(screen.getByTestId("s7-structured-links-error")).toHaveTextContent("No current links are claimed");
  });

  it("is empty-honest and refreshable; it does not query without a signed-in user", () => {
    render(<CanonicalStructuredWBSLinksPanel projectId="proj-1" />);
    expect(screen.getByText(/No canonical Budget \/ Schedule approvals recorded/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /refresh canonical status/i }));
    expect(refetch).toHaveBeenCalled();
    auth.userId = "";
    render(<CanonicalStructuredWBSLinksPanel projectId="proj-1" />);
    expect(query.mock.calls.at(-1)?.[0].enabled).toBe(false);
  });
});
