/** S7: the approved baseline, its revision and who approved it -- self-approval is never shown as independent. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { CanonicalWBSBaselinePanel } from "./CanonicalWBSBaselinePanel";
import type { ProjectWBSAuthority } from "@/lib/api/generated/models";

const { query, auth } = vi.hoisted(() => ({
  query: vi.fn(),
  auth: { orgId: "org-1", userId: "user-1", isLoaded: true },
}));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth }));
vi.mock("@tanstack/react-query", () => ({ useQuery: (args: unknown) => query(args) }));
vi.mock("@/lib/api/client", () => ({ orvalApiClient: vi.fn() }));

const approved = {
  state: "APPROVED_BASELINE",
  display_state: "APPROVED_BASELINE",
  approved: true,
  scope_label: "Approved WBS Baseline #1",
  baseline_id: "b-1",
  baseline_no: 1,
  tree_digest: "sha256:287f95d8c247240126fca993bec9e0e8",
  applied_at: "2026-11-01T09:30:00Z",
  draft_exists: false,
} as unknown as ProjectWBSAuthority;

const baseline = (self: boolean) => ({
  id: "b-1",
  baseline_no: 1,
  parent_baseline_id: null,
  source_change_set_id: "cs-1",
  tree_digest: "sha256:287f95d8c247240126fca993bec9e0e8",
  change_set_digest: "c".repeat(64),
  node_count: 2,
  self_approved: self,
  applied_at: "2026-11-01T09:30:00Z",
});

const state = (over: object) =>
  query.mockReturnValue({ data: undefined, isLoading: false, isError: false, isSuccess: true, ...over });

describe("CanonicalWBSBaselinePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    state({ data: [baseline(true)] });
  });

  it("says plainly when there is no approved baseline and does not query", () => {
    render(<CanonicalWBSBaselinePanel projectId="p" authority={{ ...approved, approved: false } as ProjectWBSAuthority} />);
    expect(screen.getByTestId("s7-baseline-none")).toHaveTextContent("No approved WBS baseline");
    expect(query.mock.calls[0][0].enabled).toBe(false);
  });

  it("shows baseline number, revision digest and node count", () => {
    render(<CanonicalWBSBaselinePanel projectId="p" authority={approved} />);
    expect(screen.getByTestId("s7-baseline-label")).toHaveTextContent("Approved WBS Baseline #1 · state APPROVED_BASELINE");
    expect(screen.getByTestId("s7-baseline-revision")).toHaveTextContent("baseline #1");
    expect(screen.getByTestId("s7-baseline-revision")).toHaveTextContent("287f95d8c247");
    expect(screen.getByTestId("s7-baseline-revision")).toHaveTextContent("2 nodes");
  });

  it("labels a self-approval SELF_APPROVED_NOT_INDEPENDENT, never as an independent approval", () => {
    render(<CanonicalWBSBaselinePanel projectId="p" authority={approved} />);
    expect(screen.getByTestId("s7-baseline-approval")).toHaveTextContent("SELF_APPROVED_NOT_INDEPENDENT");
    expect(screen.getByTestId("s7-baseline-approval")).not.toHaveTextContent("(independent approval)");
  });

  it("labels a distinct approver as independent", () => {
    state({ data: [baseline(false)] });
    render(<CanonicalWBSBaselinePanel projectId="p" authority={approved} />);
    expect(screen.getByTestId("s7-baseline-approval")).toHaveTextContent("independent approval");
    expect(screen.getByTestId("s7-baseline-approval")).not.toHaveTextContent("SELF_APPROVED");
  });

  it("claims no authority when the approval cannot be verified or is absent from the governed list", () => {
    state({ data: undefined, isError: true, isSuccess: false });
    const { unmount } = render(<CanonicalWBSBaselinePanel projectId="p" authority={approved} />);
    expect(screen.getByTestId("s7-baseline-error")).toHaveTextContent("No approval authority is claimed");
    unmount();
    state({ data: [] });
    render(<CanonicalWBSBaselinePanel projectId="p" authority={approved} />);
    expect(screen.getByTestId("s7-baseline-missing")).toBeInTheDocument();
    expect(screen.queryByTestId("s7-baseline-approval")).not.toBeInTheDocument();
  });
});
