/** S5: per-finding decisions are provisional, attributed server-side, and echo the server's own pins. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosError } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReviewFindingsPanel } from "./ReviewFindingsPanel";

const { list, record, auth } = vi.hoisted(() => ({
  list: vi.fn(),
  record: vi.fn(),
  auth: { orgId: "o", userId: "u", isLoaded: true },
}));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth }));
vi.mock("@/lib/api/generated/hitl-findings/hitl-findings", () => ({
  listReviewFindingsApiV1HitlReviewsReviewRowIdFindingsGet: (...args: unknown[]) => list(...args),
  recordFindingDecisionApiV1HitlReviewsReviewRowIdFindingsDecisionsPost: (...args: unknown[]) => record(...args),
}));

const ROW = "row-1";
const finding = (ordinal: number, over: object = {}) => ({
  ordinal,
  source_item_id: `risk-sha256:${String(ordinal).repeat(64)}`,
  finding_id: `f${ordinal}`.padEnd(64, "0"),
  risk: { title: `Risk ${ordinal}`, description: `Description ${ordinal}`, category: "TIME", severity: "high" },
  current: null,
  history: [],
  ...over,
});
const view = (over: object = {}) => ({
  review_row_id: ROW,
  artifact_id: "art-1",
  artifact_version: 2,
  artifact_hash: "a".repeat(64),
  document_revision_id: "rev-1",
  generation: 3,
  fencing_token: 10,
  ledger_revision: 0,
  findings: [finding(0), finding(1)],
  decision_scope: "PROVISIONAL_REVIEWER_INTENT",
  final_approval: "SEPARATE_ACT",
  ...over,
});

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ReviewFindingsPanel reviewRowId={ROW} />
    </QueryClientProvider>,
  );
}

describe("ReviewFindingsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    list.mockResolvedValue(view());
    record.mockResolvedValue({ event_id: "e", ledger_revision: 1, replayed: false });
  });

  it("lists the findings and says every decision is provisional and separate from the final approval", async () => {
    renderPanel();
    expect(await screen.findByTestId(`review-findings-${ROW}`)).toHaveTextContent("2 findings in this analysis");
    expect(screen.getByTestId(`review-findings-scope-${ROW}`)).toHaveTextContent(/do not approve, reject or trust the analysis/i);
    expect(screen.getByTestId("finding-0")).toHaveTextContent("Risk 0");
    expect(screen.getByTestId("finding-current-1")).toHaveTextContent("No decision yet");
  });

  it("confirms a finding with the server's own pins and no actor field", async () => {
    renderPanel();
    await userEvent.click(await screen.findByTestId("finding-action-0-CONFIRMED"));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(1));
    const [rowId, body] = record.mock.calls[0];
    expect(rowId).toBe(ROW);
    expect(body).toMatchObject({
      artifact_id: "art-1",
      artifact_version: 2,
      artifact_hash: "a".repeat(64),
      document_revision_id: "rev-1",
      generation: 3,
      fencing_token: 10,
      ordinal: 0,
      action: "CONFIRMED",
      expected_ledger_revision: 0,
      reason: null,
      proposed_text: null,
    });
    expect(body.idempotency_key.length).toBeGreaterThanOrEqual(8);
    expect(Object.keys(body)).not.toContain("reviewer_id");
    expect(Object.keys(body)).not.toContain("tenant_id");
  });

  it("will not submit a dismissal or a correction without the reason (and text) the API requires", async () => {
    renderPanel();
    await userEvent.click(await screen.findByTestId("finding-action-1-DISMISSED"));
    const submit = screen.getByTestId("finding-submit-1");
    expect(submit).toBeDisabled();
    await userEvent.type(screen.getByTestId("finding-reason-1"), "waived by the owner");
    expect(submit).toBeEnabled();
    await userEvent.click(submit);
    await waitFor(() => expect(record).toHaveBeenCalledTimes(1));
    expect(record.mock.calls[0][1]).toMatchObject({ ordinal: 1, action: "DISMISSED", reason: "waived by the owner", proposed_text: null });

    await userEvent.click(screen.getByTestId("finding-action-0-CORRECTION_PROPOSED"));
    await userEvent.type(screen.getByTestId("finding-reason-0"), "wrong date");
    expect(screen.getByTestId("finding-submit-0")).toBeDisabled();
    await userEvent.type(screen.getByTestId("finding-text-0"), "Penalty applies after 30/09/2027");
    expect(screen.getByTestId("finding-submit-0")).toBeEnabled();
  });

  it("shows the recorded decision as provisional, with its reason and how many decisions exist", async () => {
    list.mockResolvedValue(
      view({
        ledger_revision: 2,
        findings: [
          finding(0, {
            current: { event_id: "e2", ledger_revision: 2, action: "DISMISSED", reason: "not applicable", reviewer_id: "u" },
            history: [
              { event_id: "e1", ledger_revision: 1, action: "NEEDS_INFO", reason: "ask legal", reviewer_id: "u" },
              { event_id: "e2", ledger_revision: 2, action: "DISMISSED", reason: "not applicable", reviewer_id: "u" },
            ],
          }),
        ],
      }),
    );
    renderPanel();
    expect(await screen.findByTestId("finding-current-0")).toHaveTextContent("Dismissed (provisional)");
    expect(screen.getByTestId("finding-0")).toHaveTextContent("Reason: not applicable");
    expect(screen.getByTestId("finding-0")).toHaveTextContent("2 decisions recorded; the latest stands.");
  });

  it("says plainly what a refusal means and refreshes instead of guessing", async () => {
    const refusal = new AxiosError("conflict", "409", undefined, undefined, {
      status: 409,
      data: { detail: { code: "stale_ledger_revision" } },
    } as never);
    record.mockRejectedValue(refusal);
    renderPanel();
    await userEvent.click(await screen.findByTestId("finding-action-0-CONFIRMED"));
    expect(await screen.findByTestId(`review-findings-refused-${ROW}`)).toHaveTextContent(/Another decision was recorded meanwhile/);
    await waitFor(() => expect(list.mock.calls.length).toBeGreaterThan(1));
  });

  it("renders nothing for a review that is not a candidate-bound analysis (the API answers 404)", async () => {
    list.mockRejectedValue(new AxiosError("nf", "404", undefined, undefined, { status: 404, data: {} } as never));
    const { container } = renderPanel();
    await waitFor(() => expect(list).toHaveBeenCalled());
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("states honestly when the candidate lists no individual findings", async () => {
    list.mockResolvedValue(view({ findings: [] }));
    renderPanel();
    expect(await screen.findByTestId(`review-findings-empty-${ROW}`)).toHaveTextContent(/lists no individual findings/i);
  });
});
