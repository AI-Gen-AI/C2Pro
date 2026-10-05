/**
 * Test Suite ID: TS-P0C-WHAT-CHANGED-UI-001
 * What Changed? states each revision honestly: an analysis error or a pending review is never
 * presented as "no material change", and no-change is only shown for a completed comparison.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@/src/tests/test-utils";

const apiClientGetMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "proj_changes_001" }),
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    get: (...args: unknown[]) => apiClientGetMock(...args),
  },
}));

import ProjectChangesPage from "./page";

type Item = {
  event_id: string;
  occurred_at: string;
  event_type: string;
  state: "processing" | "ready" | "needs_review" | "error";
  change_cause: "BUSINESS_STATE_CHANGED" | "NEWLY_DISCOVERED" | null;
  confidence: number | null;
  document_id: string | null;
  provenance: { target_revision_id?: string; diff_engine_version?: string };
  matcher_status?: "current" | "legacy" | "unsupported" | null;
  legacy_matcher?: boolean;
  qualification_reason?: string | null;
  derivation?: "original" | "recomputed" | "reinterpreted" | null;
  derived_from_event_id?: string | null;
  effective?: boolean | null;
  superseded_by_event_id?: string | null;
};

function item(overrides: Partial<Item>): Item {
  return {
    event_id: `evt-${Math.random().toString(36).slice(2)}`,
    occurred_at: "2026-09-14T10:00:00",
    event_type: "revision.changed",
    state: "ready",
    change_cause: null,
    confidence: 0.9,
    document_id: "doc-1",
    provenance: { target_revision_id: "rev-2", diff_engine_version: "p0c-v1" },
    ...overrides,
  };
}

function timeline(items: Item[]) {
  apiClientGetMock.mockResolvedValue({ data: { items, next_cursor: null } });
}

async function cardFor(testId: string) {
  return within(await screen.findByTestId(testId));
}

describe("ProjectChangesPage — honest revision states", () => {
  beforeEach(() => {
    apiClientGetMock.mockReset();
  });

  it("never presents a failed revision analysis as no material change", async () => {
    timeline([item({ event_id: "evt-error", event_type: "revision.analysis_failed", state: "error", confidence: null })]);

    render(<ProjectChangesPage />);

    const card = await cardFor("change-item-evt-error");
    expect(card.getByText("Revision analysis failed")).toBeInTheDocument();
    expect(card.getByText("Analysis error")).toBeInTheDocument();
    expect(card.queryByText(/no material change/i)).not.toBeInTheDocument();
    expect(card.queryByText(/^no change$/i)).not.toBeInTheDocument();
  });

  it("never presents a change awaiting review as no material change", async () => {
    timeline([item({ event_id: "evt-review", state: "needs_review" })]);

    render(<ProjectChangesPage />);

    const card = await cardFor("change-item-evt-review");
    expect(card.getByText("Change needs review")).toBeInTheDocument();
    expect(card.queryByText(/no material change/i)).not.toBeInTheDocument();
  });

  it("shows no material change only for a completed comparison without a change cause", async () => {
    timeline([item({ event_id: "evt-none", state: "ready", change_cause: null })]);

    render(<ProjectChangesPage />);

    const card = await cardFor("change-item-evt-none");
    expect(card.getByText("No material change found")).toBeInTheDocument();
    expect(card.getByText("No change")).toBeInTheDocument();
  });

  it("names business-state changes and newly discovered facts distinctly", async () => {
    timeline([
      item({ event_id: "evt-business", change_cause: "BUSINESS_STATE_CHANGED" }),
      item({ event_id: "evt-new", change_cause: "NEWLY_DISCOVERED" }),
      item({ event_id: "evt-processing", state: "processing", event_type: "revision.ingested", confidence: null, provenance: {} }),
    ]);

    render(<ProjectChangesPage />);

    expect((await cardFor("change-item-evt-business")).getByText("Project evidence changed")).toBeInTheDocument();
    expect((await cardFor("change-item-evt-new")).getByText("C2Pro learned something new")).toBeInTheDocument();
    const processing = await cardFor("change-item-evt-processing");
    expect(processing.getByText("Revision is being compared")).toBeInTheDocument();
    expect(processing.getByText("Confidence unavailable")).toBeInTheDocument();
    expect(processing.queryByRole("link")).not.toBeInTheDocument();
  });

  it("states that history could not be loaded instead of showing an empty history", async () => {
    apiClientGetMock.mockRejectedValue(new Error("network down"));

    render(<ProjectChangesPage />);

    expect(await screen.findByText(/could not load this project.s change history/i)).toBeInTheDocument();
    expect(screen.queryByText("No history yet")).not.toBeInTheDocument();
  });

  it("labels a legacy-matcher comparison as needing review with its reason", async () => {
    timeline([
      item({
        event_id: "evt-legacy",
        state: "needs_review",
        confidence: null,
        change_cause: null,
        matcher_status: "legacy",
        legacy_matcher: true,
        qualification_reason: "Compared by an older matcher (p0c-structural-l1-v1).",
      }),
    ]);

    render(<ProjectChangesPage />);

    const card = await cardFor("change-item-evt-legacy");
    expect(card.getByText("Older matcher")).toBeInTheDocument();
    expect(card.getByText(/compared by an older matcher/i)).toBeInTheDocument();
    expect(card.getByText("Change needs review")).toBeInTheDocument();
  });

  it("labels an unregistered matcher as unverified, never as legacy", async () => {
    timeline([
      item({
        event_id: "evt-unsupported",
        state: "needs_review",
        confidence: null,
        matcher_status: "unsupported",
        legacy_matcher: false,
        qualification_reason: "Compared by an unregistered engine (x-v9).",
      }),
    ]);

    render(<ProjectChangesPage />);

    const card = await cardFor("change-item-evt-unsupported");
    expect(card.getByText("Unverified matcher")).toBeInTheDocument();
    expect(card.queryByText("Older matcher")).not.toBeInTheDocument();
  });

  it("keeps a superseded legacy result visible as history and links to it exactly", async () => {
    timeline([
      item({
        event_id: "evt-legacy-original",
        state: "needs_review",
        matcher_status: "legacy",
        legacy_matcher: true,
        derivation: "original",
        effective: false,
        superseded_by_event_id: "evt-recomputed",
      }),
      item({
        event_id: "evt-recomputed",
        event_type: "revision.recomputed",
        change_cause: "BUSINESS_STATE_CHANGED",
        matcher_status: "current",
        derivation: "recomputed",
        derived_from_event_id: "evt-legacy-original",
        effective: true,
      }),
    ]);

    render(<ProjectChangesPage />);

    const original = await cardFor("change-item-evt-legacy-original");
    expect(original.getByText(/historical — superseded/i)).toBeInTheDocument();
    expect(original.getByText("Older matcher")).toBeInTheDocument();
    expect(original.getByRole("link")).toHaveAttribute(
      "href",
      "/projects/proj_changes_001/changes/doc-1/rev-2?event=evt-legacy-original",
    );
    const recomputed = await cardFor("change-item-evt-recomputed");
    expect(recomputed.getByText(/recomputed · current matcher/i)).toBeInTheDocument();
    expect(recomputed.queryByText(/historical/i)).not.toBeInTheDocument();
    expect(recomputed.getByRole("link")).toHaveAttribute("href", "/projects/proj_changes_001/changes/doc-1/rev-2");
  });
});
