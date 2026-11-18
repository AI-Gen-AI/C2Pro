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
  risk: {
    title: `Risk ${ordinal}`, description: `Description ${ordinal}`, category: "TIME", severity: "high",
    source_quote_status: "VERIFIED",
    source_quote: `Contract clause ${ordinal}: Contractor must comply with the agreed milestone.`,
  },
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

async function acknowledgeQuote(ordinal = 0) {
  const checkbox = await screen.findByTestId(`finding-source-reviewed-${ordinal}`);
  await waitFor(() => expect(checkbox).toBeEnabled());
  if (!("checked" in checkbox && checkbox.checked)) await userEvent.click(checkbox);
}

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
    renderPanel(onReady);
    expect(await screen.findByTestId(`review-findings-progress-${ROW}`)).toHaveTextContent("1/2");
    await waitFor(() => expect(onReady).toHaveBeenLastCalledWith(false));
    expect(screen.getByTestId(`review-findings-progress-${ROW}`)).toHaveTextContent(/final approval remains blocked/i);
  });

  it("does not silently hide the findings when their API request fails", async () => {
    list.mockRejectedValue(new Error("Not found"));
    renderPanel(vi.fn());
    expect(await screen.findByTestId(`review-findings-error-${ROW}`)).toHaveTextContent(/findings are unavailable for this review/i);
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
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled();
    await acknowledgeQuote();
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
      expect(screen.getByTestId("finding-trace-0")).toHaveTextContent(/literal match in the analyzed text/i);
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
    await acknowledgeQuote();
    await userEvent.click(screen.getByTestId("finding-action-0-CONFIRMED"));
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

  it("replays an uncertain CONFIRMED with the same idempotency key and exact original CAS pins", async () => {
    // Simulate a response lost AFTER the server may have committed: the GET then
    // returns a newer ledger head. Repeating the POST must still replay the original.
    list.mockResolvedValueOnce(view()).mockResolvedValue(view({ ledger_revision: 3 }));
    record.mockRejectedValueOnce(new Error("Response lost after server commit"));
    renderPanel();

    await acknowledgeQuote();
    await userEvent.click(screen.getByTestId("finding-action-0-CONFIRMED"));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(1));
    const first = record.mock.calls[0][1];
    expect(await screen.findByTestId(`review-findings-refused-${ROW}`)).toBeInTheDocument();
    await waitFor(() => expect(list.mock.calls.length).toBeGreaterThan(1));

    await userEvent.click(screen.getByTestId("finding-action-0-CONFIRMED"));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(2));
    const retried = record.mock.calls[1][1];
    expect(retried).toEqual(first);
    expect(retried.expected_ledger_revision).toBe(0);
    expect(retried.idempotency_key).toBe(first.idempotency_key);
  });

  it("starts a new CONFIRMED request only after an explicit stale-ledger 409 and refreshed server view", async () => {
    const stale = new AxiosError("Conflict", "ERR_BAD_REQUEST", undefined, undefined, {
      status: 409, data: { detail: { code: "stale_ledger_revision" } },
    } as never);
    list.mockResolvedValueOnce(view()).mockResolvedValue(view({ ledger_revision: 3 }));
    record.mockRejectedValueOnce(stale);
    renderPanel();

    await acknowledgeQuote();
    await userEvent.click(screen.getByTestId("finding-action-0-CONFIRMED"));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(1));
    const first = record.mock.calls[0][1];
    expect(await screen.findByTestId(`review-findings-refused-${ROW}`)).toHaveTextContent(/Another decision was recorded/);
    await waitFor(() => expect(list.mock.calls.length).toBeGreaterThan(1));

    await userEvent.click(screen.getByTestId("finding-action-0-CONFIRMED"));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(2));
    expect(record.mock.calls[1][1].idempotency_key).not.toBe(first.idempotency_key);
    expect(record.mock.calls[1][1].expected_ledger_revision).toBe(3);
  });

  it("replays an uncertain DISMISSED with original body after ledger refresh", async () => {
    list.mockResolvedValueOnce(view()).mockResolvedValue(view({ ledger_revision: 3 }));
    record.mockRejectedValueOnce(new Error("Response lost after server commit"));
    renderPanel();
    await userEvent.click(await screen.findByTestId("finding-action-0-DISMISSED"));
    await userEvent.type(screen.getByTestId("finding-reason-0"), "No verified obligation");
    await userEvent.click(screen.getByTestId("finding-submit-0"));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(1));
    const first = record.mock.calls[0][1];
    expect(await screen.findByTestId(`review-findings-refused-${ROW}`)).toBeInTheDocument();
    await waitFor(() => expect(list.mock.calls.length).toBeGreaterThan(1));
    await userEvent.click(screen.getByTestId("finding-submit-0"));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(2));
    expect(record.mock.calls[1][1]).toEqual(first);
    expect(record.mock.calls[1][1].expected_ledger_revision).toBe(0);
  });

  it("re-bases a DISMISSED decision with a new key after definite stale-ledger 409", async () => {
    list.mockResolvedValueOnce(view()).mockResolvedValue(view({ ledger_revision: 4 }));
    record.mockRejectedValueOnce(new AxiosError("Conflict", "ERR_BAD_REQUEST", undefined, undefined, {
      status: 409, data: { detail: { code: "stale_ledger_revision" } },
    } as never));
    renderPanel();
    await userEvent.click(await screen.findByTestId("finding-action-0-DISMISSED"));
    await userEvent.type(screen.getByTestId("finding-reason-0"), "Document superseded");
    await userEvent.click(screen.getByTestId("finding-submit-0"));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(1));
    const old = record.mock.calls[0][1];
    expect(await screen.findByTestId(`review-findings-refused-${ROW}`)).toHaveTextContent(/Another decision was recorded/);
    await waitFor(() => expect(list.mock.calls.length).toBeGreaterThan(1));
    await userEvent.click(screen.getByTestId("finding-submit-0"));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(2));
    const rebased = record.mock.calls[1][1];
    expect(rebased.idempotency_key).not.toBe(old.idempotency_key);
    expect(rebased.expected_ledger_revision).toBe(4);
  });

  it("never replays a CONFIRMED request into a different reviewRowId on the same artifact", async () => {
    list.mockImplementation((rowId: string) => Promise.resolve(view({ review_row_id: rowId })));
    record.mockRejectedValueOnce(new Error("Lost response"));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const ui = (rowId: string) => (
      <QueryClientProvider client={client}>
        <ReviewFindingsPanel reviewRowId={rowId} />
      </QueryClientProvider>
    );
    const rendered = render(ui(ROW));
    await acknowledgeQuote();
    await userEvent.click(screen.getByTestId("finding-action-0-CONFIRMED"));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(1));
    const first = record.mock.calls[0][1];
    expect(await screen.findByTestId(`review-findings-refused-${ROW}`)).toBeInTheDocument();
    rendered.rerender(ui("row-2"));
    await waitFor(() => expect(list).toHaveBeenCalledWith("row-2", expect.anything()));
    await acknowledgeQuote();
    await userEvent.click(screen.getByTestId("finding-action-0-CONFIRMED"));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(2));
    expect(record.mock.calls[1][0]).toBe("row-2");
    expect(record.mock.calls[1][1].idempotency_key).not.toBe(first.idempotency_key);
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

  it("fails closed when a background findings read errors despite stale cached empty results", async () => {
    const onReady = vi.fn();
    list.mockResolvedValueOnce(view({ findings: [] })).mockRejectedValueOnce(new Error("Network outage"));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ReviewFindingsPanel reviewRowId={ROW} onReadinessChange={onReady} />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(onReady).toHaveBeenLastCalledWith(false));
    await client.invalidateQueries({ queryKey: reviewFindingsKey(auth.orgId, auth.userId, ROW) });
    expect(await screen.findByTestId(`review-findings-error-${ROW}`)).toBeInTheDocument();
    await waitFor(() => expect(onReady).toHaveBeenLastCalledWith(false));
  });

  it("says plainly what a refusal means and refreshes instead of guessing", async () => {
    const refusal = new AxiosError("conflict", "409", undefined, undefined, {
      status: 409,
      data: { detail: { code: "stale_ledger_revision" } },
    } as never);
    record.mockRejectedValue(refusal);
    renderPanel();
    await acknowledgeQuote();
    await userEvent.click(screen.getByTestId("finding-action-0-CONFIRMED"));
    expect(await screen.findByTestId(`review-findings-refused-${ROW}`)).toHaveTextContent(/Another decision was recorded meanwhile/);
    await waitFor(() => expect(list.mock.calls.length).toBeGreaterThan(1));
  });

  it("shows a blocking error and retry when the individual findings API returns 404", async () => {
    list.mockRejectedValue(new AxiosError("nf", "404", undefined, undefined, { status: 404, data: {} } as never));
    renderPanel();
    const error = await screen.findByTestId(`review-findings-error-${ROW}`);
    expect(error).toHaveTextContent(/findings are unavailable/i);
    expect(error).toHaveTextContent(/final approval is unavailable/i);
    expect(screen.getByRole("button", { name: /retry loading findings/i })).toBeInTheDocument();
  });

  it("blocks final approval for an empty findings list without verified analysis coverage", async () => {
    const onReady = vi.fn();
    list.mockResolvedValue(view({ findings: [] }));
    renderPanel(onReady);
    expect(await screen.findByTestId(`review-findings-empty-${ROW}`)).toHaveTextContent(/lists no individual findings/i);
    await waitFor(() => expect(onReady).toHaveBeenLastCalledWith(false));
    expect(screen.getByTestId(`review-findings-progress-${ROW}`)).toHaveTextContent(/final approval remains blocked/i);
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


describe("HITL-UX-01 concise, source-bounded risk review", () => {
  it("shows a short executive view and keeps the full AI analysis and literal evidence behind a disclosure", async () => {
    const full = "The contract exposes the client to additional costs through a fixed retention and an undefined certificate issuance date. ".repeat(7);
    list.mockResolvedValue(view({ findings: [finding(0, {
      risk: {
        title: "Retention release without deadline",
        category: "BUDGET",
        severity: "HIGH",
        description: full,
        mitigation_suggestion: "Negotiate a release deadline and a partial release milestone.",
        consequences: "Retention may stay outstanding until the certificate is issued.",
        financial_impact: "Working capital exposure; amount not quantified.",
        source_locator: "Section 2.3",
        clause_ref: "2.3",
        source_quote: "A retention of 5% shall be withheld from each payment.",
        source_quote_status: "VERIFIED",
      },
    })] }));
    renderPanel();
    const executive = await screen.findByTestId("finding-brief-0");
    expect(executive.textContent?.length).toBeLessThan(220);
    expect(screen.getByTestId("finding-action-summary-0")).toHaveTextContent("Negotiate a release deadline");
    expect(screen.getByTestId("finding-consequences-0")).toHaveTextContent("Retention may stay outstanding");
    expect(screen.getByTestId("finding-impact-0")).toHaveTextContent("amount not quantified");
    expect(screen.getByTestId("finding-original-location-0")).toHaveTextContent("Suggested source location (not independently verified): Section 2.3");
    expect(screen.getByTestId("finding-evidence-0")).not.toHaveAttribute("open");
    await userEvent.click(screen.getByText("View evidence and full AI analysis"));
    expect(screen.getByTestId("finding-evidence-0")).toHaveAttribute("open");
    expect(screen.getByTestId("finding-description-0")).toHaveTextContent(full.trim());
    expect(screen.getByTestId("finding-quote-0")).toHaveTextContent("A retention of 5%");
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled();
    expect(screen.getByTestId("finding-interpretation-warning-0")).toHaveTextContent(/literal match does not validate/i);
    await userEvent.click(screen.getByTestId("finding-source-reviewed-0"));
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeEnabled();
  });

  it("§5.2: demands deliberate source comparison before a provisional confirmation of contradictory AI prose", async () => {
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
    await screen.findByTestId("finding-0");
    expect(screen.getByTestId("finding-quote-0")).toHaveTextContent("within fourteen (14) days");
    expect(screen.getByTestId("finding-brief-0")).toHaveTextContent("no agreed timeframe");
    expect(screen.getByTestId("finding-interpretation-warning-0")).toHaveTextContent(/deadlines, exceptions, amounts/);
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled();
    expect(screen.getByTestId("finding-action-0-CORRECTION_PROPOSED")).toBeEnabled();
    expect(record).not.toHaveBeenCalled();
    await userEvent.click(screen.getByTestId("finding-source-reviewed-0"));
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeEnabled();
    expect(record).not.toHaveBeenCalled();
  });

  it("does not invent a contradiction from linguistic keywords: manual comparison is required, not a legal verdict", async () => {
    list.mockResolvedValue(view({ findings: [finding(0, {
      risk: { title: "Timely cure", description: "The Contractor has a defined cure period.",
        source_quote: "Defects must be rectified within fourteen (14) days of written notice.",
        source_quote_status: "VERIFIED" },
    })] }));
    renderPanel();
    await screen.findByTestId("finding-0");
    expect(screen.queryByTestId("finding-source-conflict-0")).toBeNull();
    expect(screen.getByTestId("finding-interpretation-warning-0")).toHaveTextContent(/not an automated legal determination/i);
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled();
    await userEvent.click(screen.getByTestId("finding-source-reviewed-0"));
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeEnabled();
  });

  it("shows both independent business impact axes without inferring missing currency units", async () => {
    list.mockResolvedValue(view({ findings: [finding(0, {
      risk: { title: "Retention and delay", description: "Impacts projected by the model",
        financial_impact: 120000, schedule_impact: "21 days, unverified" },
    })] }));
    renderPanel();
    await screen.findByTestId("finding-0");
    expect(screen.getByTestId("finding-financial-impact-0")).toHaveTextContent("120000 (unit/currency not supplied)");
    expect(screen.getByTestId("finding-schedule-impact-0")).toHaveTextContent("21 days, unverified");
    expect(screen.getByTestId("finding-impact-0")).toHaveTextContent(/AI claim, unverified/i);
  });

  it("does not confuse legacy impact severity with quantified commercial impact", async () => {
    list.mockResolvedValue(view({ findings: [finding(0, {
      risk: { title: "Delay risk", description: "Potential delay", severity: "HIGH", impact: "HIGH" },
    })] }));
    renderPanel();
    await screen.findByTestId("finding-0");
    expect(screen.getByTestId("finding-0")).toHaveTextContent("HIGH");
    expect(screen.getByTestId("finding-impact-0")).toHaveTextContent("Not quantified in the candidate");
    expect(screen.getByTestId("finding-consequences-0")).toHaveTextContent("Not assessed in the candidate");
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
    expect(screen.queryByTestId("finding-quote-0")).toBeNull();
    expect(screen.getByTestId("finding-no-verified-source-0")).toHaveTextContent(/no server-verified literal quotation/i);
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled();
    expect(screen.getByTestId("finding-action-0-NEEDS_INFO")).toBeEnabled();
    expect(screen.getByTestId("finding-action-0-CORRECTION_PROPOSED")).toBeEnabled();
    expect(record).not.toHaveBeenCalled();
  });
});


/** UX-REG-04 permanent adversarial cases: a checkbox is tied to a complete pinned source, not to a risk digest. */
describe("UX-REG-04 source comparison identity and stale responses", () => {
  const traced = (risk: object = {}) => finding(0, {
    risk: {
      title: "Milestone", description: "Analysis requiring a source comparison", category: "TIME",
      source_quote: "Defects must be corrected within fourteen days.",
      source_quote_status: "VERIFIED", ...risk,
    },
  });
  const candidate = (changes: object = {}) => view({ findings: [traced()], ...changes });
  const key = () => reviewFindingsKey(auth.orgId, auth.userId, ROW);

  function mount() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const panel = () => (
      <QueryClientProvider client={client}>
        <ReviewFindingsPanel reviewRowId={ROW} />
      </QueryClientProvider>
    );
    const rendered = render(panel());
    return { client, rerender: () => rendered.rerender(panel()) };
  }

  async function acknowledge() {
    await screen.findByTestId("finding-source-reviewed-0");
    await userEvent.click(screen.getByTestId("finding-source-reviewed-0"));
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeEnabled();
  }

  beforeEach(() => {
    vi.clearAllMocks();
    auth.orgId = "o";
    auth.userId = "u";
    auth.isLoaded = true;
    list.mockResolvedValue(candidate());
    record.mockResolvedValue({ event_id: "e", ledger_revision: 1, replayed: false });
  });

  it.each([
    ["document revision", { document_revision_id: "rev-2" }],
    ["generation", { generation: 4 }],
    ["fencing token", { fencing_token: 11 }],
    ["artifact version", { artifact_version: 3 }],
    ["artifact identity", { artifact_id: "art-2" }],
    ["artifact digest", { artifact_hash: "b".repeat(64) }],
  ])("requires fresh comparison on %s even with unchanged risk ID and previous digest where applicable", async (_name, change) => {
    list.mockResolvedValueOnce(candidate()).mockResolvedValueOnce(candidate(change));
    const { client } = mount();
    await acknowledge();
    await client.invalidateQueries({ queryKey: key() });
    await waitFor(() => expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled());
    expect(screen.getByTestId("finding-source-reviewed-0")).not.toBeChecked();
    expect(record).not.toHaveBeenCalled();
    await acknowledge();
    await userEvent.click(screen.getByTestId("finding-action-0-CONFIRMED"));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(1));
    expect(record.mock.calls[0][1]).toMatchObject(change);
  });

  it("does not reuse A's acknowledgement after candidate A -> B -> A", async () => {
    list.mockResolvedValueOnce(candidate())
      .mockResolvedValueOnce(candidate({ generation: 4 }))
      .mockResolvedValueOnce(candidate());
    const { client } = mount();
    await acknowledge();
    await client.invalidateQueries({ queryKey: key() });
    await waitFor(() => expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled());
    await client.invalidateQueries({ queryKey: key() });
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled();
    expect(screen.getByTestId("finding-source-reviewed-0")).not.toBeChecked();
  });

  it("disables confirmation during a pending refetch and rejects the old comparison after its response", async () => {
    let respond: ((next: unknown) => void) | undefined;
    list.mockResolvedValueOnce(candidate()).mockImplementationOnce(
      () => new Promise((resolve) => { respond = resolve; }),
    );
    const { client } = mount();
    await acknowledge();
    const refresh = client.invalidateQueries({ queryKey: key() });
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2));
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled();
    expect(screen.getByTestId("finding-source-reviewed-0")).toBeDisabled();
    expect(record).not.toHaveBeenCalled();
    respond?.(candidate({ fencing_token: 12 }));
    await refresh;
    await waitFor(() => expect(screen.getByTestId("finding-source-reviewed-0")).not.toBeChecked());
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled();
  });

  it("clears the comparison on error and requires fresh acknowledgement after retry of the same revision", async () => {
    list.mockResolvedValueOnce(candidate())
      .mockRejectedValueOnce(new Error("source temporarily unavailable"))
      .mockResolvedValueOnce(candidate());
    const { client } = mount();
    await acknowledge();
    await client.invalidateQueries({ queryKey: key() });
    expect(await screen.findByTestId(`review-findings-error-${ROW}`)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /retry loading findings/i }));
    await screen.findByTestId("finding-source-reviewed-0");
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled();
    expect(record).not.toHaveBeenCalled();
  });

  it.each([
    ["document revision", { document_revision_id: null }],
    ["generation", { generation: undefined }],
    ["fencing token", { fencing_token: null }],
    ["artifact identifier", { artifact_id: "" }],
    ["review id mismatch", { review_row_id: "different-row" }],
  ])("fails closed when %s is unavailable or inconsistent", async (_name, change) => {
    list.mockResolvedValue(candidate(change));
    mount();
    expect(await screen.findByTestId("finding-invalid-source-0")).toHaveTextContent(/identity is incomplete/i);
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled();
    expect(screen.getByTestId("finding-source-reviewed-0")).toBeDisabled();
    expect(record).not.toHaveBeenCalled();
  });

  it("does not replay an uncertain old CONFIRMED across new generation or fence", async () => {
    const shifted = candidate({ generation: 5, fencing_token: 13 });
    list.mockResolvedValueOnce(candidate()).mockResolvedValue(shifted);
    record.mockRejectedValueOnce(new Error("response lost"));
    const { client } = mount();
    await acknowledge();
    await userEvent.click(screen.getByTestId("finding-action-0-CONFIRMED"));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(1));
    const old = record.mock.calls[0][1];
    await client.invalidateQueries({ queryKey: key() });
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled();
    await acknowledge();
    await userEvent.click(screen.getByTestId("finding-action-0-CONFIRMED"));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(2));
    const now = record.mock.calls[1][1];
    expect(now).toMatchObject({ generation: 5, fencing_token: 13 });
    expect(now.idempotency_key).not.toBe(old.idempotency_key);
  });

  it("invalidates org and user scope without carrying a previous acknowledgement", async () => {
    const { rerender } = mount();
    await acknowledge();
    auth.orgId = "new-org";
    rerender();
    await waitFor(() => expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled());
    await acknowledge();
    auth.userId = "other-user";
    rerender();
    await waitFor(() => expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeDisabled());
    expect(record).not.toHaveBeenCalled();
  });
});


