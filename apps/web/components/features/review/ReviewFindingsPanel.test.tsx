/** S5: per-finding decisions are provisional, attributed server-side, and echo the server's own pins. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosError } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReviewFindingsPanel } from "./ReviewFindingsPanel";
import { reviewFindingsKey } from "./useReviewCapabilities";

const { list, record, derive, auth } = vi.hoisted(() => ({
  list: vi.fn(),
  record: vi.fn(),
  derive: vi.fn(),
  auth: { orgId: "o", userId: "u", isLoaded: true },
}));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth }));
vi.mock("@/lib/api/generated/hitl-findings/hitl-findings", () => ({
  listReviewFindingsApiV1HitlReviewsReviewRowIdFindingsGet: (...args: unknown[]) => list(...args),
  recordFindingDecisionApiV1HitlReviewsReviewRowIdFindingsDecisionsPost: (...args: unknown[]) => record(...args),
  deriveCandidateApiV1HitlReviewsReviewRowIdDerivedCandidatePost: (...args: unknown[]) => derive(...args),
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

function renderPanel(onReadinessChange?: (ready: boolean) => void) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ReviewFindingsPanel reviewRowId={ROW} onReadinessChange={onReadinessChange} />
    </QueryClientProvider>,
  );
}

describe("ReviewFindingsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    list.mockResolvedValue(view());
    record.mockResolvedValue({ event_id: "e", ledger_revision: 1, replayed: false });
  });

  it("blocks final approval until every risk is individually confirmed and reports readiness", async () => {
    const onReady = vi.fn();
    const confirmed = { action: "CONFIRMED", reason: null, proposed_text: null };
    list.mockResolvedValue(view({ findings: [finding(0, { current: confirmed }), finding(1)] }));
    const { rerender } = renderPanel(onReady);
    expect(await screen.findByTestId(`review-findings-progress-${ROW}`)).toHaveTextContent("1/2");
    await waitFor(() => expect(onReady).toHaveBeenLastCalledWith(false));
    expect(screen.getByTestId(`review-findings-progress-${ROW}`)).toHaveTextContent(/final approval remains blocked/i);
    rerender(<></>);
  });

  it("does not silently hide the findings when their API request fails", async () => {
    list.mockRejectedValue(new Error("Not found"));
    renderPanel(vi.fn());
    expect(await screen.findByTestId(`review-findings-error-${ROW}`)).toHaveTextContent(/could not be loaded/i);
    expect(screen.getByRole("button", { name: /retry loading findings/i })).toBeInTheDocument();
  });

  it("reports readiness only for an entirely confirmed candidate", async () => {
    const onReady = vi.fn();
    const confirmed = { action: "CONFIRMED", reason: null, proposed_text: null };
    list.mockResolvedValue(view({ findings: [finding(0, { current: confirmed }), finding(1, { current: confirmed })] }));
    renderPanel(onReady);
    await screen.findByTestId("finding-0");
    await waitFor(() => expect(onReady).toHaveBeenLastCalledWith(true));
  });

  it("S5-02: a reader without REVIEW_FINDING sees the findings but cannot record decisions, and is told why", async () => {
    list.mockResolvedValue(
      view({ capabilities: { mode: "enforce", read_review: true, review_finding: false, approve_candidate: false } }),
    );
    renderPanel();
    expect(await screen.findByTestId(`review-findings-readonly-${ROW}`)).toBeInTheDocument();
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled();
    expect(screen.getByTestId("finding-action-1-DISMISSED")).toBeDisabled();
  });

  it("S5-02: a findings read without capabilities hides nothing (it is only a hint; the server decides)", async () => {
    list.mockResolvedValue(view({ capabilities: null }));
    renderPanel();
    await screen.findByTestId("finding-0");
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeEnabled();
    expect(screen.queryByTestId(`review-findings-readonly-${ROW}`)).toBeNull();
  });

  it("lists the findings and says every decision is provisional and separate from the final approval", async () => {
    renderPanel();
    expect(await screen.findByTestId(`review-findings-${ROW}`)).toHaveTextContent("2 findings in this analysis");
    expect(screen.getByTestId(`review-findings-scope-${ROW}`)).toHaveTextContent(/do not approve, reject or trust the analysis/i);
    expect(screen.getByTestId("finding-0")).toHaveTextContent("Risk 0");
    expect(screen.getByTestId("finding-current-1")).toHaveTextContent("No decision yet");
  });

  describe("contract traceability (clause reference and quoted text, apart from the generated description)", () => {
    const QUOTE = "The Contractor shall achieve the structural milestone within 120 days of commencement.";
    const traced = (risk: object) => view({ findings: [finding(0, { risk: { title: "Milestone", description: "A generated summary.", category: "SCHEDULE", ...risk } })] });

    it("shows the clause reference and the verified quote, each apart from the AI-generated description", async () => {
      list.mockResolvedValue(traced({ clause_ref: "3.2", source_quote: QUOTE, source_quote_status: "VERIFIED" }));
      renderPanel();
      await screen.findByTestId("finding-0");
      expect(screen.getByTestId("finding-clause-0")).toHaveTextContent("Contract reference: Clause 3.2");
      expect(screen.getByTestId("finding-quote-0")).toHaveTextContent(QUOTE);
      expect(screen.getByTestId("finding-description-0")).toHaveTextContent("Analysis (AI-generated): A generated summary.");
      expect(screen.getByTestId("finding-description-0")).not.toHaveTextContent(QUOTE);
      expect(screen.getByTestId("finding-trace-0")).toHaveTextContent(/found verbatim in the document/i);
      expect(screen.queryByTestId("finding-quote-missing-0")).toBeNull();
    });

    it("never shows text as a quotation unless the server verified it: a withheld quote says so", async () => {
      list.mockResolvedValue(
        traced({ clause_ref: "3.1", source_quote: "Sneaked in by a client bug", source_quote_status: "NOT_FOUND_IN_DOCUMENT" }),
      );
      renderPanel();
      await screen.findByTestId("finding-0");
      expect(screen.queryByTestId("finding-quote-0")).toBeNull();
      expect(screen.getByTestId("finding-quote-missing-0")).toHaveTextContent(/not found verbatim in the document/i);
      expect(screen.getByTestId("finding-trace-0")).not.toHaveTextContent("Sneaked in by a client bug");
    });

    it("a quote without a VERIFIED status is not shown either, and a missing clause reference is stated, not invented", async () => {
      list.mockResolvedValue(traced({ source_quote: QUOTE }));
      renderPanel();
      await screen.findByTestId("finding-0");
      expect(screen.queryByTestId("finding-quote-0")).toBeNull();
      expect(screen.getByTestId("finding-quote-missing-0")).toHaveTextContent("No quote available for this finding.");
      expect(screen.getByTestId("finding-clause-0")).toHaveTextContent("none given by the analysis");
    });
  });

  describe("derived candidate Vn+1 after a DISMISSED / CORRECTION_PROPOSED decision", () => {
    const decision = (action: string) => ({
      event_id: "e", ledger_revision: 3, action, reason: "no verified quote", proposed_text: null,
      reviewer_id: "u", recorded_at: null,
    });
    const dismissed = () =>
      view({
        ledger_revision: 3,
        findings: [
          finding(0, { current: decision("CONFIRMED") }),
          finding(1, { current: decision("DISMISSED") }),
        ],
      });

    it("offers nothing while no finding is dismissed or corrected", async () => {
      list.mockResolvedValue(view({ findings: [finding(0, { current: decision("CONFIRMED") })] }));
      renderPanel();
      await screen.findByTestId("finding-0");
      expect(screen.queryByTestId(`derive-start-${ROW}`)).toBeNull();
    });

    it("is hidden from a reader without REVIEW_FINDING", async () => {
      list.mockResolvedValue({
        ...dismissed(),
        capabilities: { mode: "enforce", read_review: true, review_finding: false, approve_candidate: false },
      });
      renderPanel();
      await screen.findByTestId("finding-0");
      expect(screen.queryByTestId(`derive-start-${ROW}`)).toBeNull();
    });

    it("asks for explicit confirmation, then sends the SERVER's candidate hash and ledger head and shows Vn+1 as PROPOSED", async () => {
      list.mockResolvedValue(dismissed());
      derive.mockResolvedValue({
        review_row_id: ROW, source_artifact_id: "art-1", source_artifact_version: 2, source_artifact_hash: "a".repeat(64),
        derived_artifact_id: "art-2", derived_artifact_version: 3, derived_artifact_hash: "b".repeat(64),
        reconciliation_digest: "d", source_ledger_revision: 3, retained: 1, excluded: 1, corrected: 0, replayed: false,
        event_id: "ev", scoring_state: "PENDING_REEVALUATION", derived_state: "PROPOSED",
      });
      renderPanel();
      await userEvent.click(await screen.findByTestId(`derive-start-${ROW}`));
      expect(derive).not.toHaveBeenCalled();
      await userEvent.click(screen.getByTestId(`derive-confirm-${ROW}`));
      await waitFor(() => expect(derive).toHaveBeenCalledTimes(1));
      expect(derive).toHaveBeenCalledWith(ROW, { source_artifact_hash: "a".repeat(64), expected_ledger_revision: 3 });
      expect(await screen.findByTestId(`derived-result-${ROW}`)).toHaveTextContent("version 3 (PROPOSED)");
      expect(screen.getByTestId(`derived-counts-${ROW}`)).toHaveTextContent("Kept 1, excluded 1, corrected 0");
      expect(screen.getByTestId(`derived-result-${ROW}`)).toHaveTextContent(/nothing was approved or trusted/i);
    });

    it("fails closed and shows the server's own reason when it refuses the derivation", async () => {
      list.mockResolvedValue(dismissed());
      derive.mockRejectedValue(
        new AxiosError("Conflict", "ERR_BAD_REQUEST", undefined, undefined, {
          status: 409,
          data: { detail: { code: "undecided_findings", message: "Two findings still have no decision.", blockers: [] } },
        } as never),
      );
      renderPanel();
      await userEvent.click(await screen.findByTestId(`derive-start-${ROW}`));
      await userEvent.click(screen.getByTestId(`derive-confirm-${ROW}`));
      expect(await screen.findByTestId(`derive-refused-${ROW}`)).toHaveTextContent(/Two findings still have no decision\. Nothing was derived/);
      expect(screen.queryByTestId(`derived-result-${ROW}`)).toBeNull();
    });
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

  it("S5 runner race: a card mounted before the candidate was replaced first paints the CACHED empty read, then the fresh findings", async () => {
    // Hypothesis of run 41404854469: the review was painted while its candidate listed no findings (read cached), the
    // controlled candidate was seeded afterwards, and the panel is mounted again with the stale read still cached.
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(reviewFindingsKey(auth.orgId, auth.userId, ROW), view({ findings: [] }));
    let fresh: (value: unknown) => void = () => undefined;
    list.mockImplementation(() => new Promise((resolve) => { fresh = resolve; }));
    render(
      <QueryClientProvider client={client}>
        <ReviewFindingsPanel reviewRowId={ROW} />
      </QueryClientProvider>,
    );
    // First paint: the panel is already visible (not loading) and shows ZERO findings -- the state a runner must not trust.
    expect(await screen.findByTestId(`review-findings-empty-${ROW}`)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Findings of this analysis" })).toBeInTheDocument();
    expect(screen.queryAllByTestId(/^finding-\d+$/)).toHaveLength(0);
    // The fresh read (five findings) arrives while the panel is on screen and replaces it.
    fresh(view({ findings: [finding(0), finding(1), finding(2), finding(3), finding(4)] }));
    await waitFor(() => expect(screen.getAllByTestId(/^finding-\d+$/)).toHaveLength(5));
    expect(screen.queryByTestId(`review-findings-empty-${ROW}`)).toBeNull();
  });
});


describe("ACC-01 compact findings and source contradiction", () => {
  it("shows a short executive view and keeps the full AI analysis and literal evidence behind a disclosure", async () => {
    const full = "The contract exposes the client to additional costs through a fixed retention and an undefined certificate issuance date. ".repeat(7);
    list.mockResolvedValue(view({ findings: [finding(0, {
      risk: {
        title: "Retention release without deadline",
        category: "BUDGET",
        severity: "HIGH",
        description: full,
        mitigation_suggestion: "Negotiate a release deadline and a partial release milestone.",
        clause_ref: "2.3",
        source_quote: "A retention of 5% shall be withheld from each payment.",
        source_quote_status: "VERIFIED",
      },
    })] }));
    renderPanel();
    const executive = await screen.findByTestId("finding-brief-0");
    expect(executive.textContent?.length).toBeLessThan(220);
    expect(screen.getByTestId("finding-action-summary-0")).toHaveTextContent("Negotiate a release deadline");
    expect(screen.getByTestId("finding-evidence-0")).not.toHaveAttribute("open");
    await userEvent.click(screen.getByText("View evidence and full AI analysis"));
    expect(screen.getByTestId("finding-evidence-0")).toHaveAttribute("open");
    expect(screen.getByTestId("finding-description-0")).toHaveTextContent(full.trim());
    expect(screen.getByTestId("finding-quote-0")).toHaveTextContent("A retention of 5%");
  });

  it("refuses a one-click confirmation when the verified 5.2 source provides a fourteen-day deadline", async () => {
    list.mockResolvedValue(view({ findings: [finding(0, {
      risk: {
        title: "Defect rectification",
        category: "QUALITY", severity: "HIGH", clause_ref: "5.2",
        description: "There is no agreed timeframe for the Contractor to rectify defects.",
        source_quote: "Defective work identified during inspection shall be rectified at the Contractor's cost within fourteen (14) days of written notice.",
        source_quote_status: "VERIFIED",
      },
    })] }));
    renderPanel();
    const warning = await screen.findByTestId("finding-source-conflict-0");
    expect(warning).toHaveTextContent(/verified contract quotation/i);
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled();
    expect(screen.getByTestId("finding-action-0-CORRECTION_PROPOSED")).toBeEnabled();
    expect(record).not.toHaveBeenCalled();
  });

  it("does not invent a source contradiction when the purported quote is unverified", async () => {
    list.mockResolvedValue(view({ findings: [finding(0, {
      risk: {
        title: "Defect rectification",
        description: "No agreed timeframe is defined.",
        source_quote: "within fourteen (14) days of written notice",
        source_quote_status: "NOT_FOUND_IN_DOCUMENT",
      },
    })] }));
    renderPanel();
    await screen.findByTestId("finding-0");
    expect(screen.queryByTestId("finding-source-conflict-0")).toBeNull();
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeEnabled();
  });
});
