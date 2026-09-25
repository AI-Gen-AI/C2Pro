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
});