/** CORE #6993556886: terminal readiness is independent of a historical CONFIRMED label.
 * Neither a missing source pin nor unverified text is evidence of a valid final signature.
 * No test mutates persisted decisions: mocked read model remains the authoritative history.
 */
describe("CORE evidence policy — validated confirmation and final readiness", () => {
  const confirmed = { action: "CONFIRMED", reason: null, proposed_text: null, reviewer_id: "reviewer" };
  const previouslyConfirmed = (ordinal: number, overrides: object = {}) =>
    finding(ordinal, { current: confirmed, ...overrides });
  const complete = (overrides: object = {}) =>
    view({ findings: [previouslyConfirmed(0), previouslyConfirmed(1)], ...overrides });

  beforeEach(() => {
    vi.clearAllMocks();
    auth.orgId = "o";
    auth.userId = "u";
    auth.isLoaded = true;
    record.mockResolvedValue({ event_id: "e", ledger_revision: 1, replayed: false });
    list.mockResolvedValue(complete());
  });

  it.each([
    ["document_revision_id null", { document_revision_id: null }],
    ["document_revision_id blank", { document_revision_id: "" }],
    ["generation null", { generation: null }],
    ["generation not numeric", { generation: "3" }],
    ["generation fractional", { generation: 3.5 }],
    ["generation negative", { generation: -1 }],
    ["fencing_token null", { fencing_token: null }],
    ["fencing_token missing", { fencing_token: undefined }],
    ["fencing_token fractional", { fencing_token: 10.5 }],
    ["fencing_token negative", { fencing_token: -1 }],
    ["review_row_id mismatch", { review_row_id: "unrelated-review" }],
    ["artifact_id empty", { artifact_id: "" }],
    ["artifact_version null", { artifact_version: null }],
    ["artifact_version zero", { artifact_version: 0 }],
  ])("keeps every existing CONFIRMED but refuses final readiness with %s", async (_case, badPin) => {
    const onReady = vi.fn();
    list.mockResolvedValue(complete(badPin));
    renderPanel(onReady);
    expect(await screen.findByTestId("finding-0")).toHaveTextContent("Confirmed (provisional)");
    expect(screen.getByTestId("finding-current-1")).toHaveTextContent("Confirmed (provisional)");
    expect(screen.getByTestId(`review-findings-progress-${ROW}`)).toHaveTextContent("2/2");
    await waitFor(() => expect(onReady).toHaveBeenLastCalledWith(false));
    expect(record).not.toHaveBeenCalled();
  });

  it("rejects final readiness if only one of two historical CONFIRMED risks lacks a VERIFIED literal", async () => {
    const onReady = vi.fn();
    list.mockResolvedValue(complete({
      findings: [
        previouslyConfirmed(0),
        previouslyConfirmed(1, {
          risk: { title: "Risk 1", description: "Claim from an unverified source",
            source_quote: "Text that cannot be relied on", source_quote_status: "NOT_FOUND_IN_DOCUMENT" },
        }),
      ],
    }));
    renderPanel(onReady);
    expect(await screen.findByTestId("finding-current-1")).toHaveTextContent("Confirmed (provisional)");
    expect(screen.getByTestId(`review-findings-progress-${ROW}`)).toHaveTextContent("2/2");
    expect(screen.getByTestId("finding-action-1-CONFIRMED")).toBeDisabled();
    await waitFor(() => expect(onReady).toHaveBeenLastCalledWith(false));
    expect(record).not.toHaveBeenCalled();
  });

  it("allows readiness with nonempty VERIFIED quotations, complete pins and individually CONFIRMED findings", async () => {
    const onReady = vi.fn();
    renderPanel(onReady);
    expect(await screen.findByTestId("finding-current-0")).toHaveTextContent("Confirmed (provisional)");
    expect(screen.getByTestId("finding-quote-1")).toHaveTextContent("Contract clause 1");
    await waitFor(() => expect(onReady).toHaveBeenLastCalledWith(true));
    expect(record).not.toHaveBeenCalled();
  });

  it.each([
    ["no source status", { source_quote: "An unattributed quotation" }],
    ["explicit unverified", { source_quote_status: "UNVERIFIED", source_quote: "Unverified text" }],
    ["literal not found", { source_quote_status: "NOT_FOUND_IN_DOCUMENT", source_quote: "An invented clause" }],
    ["VERIFIED without actual text", { source_quote_status: "VERIFIED", source_quote: "   " }],
  ])("blocks new CONFIRMED when %s, while leaving NEEDS_INFO and correction available", async (_case, risk) => {
    const onReady = vi.fn();
    const base = { title: "Risk 0", description: "Needs a legal source", category: "TIME" };
    list.mockResolvedValue(view({ findings: [finding(0, { risk: { ...base, ...risk } })] }));
    renderPanel(onReady);
    expect(await screen.findByTestId("finding-0")).toHaveTextContent("Risk 0");
    const confirm = screen.getByTestId("finding-action-0-CONFIRMED");
    expect(confirm).toBeDisabled();
    expect(screen.queryByTestId("finding-source-reviewed-0")).toBeNull();
    expect(screen.getByTestId("finding-no-verified-source-0")).toHaveTextContent(/confirmation is blocked/i);
    expect(screen.getByTestId("finding-action-0-NEEDS_INFO")).toBeEnabled();
    expect(screen.getByTestId("finding-action-0-CORRECTION_PROPOSED")).toBeEnabled();
    await userEvent.click(confirm);
    expect(record).not.toHaveBeenCalled();
    await waitFor(() => expect(onReady).toHaveBeenLastCalledWith(false));
    await userEvent.click(screen.getByTestId("finding-action-0-NEEDS_INFO"));
    await userEvent.type(screen.getByTestId("finding-reason-0"), "Please verify the original contract clause");
    await userEvent.click(screen.getByTestId("finding-submit-0"));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(1));
    expect(record.mock.calls[0][1]).toMatchObject({ action: "NEEDS_INFO", reason: "Please verify the original contract clause" });
    expect(record.mock.calls[0][1].action).not.toBe("CONFIRMED");
  });

  it("a verified literal alone is insufficient to create CONFIRMED until human comparison is acknowledged", async () => {
    list.mockResolvedValue(view({ findings: [finding(0)] }));
    renderPanel();
    expect(await screen.findByTestId("finding-action-0-CONFIRMED")).toBeDisabled();
    expect(record).not.toHaveBeenCalled();
    await acknowledgeQuote();
    expect(screen.getByTestId("finding-action-0-CONFIRMED")).toBeEnabled();
    await userEvent.click(screen.getByTestId("finding-action-0-CONFIRMED"));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(1));
    expect(record.mock.calls[0][1]).toMatchObject({ action: "CONFIRMED" });
  });

  it("does not discard a valid historical decision because a different finding needs new evidence", async () => {
    const onReady = vi.fn();
    list.mockResolvedValue(view({
      findings: [previouslyConfirmed(0), finding(1, {
        risk: { title: "Risk 1", description: "No source yet", source_quote_status: "NOT_FOUND_IN_DOCUMENT" },
      })],
    }));
    renderPanel(onReady);
    expect(await screen.findByTestId("finding-current-0")).toHaveTextContent("Confirmed (provisional)");
    expect(screen.getByTestId("finding-current-1")).toHaveTextContent("No decision yet");
    expect(screen.getByTestId("finding-action-1-CONFIRMED")).toBeDisabled();
    expect(screen.getByTestId("finding-action-1-NEEDS_INFO")).toBeEnabled();
    expect(screen.getByTestId("finding-action-1-CORRECTION_PROPOSED")).toBeEnabled();
    expect(screen.getByTestId(`review-findings-progress-${ROW}`)).toHaveTextContent("1/2");
    await waitFor(() => expect(onReady).toHaveBeenLastCalledWith(false));
    expect(record).not.toHaveBeenCalled();
  });
});
