/** ACC-01 S7: source-backed approval is durable, reloaded and not automatically current. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, renderWithProviders, screen, waitFor } from "@/src/tests/test-utils";
import type { ProjectWBSAuthority } from "@/lib/api/generated/models";
import type { WBSTreeItem } from "@/hooks/useWBSTree";
import {
  CanonicalTechnicalWBSLinksPanel,
  canonicalTechnicalLinksKey,
} from "./CanonicalTechnicalWBSLinksPanel";

const { api, auth } = vi.hoisted(() => ({
  api: vi.fn(),
  auth: {
    orgId: "clerk-org-A" as string | null,
    userId: "clerk-human-A" as string | null,
    isLoaded: true,
  },
}));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth }));
vi.mock("@/lib/api/client", () => ({ orvalApiClient: (...args: unknown[]) => api(...args) }));

const event = {
  event_id: "event-canonical-1",
  occurred_at: "2026-10-29T15:40:00Z",
  review_event_id: "audit-1",
  technical_document_id: "doc-1",
  technical_revision_id: "rev-trusted-A",
  source_clause_id: "clause-4-1",
  source_section: "4.1",
  wbs_baseline_id: "baseline-A",
  wbs_node_id: "node-1-1",
  current_state: "CURRENT_VERIFIED" as const,
  state_reason: "CURRENT_VERIFIED",
  authority: "EXPLICIT_HUMAN_CANONICAL_LINK" as const,
  approval: "APPROVE_CANONICAL_LINK" as const,
  technical_assessment: "NOT_ASSESSED" as const,
};
const items: WBSTreeItem[] = [{
  id: "root", code: "1", name: "Groundworks", level: 1,
  children: [{ id: "node-1-1", code: "1.1", name: "Concrete", level: 2, children: [] }],
}];
const authority = {
  approved: true,
  display_state: "APPROVED_BASELINE",
  baseline_id: "baseline-A",
} as ProjectWBSAuthority;

describe("CanonicalTechnicalWBSLinksPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    auth.orgId = "clerk-org-A";
    auth.userId = "clerk-human-A";
    auth.isLoaded = true;
    api.mockResolvedValue([event]);
  });

  it("reads the canonical event from authenticated GET after mounting with an empty UI cache", async () => {
    renderWithProviders(
      <CanonicalTechnicalWBSLinksPanel projectId="proj-A" authority={authority} items={items} />,
    );
    expect(await screen.findByTestId("technical-wbs-current-count")).toHaveTextContent(
      "1 currently verified Technical link",
    );
    expect(screen.getByTestId("technical-wbs-canonical-item")).toHaveTextContent(
      "Approved and currently verified",
    );
    expect(screen.getByTestId("technical-wbs-canonical-item")).toHaveTextContent("1.1: Concrete");
    expect(screen.getByTestId("technical-wbs-canonical-item")).toHaveTextContent("NOT ASSESSED");
    expect(screen.getByRole("link", { name: /inspect exact original source revision/i }))
      .toHaveAttribute("href", "/projects/proj-A/evidence?documentId=doc-1&revisionId=rev-trusted-A&highlightId=clause-4-1");
    expect(api).toHaveBeenCalledWith({
      method: "GET",
      url: "/api/v1/projects/proj-A/technical-wbs/canonical-links",
    });
  });

  it("never treats a backend historical event as a current link", async () => {
    api.mockResolvedValue([{ ...event, current_state: "HISTORICAL_NOT_CURRENT", state_reason: "TECHNICAL_REVISION_NOT_TRUSTED" }]);
    renderWithProviders(
      <CanonicalTechnicalWBSLinksPanel projectId="proj-A" authority={authority} items={items} />,
    );
    expect(await screen.findByTestId("technical-wbs-current-count")).toHaveTextContent(
      "0 currently verified Technical links",
    );
    expect(screen.getByTestId("technical-wbs-canonical-item")).toHaveTextContent(
      "Approved historically — not verified current",
    );
    expect(screen.getByTestId("technical-wbs-canonical-item")).not.toHaveTextContent(
      "Approved and currently verified",
    );
  });

  it("does not claim current authority with a stale WBS baseline cache or missing WBS node", async () => {
    const staleAuthority = { ...authority, baseline_id: "baseline-B" };
    const { rerender } = renderWithProviders(
      <CanonicalTechnicalWBSLinksPanel projectId="proj-A" authority={staleAuthority} items={items} />,
    );
    await waitFor(() => expect(screen.getByTestId("technical-wbs-current-count")).toHaveTextContent("0 currently verified"));
    rerender(<CanonicalTechnicalWBSLinksPanel projectId="proj-A" authority={authority} items={[]} />);
    expect(screen.getByTestId("technical-wbs-current-count")).toHaveTextContent("0 currently verified");
  });

  it("shows read errors rather than inventing 0 results or a trusted association", async () => {
    api.mockRejectedValueOnce(new Error("401 unauthorized"));
    renderWithProviders(
      <CanonicalTechnicalWBSLinksPanel projectId="proj-A" authority={authority} items={items} />,
    );
    expect(await screen.findByTestId("technical-wbs-canonical-read-error")).toHaveTextContent(
      /could not be verified/i,
    );
    expect(screen.queryByTestId("technical-wbs-current-count")).not.toBeInTheDocument();
    expect(screen.queryByTestId("technical-wbs-canonical-empty")).not.toBeInTheDocument();
  });

  it("requires loaded Clerk identity and scopes cache by project, organization and actor", () => {
    expect(canonicalTechnicalLinksKey("org-A", "user-A", "project-A")).not.toEqual(
      canonicalTechnicalLinksKey("org-B", "user-B", "project-A"),
    );
    auth.isLoaded = false;
    renderWithProviders(
      <CanonicalTechnicalWBSLinksPanel projectId="proj-A" authority={authority} items={items} />,
    );
    expect(api).not.toHaveBeenCalled();
    expect(screen.queryByTestId("technical-wbs-current-count")).not.toBeInTheDocument();
  });

  it("refreshes durable approval history instead of relying on local POST state", async () => {
    api.mockResolvedValueOnce([]).mockResolvedValueOnce([event]);
    renderWithProviders(
      <CanonicalTechnicalWBSLinksPanel projectId="proj-A" authority={authority} items={items} />,
    );
    expect(await screen.findByTestId("technical-wbs-canonical-empty")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("technical-wbs-refresh-approved"));
    expect(await screen.findByTestId("technical-wbs-canonical-item")).toHaveTextContent(
      "Approved and currently verified",
    );
    expect(api).toHaveBeenCalledTimes(2);
  });
});
