/**
 * S5: decide FINDING BY FINDING on a pending analysis review.
 *
 * Every decision is PROVISIONAL reviewer intent appended to a ledger by the authenticated human; it does not approve,
 * reject or trust the analysis (that stays the separate Approve / Reject act on the card) and the API says so
 * (`decision_scope`, `final_approval`). The pins echoed back are the server's own read model: the server re-checks
 * them against the pending review, the live processing authority and the exact candidate before it appends.
 */
"use client";

import { useAuth } from "@clerk/nextjs";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  deriveCandidateApiV1HitlReviewsReviewRowIdDerivedCandidatePost,
  listReviewFindingsApiV1HitlReviewsReviewRowIdFindingsGet,
  recordFindingDecisionApiV1HitlReviewsReviewRowIdFindingsDecisionsPost,
} from "@/lib/api/generated/hitl-findings/hitl-findings";
import type {
  DerivedCandidateResponse,
  ReviewFindingResponse,
  ReviewFindingsResponse,
} from "@/lib/api/generated/models";
import type { FindingDecisionAction } from "@/lib/api/generated/models/findingDecisionAction";
import { reviewFindingsKey } from "./useReviewCapabilities";

const ACTION_LABEL: Record<FindingDecisionAction, string> = {
  CONFIRMED: "Approve finding",
  DISMISSED: "Reject finding",
  NEEDS_INFO: "Needs info",
  CORRECTION_PROPOSED: "Propose correction",
};

const RECORDED_LABEL: Record<FindingDecisionAction, string> = {
  CONFIRMED: "Confirmed",
  DISMISSED: "Dismissed",
  NEEDS_INFO: "Needs more information",
  CORRECTION_PROPOSED: "Correction proposed",
};

const REFUSAL: Record<string, string> = {
  stale_ledger_revision: "Another decision was recorded meanwhile. The list was refreshed; decide again.",
  stale_or_unbound_candidate:
    "This analysis changed or was superseded. The list was refreshed; nothing was recorded.",
  idempotency_conflict: "That request was already used with different content. Nothing was recorded.",
  ledger_guard_refused: "The review is no longer pending. Nothing was recorded.",
  reviewer_not_authorized: "Only an active human reviewer of this workspace can record decisions.",
  project_capability_required: "You do not have permission to record decisions on this project's review.",
  review_unavailable: "This review is no longer open. Nothing was recorded.",
};

/** Server-authored refusal of a derivation (409 with a code, a message and the blocking findings): shown as said. */
function derivationRefusalFrom(error: unknown): string {
  if (isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: { code?: string; message?: string } } | undefined)?.detail;
    if (detail?.code && REFUSAL[detail.code]) return REFUSAL[detail.code];
    if (detail?.message) return `${detail.message} Nothing was derived.`;
  }
  return "The corrected candidate could not be derived. Nothing was changed.";
}

function refusalFrom(error: unknown): string {
  if (isAxiosError(error)) {
    const code = (error.response?.data as { detail?: { code?: string } } | undefined)?.detail?.code;
    if (code && REFUSAL[code]) return REFUSAL[code];
  }
  return "The decision could not be recorded.";
}

const needsReason = (action: FindingDecisionAction) => action !== "CONFIRMED";

/** A brief display is not new evidence: the complete model text remains in the disclosure. */
function shortAnalysis(value: unknown): string {
  if (typeof value !== "string") return "";
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= 190) return normalized;
  const firstSentence = normalized.match(/^.{30,190}?[.!?](?=\s|$)/)?.[0];
  if (firstSentence) return firstSentence;
  const lastSpace = normalized.slice(0, 190).lastIndexOf(" ");
  return `${normalized.slice(0, Math.max(100, lastSpace)).trimEnd()}…`;
}

/** A presentation-only scalar. Never assume that an untyped number has units/currency. */
function readable(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return null;
}

function proposedImpact(value: unknown): string {
  const claim = readable(value);
  if (claim === null) return "Not quantified in the candidate.";
  return typeof value === "number" ? `${claim} (unit/currency not supplied)` : claim;
}

/** Manual comparison is bound to the reviewer, pinned revision, processing lease and exact finding.
 * Missing pins fail closed; JSON avoids ambiguous string delimiters. No PDF provenance is asserted.
 */
function sourceComparisonIdentity(
  view: ReviewFindingsResponse,
  finding: ReviewFindingResponse,
  scope: { orgId: string | null | undefined; userId: string | null | undefined; reviewRowId: string },
): string | null {
  const ids = [
    scope.orgId, scope.userId, scope.reviewRowId, view.review_row_id,
    view.artifact_id, view.artifact_hash, view.document_revision_id,
    finding.finding_id, finding.source_item_id,
  ];
  const numbers = [view.artifact_version, view.generation, view.fencing_token, finding.ordinal];
  // Match backend UUID fields and lowercase SHA-256 digest without constraining Clerk IDs.
  // Backend UUID accepts canonical hyphenated and compact 32-hex forms, any UUID version.
  const uuidPattern = /^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32})$/i;
  const artifactUuidValid = typeof view.artifact_id === "string" && uuidPattern.test(view.artifact_id);
  const documentRevisionUuidValid = typeof view.document_revision_id === "string" && uuidPattern.test(view.document_revision_id);
  const artifactHashValid = typeof view.artifact_hash === "string" && /^[0-9a-f]{64}$/.test(view.artifact_hash);
  if (
    ids.some((id) => typeof id !== "string" || !id.trim()) ||
    !artifactUuidValid || !documentRevisionUuidValid || !artifactHashValid ||
    numbers.some((value) => typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) ||
    view.artifact_version < 1 ||
    view.review_row_id !== scope.reviewRowId
  ) return null;
  return JSON.stringify([...ids, ...numbers, finding.risk.source_quote_status, finding.risk.source_quote]);
}

/** A verified literal in analyzed text is not certification of the original PDF. */
function hasVerifiedLiteralSource(finding: ReviewFindingResponse): boolean {
  return finding.risk.source_quote_status === "VERIFIED" &&
    typeof finding.risk.source_quote === "string" &&
    finding.risk.source_quote.trim().length > 0;
}

function newKey(): string {
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  return `finding-${Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("")}`;
}

type Draft = { action: FindingDecisionAction; reason: string; proposedText: string; key: string };
type PendingSubmission = {
  view: ReviewFindingsResponse;
  finding: ReviewFindingResponse;
  draft: Draft;
};

/**
 * Where in the contract a finding comes from, kept apart from the generated description above it: the clause label the analysis
 * assigned and the contract text it rests on. The quote is shown only when the server verified it verbatim against the document;
 * otherwise the reviewer is told there is none and why, never a paraphrase presented as a citation.
 */
function ContractTrace({ ordinal, risk }: { ordinal: number; risk: Record<string, unknown> }) {
  const clause = typeof risk.clause_ref === "string" ? risk.clause_ref.trim() : "";
  const quote = typeof risk.source_quote === "string" ? risk.source_quote.trim() : "";
  const status = typeof risk.source_quote_status === "string" ? risk.source_quote_status : "";
  const proposedLocator = readable(risk.source_locator);
  const proposedPage = readable(risk.page_number);
  const verified = status === "VERIFIED" && quote.length > 0;
  return (
    <div className="mt-2 rounded border border-dashed p-2 text-xs" data-testid={`finding-trace-${ordinal}`}>
      <p data-testid={`finding-clause-${ordinal}`}>
        <span className="font-medium">Contract reference:</span> {clause ? `Clause ${clause}` : "none given by the analysis"}
      </p>
      {verified ? (
        <figure className="mt-1">
          <blockquote className="border-l-2 pl-2 italic" data-testid={`finding-quote-${ordinal}`}>
            {quote}
          </blockquote>
          <figcaption className="mt-0.5 text-muted-foreground">Literal match in the analyzed text; original PDF/page provenance still requires verification.</figcaption>
        </figure>
      ) : (
        <p className="mt-1 text-muted-foreground" data-testid={`finding-quote-missing-${ordinal}`}>
          {status === "NOT_FOUND_IN_DOCUMENT"
            ? "No verified quote: the text the analysis proposed was not found verbatim in the document, so it is not shown."
            : "No quote available for this finding."}
        </p>
      )}
      <p className="mt-1 text-muted-foreground" data-testid={`finding-original-location-${ordinal}`}>
        {proposedLocator || proposedPage
          ? `Suggested source location (not independently verified): ${[proposedLocator, proposedPage ? `page ${proposedPage}` : null].filter(Boolean).join(", ")}`
          : "Original page location not verified; check the source document and revision."}
      </p>
    </div>
  );
}

export function ReviewFindingsPanel({ reviewRowId, onReadinessChange }: { reviewRowId: string; onReadinessChange?: (ready: boolean) => void }) {
  const { orgId, userId, isLoaded } = useAuth();
  const queryClient = useQueryClient();
  const queryKey = reviewFindingsKey(orgId, userId, reviewRowId);
  const query = useQuery({
    queryKey,
    queryFn: ({ signal }) => listReviewFindingsApiV1HitlReviewsReviewRowIdFindingsGet(reviewRowId, signal),
    enabled: Boolean(isLoaded && userId),
    retry: false,
    staleTime: 0,
  });
  // S5-02 (advisory): the capabilities ride on this same read; the server re-validates every action anyway.
  const mayReview = query.data?.capabilities?.review_finding !== false;
  // Revoke all manual comparisons when a candidate moves, including A -> B -> A.
  const currentCandidateKey = query.data
    ? JSON.stringify([
        orgId, userId, reviewRowId, query.data.review_row_id,
        query.data.artifact_id, query.data.artifact_version, query.data.artifact_hash,
        query.data.document_revision_id, query.data.generation, query.data.fencing_token,
      ])
    : null;
  const [drafts, setDrafts] = useState<Record<number, Draft | undefined>>({});
  // A manual source-to-claim comparison is needed for quoted findings, keyed to the exact candidate.
  // This checkbox does not certify a source or authorize a server decision.
  const [sourceReviewed, setSourceReviewed] = useState<Record<string, boolean>>({});
  // Unknown outcomes must be retried with the exact same body (including CAS pins).
  // A definitive conflict, identity switch, or explicit action change starts a new operation.
  const pendingConfirmations = useRef<Record<number, PendingSubmission | undefined>>({});
  const pendingDraftSubmissions = useRef<Record<number, PendingSubmission | undefined>>({});
  useEffect(() => {
    pendingConfirmations.current = {};
    pendingDraftSubmissions.current = {};
    setDrafts({});
    setSourceReviewed({});
    setRefusal(null);
  }, [reviewRowId, orgId, userId, currentCandidateKey, query.isError]);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [confirmingDerive, setConfirmingDerive] = useState(false);
  const [derived, setDerived] = useState<DerivedCandidateResponse | null>(null);
  const [deriveRefusal, setDeriveRefusal] = useState<string | null>(null);

  // Vn+1 is derived from the candidate and ledger head the SERVER reports now, never from values held by the screen.
  const derive = useMutation({
    mutationFn: (view: ReviewFindingsResponse) =>
      deriveCandidateApiV1HitlReviewsReviewRowIdDerivedCandidatePost(reviewRowId, {
        source_artifact_hash: view.artifact_hash,
        expected_ledger_revision: view.ledger_revision,
      }),
    onSuccess: (result) => {
      setDeriveRefusal(null);
      setConfirmingDerive(false);
      setDerived(result);
      void queryClient.invalidateQueries({ queryKey });
    },
    onError: (error) => {
      setDeriveRefusal(derivationRefusalFrom(error));
      setConfirmingDerive(false);
      void queryClient.invalidateQueries({ queryKey });
    },
  });

  const record = useMutation({
    mutationFn: ({ view, finding, draft }: { view: ReviewFindingsResponse; finding: ReviewFindingResponse; draft: Draft }) =>
      recordFindingDecisionApiV1HitlReviewsReviewRowIdFindingsDecisionsPost(reviewRowId, {
        artifact_id: view.artifact_id,
        artifact_version: view.artifact_version,
        artifact_hash: view.artifact_hash,
        document_revision_id: view.document_revision_id,
        generation: view.generation,
        fencing_token: view.fencing_token,
        source_item_id: finding.source_item_id,
        ordinal: finding.ordinal,
        action: draft.action,
        expected_ledger_revision: view.ledger_revision,
        idempotency_key: draft.key,
        reason: needsReason(draft.action) ? draft.reason.trim() : null,
        proposed_text: draft.action === "CORRECTION_PROPOSED" ? draft.proposedText.trim() : null,
      }),
    onSuccess: (_receipt, { view, finding }) => {
      const comparedKey = sourceComparisonIdentity(view, finding, { orgId, userId, reviewRowId });
      if (comparedKey) setSourceReviewed((current) => ({ ...current, [comparedKey]: false }));
      delete pendingConfirmations.current[finding.ordinal];
      delete pendingDraftSubmissions.current[finding.ordinal];
      setRefusal(null);
      setDrafts((current) => ({ ...current, [finding.ordinal]: undefined }));
      void queryClient.invalidateQueries({ queryKey });
    },
    onError: (error, { finding }) => {
      const detail = isAxiosError(error)
        ? (error.response?.data as { detail?: { code?: string } } | undefined)?.detail
        : undefined;
      // These explicit server rejections establish that the old candidate/CAS cannot be
      // replayed. An ambiguous timeout must retain its original request for safe retry.
      if (detail?.code && [
        "stale_ledger_revision", "stale_or_unbound_candidate",
        "idempotency_conflict", "ledger_guard_refused",
      ].includes(detail.code)) {
        delete pendingConfirmations.current[finding.ordinal];
        delete pendingDraftSubmissions.current[finding.ordinal];
        setDrafts((current) => {
          const previous = current[finding.ordinal];
          return previous ? { ...current, [finding.ordinal]: { ...previous, key: newKey() } } : current;
        });
      }
      setRefusal(refusalFrom(error));
      void queryClient.invalidateQueries({ queryKey });
    },
  });

  // Fail closed on every confirmed finding's source identity and literal evidence,
  // even if the read model carries a historical CONFIRMED. Never rewrite the ledger.
  // Backend reconciliation is a separate final-promotion guard.
  const readyForFinalApproval = Boolean(
    isLoaded &&
    userId &&
    query.isSuccess &&
    !query.isError &&
    !query.isFetching &&
    !record.isPending &&
    query.data &&
    query.data.findings.length > 0 &&
    query.data.findings.every((finding) =>
      finding.current?.action === "CONFIRMED" &&
      sourceComparisonIdentity(query.data, finding, { orgId, userId, reviewRowId }) !== null &&
      hasVerifiedLiteralSource(finding),
    ),
  );
  useEffect(() => {
    onReadinessChange?.(readyForFinalApproval);
  }, [readyForFinalApproval, onReadinessChange]);

  if (!isLoaded || !userId || query.isLoading) {
    return <p className="mt-3 text-sm text-muted-foreground" role="status" data-testid={`review-findings-loading-${reviewRowId}`}>Loading individual findings before final approval…</p>;
  }
  if (query.isError || !query.data) {
    return (
      <div className="mt-3 rounded border border-destructive/40 p-3 text-sm" role="alert" data-testid={`review-findings-error-${reviewRowId}`}>
        <p>Findings are unavailable for this review. It may have no eligible analysis candidate, have changed, or be outside your access. Final approval is unavailable; ask the project administrator to verify the source and candidate binding.</p>
        <Button size="sm" variant="outline" className="mt-2" onClick={() => void query.refetch()}>Retry loading findings</Button>
      </div>
    );
  }
  const view = query.data;
  // A DISMISSED / CORRECTION_PROPOSED decision cannot be approved "as is": it calls for the derived candidate Vn+1.
  const needsDerivation = view.findings.some(
    (finding) => finding.current?.action === "DISMISSED" || finding.current?.action === "CORRECTION_PROPOSED",
  );

  return (
    <section
      className="mt-3 rounded-md border bg-muted/30 p-3 text-sm"
      data-testid={`review-findings-${reviewRowId}`}
      aria-label="Findings of this analysis"
    >
      <p className="font-medium">
        {view.findings.length} finding{view.findings.length === 1 ? "" : "s"} in this analysis
      </p>
      <p className="mt-1 text-xs text-muted-foreground" data-testid={`review-findings-scope-${reviewRowId}`}>
        Review every risk separately. Decisions here are provisional notes by you. They do not approve, reject or trust the analysis: that remains the
        separate final Approve all / Reject decision at the bottom. Approving a finding does not mean accepting the project risk.
      </p>
      <p className="mt-2 text-xs font-medium" role="status" data-testid={`review-findings-progress-${reviewRowId}`}>
        {view.findings.filter((finding) => finding.current?.action === "CONFIRMED").length}/{view.findings.length} findings approved individually.
        {readyForFinalApproval ? " Ready for separate final approval." : " Final approval remains blocked: each finding must be confirmed with a complete source identity and a VERIFIED literal quotation; rejected findings require a corrected candidate."}
      </p>
      {view.findings.length === 0 ? (
        <p className="mt-2 text-muted-foreground" data-testid={`review-findings-empty-${reviewRowId}`}>
          This candidate lists no individual findings. Final approval is blocked until the candidate and its analysis coverage can be verified.
        </p>
      ) : null}
      {!mayReview ? (
        <p className="mt-2 text-xs text-muted-foreground" data-testid={`review-findings-readonly-${reviewRowId}`}>
          You can read these findings but you do not have permission to record decisions on this project.
        </p>
      ) : null}
      {refusal ? (
        <p role="alert" className="mt-2 text-destructive" data-testid={`review-findings-refused-${reviewRowId}`}>
          {refusal}
        </p>
      ) : null}
      <ul className="mt-2 space-y-3">
        {view.findings.map((finding) => {
          const draft = drafts[finding.ordinal];
          const title = String(finding.risk.title ?? `Finding ${finding.ordinal + 1}`);
          const brief = shortAnalysis(finding.risk.description);
          const consequence = [finding.risk.consequences, finding.risk.consequence].map(readable).find(Boolean);
          // RiskItem.impact is a legacy severity label: do not report it as quantified business impact.
          const financialImpact = proposedImpact(finding.risk.financial_impact);
          const scheduleImpact = proposedImpact(finding.risk.schedule_impact);
          const sourceComparisonKey = sourceComparisonIdentity(view, finding, { orgId, userId, reviewRowId });
          const quotedSource = hasVerifiedLiteralSource(finding);
          const sourceWasReviewed = sourceComparisonKey !== null && sourceReviewed[sourceComparisonKey] === true;
          // Never confirm from stale cached data during an in-flight refetch.
          const mayConfirmFinding = sourceComparisonKey !== null && !query.isFetching &&
            quotedSource && sourceWasReviewed;
          const suggestion = [finding.risk.mitigation_suggestion, finding.risk.recommended_action, finding.risk.mitigation]
            .find((value) => typeof value === "string" && value.trim().length > 0);
          const clause = typeof finding.risk.clause_ref === "string" ? finding.risk.clause_ref.trim() : "";
          const valid =
            draft !== undefined &&
            (!needsReason(draft.action) || draft.reason.trim().length > 0) &&
            (draft.action !== "CORRECTION_PROPOSED" || draft.proposedText.trim().length > 0);
          return (
            <li key={finding.finding_id} className="rounded border bg-background p-2" data-testid={`finding-${finding.ordinal}`}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{title}</span>
                {finding.risk.category ? <Badge variant="outline">{String(finding.risk.category)}</Badge> : null}
                {finding.risk.severity ? <Badge variant="outline">{String(finding.risk.severity)}</Badge> : null}
                {finding.current ? (
                  <Badge data-testid={`finding-current-${finding.ordinal}`}>
                    {RECORDED_LABEL[finding.current.action]} (provisional)
                  </Badge>
                ) : (
                  <Badge variant="outline" data-testid={`finding-current-${finding.ordinal}`}>
                    No decision yet
                  </Badge>
                )}
              </div>
              {brief ? (
                <p className="mt-2 text-sm text-foreground" data-testid={`finding-brief-${finding.ordinal}`}>
                  {brief}
                </p>
              ) : null}
              {clause ? <p className="mt-1 text-xs text-muted-foreground">Contract clause {clause} (reference proposed by analysis)</p> : null}
              <p className="mt-2 text-sm" data-testid={`finding-consequences-${finding.ordinal}`}>
                <span className="font-medium">Consequences (AI proposal, unverified): </span>{consequence ?? "Not assessed in the candidate."}
              </p>
              <div className="mt-1 space-y-1 text-sm" data-testid={`finding-impact-${finding.ordinal}`}>
                <p data-testid={`finding-financial-impact-${finding.ordinal}`}>
                  <span className="font-medium">Financial impact (AI claim, unverified): </span>{financialImpact}
                </p>
                <p data-testid={`finding-schedule-impact-${finding.ordinal}`}>
                  <span className="font-medium">Schedule impact (AI claim, unverified): </span>{scheduleImpact}
                </p>
              </div>
              <p className="mt-2 text-sm" data-testid={`finding-action-summary-${finding.ordinal}`}>
                <span className="font-medium">Suggested action: </span>
                {typeof suggestion === "string"
                  ? shortAnalysis(suggestion)
                  : "No specific mitigation supplied. Verify the contractual basis before deciding."}
              </p>
              <details className="mt-2 rounded border border-dashed p-2" data-testid={`finding-evidence-${finding.ordinal}`}>
                <summary className="cursor-pointer text-sm font-medium">View evidence and full AI analysis</summary>
                {finding.risk.description ? (
                  <p className="mt-2 whitespace-pre-wrap text-muted-foreground" data-testid={`finding-description-${finding.ordinal}`}>
                    <span className="mr-1 text-xs font-medium uppercase tracking-wide">Analysis (AI-generated):</span>{" "}
                    {String(finding.risk.description)}
                  </p>
                ) : null}
                {typeof suggestion === "string" && shortAnalysis(suggestion) !== suggestion.trim() ? (
                  <p className="mt-2 whitespace-pre-wrap text-muted-foreground" data-testid={`finding-action-detail-${finding.ordinal}`}>
                    <span className="font-medium">Full suggested action: </span>{suggestion}
                  </p>
                ) : null}
              </details>
              <div className="mt-2" data-testid={`finding-source-comparison-${finding.ordinal}`}>
                <p className="text-xs font-medium">Compare the model interpretation with the source evidence before deciding.</p>
                <ContractTrace ordinal={finding.ordinal} risk={finding.risk} />
                {quotedSource ? (
                  <div className="mt-2 space-y-2 rounded border border-amber-400 p-2 text-xs" data-testid={`finding-interpretation-warning-${finding.ordinal}`}>
                    <p role="note">
                      A literal match does not validate the AI interpretation. Check deadlines, exceptions, amounts and
                      conditions against the full clause before confirming. If the model claim conflicts with its quotation,
                      choose Propose correction or Needs info. This is not an automated legal determination.
                    </p>
                    <label className="flex cursor-pointer items-start gap-2">
                      <input
                        type="checkbox"
                        className="mt-0.5"
                        checked={sourceWasReviewed}
                        disabled={sourceComparisonKey === null || query.isFetching}
                        onChange={(event) => {
                          if (!sourceComparisonKey || query.isFetching) return;
                          setSourceReviewed((current) => ({ ...current, [sourceComparisonKey]: event.target.checked }));
                        }}
                        data-testid={`finding-source-reviewed-${finding.ordinal}`}
                      />
                      I have compared the AI claim with the full visible quote for this candidate; confirmation records provisional intent only.
                    </label>
                  </div>
                ) : (
                  <p className="mt-1 text-xs text-muted-foreground" data-testid={`finding-no-verified-source-${finding.ordinal}`}>
                    No server-verified literal quotation is available. Confirmation is blocked until there is a VERIFIED literal quote and you compare it with the AI claim. Choose Needs info or Propose correction; never invent evidence.
                  </p>
                )}
                {!sourceComparisonKey ? (
                  <p role="alert" className="mt-1 text-xs text-destructive" data-testid={`finding-invalid-source-${finding.ordinal}`}>
                    Source or reviewer identity is incomplete. Confirmation is blocked until the exact candidate can be verified.
                  </p>
                ) : null}
              </div>
              {finding.current?.reason ? (
                <p className="mt-1 text-xs">Reason: {finding.current.reason}</p>
              ) : null}
              {finding.current?.proposed_text ? (
                <p className="mt-1 text-xs">Proposed text: {finding.current.proposed_text}</p>
              ) : null}
              {finding.history.length > 1 ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  {finding.history.length} decisions recorded; the latest stands.
                </p>
              ) : null}
              <div className="mt-2 flex flex-wrap gap-2">
                {(Object.keys(ACTION_LABEL) as FindingDecisionAction[]).map((action) => (
                  <Button
                    key={action}
                    size="sm"
                    variant={draft?.action === action ? "default" : "outline"}
                    disabled={record.isPending || query.isFetching || !mayReview || (action === "CONFIRMED" && !mayConfirmFinding)}
                    title={action === "CONFIRMED" && !mayConfirmFinding ? "VERIFIED literal evidence, complete source identity and your comparison are required; otherwise choose Needs info or Propose correction." : undefined}
                    data-testid={`finding-action-${finding.ordinal}-${action}`}
                    onClick={() => {
                      setRefusal(null);
                      if (action === "CONFIRMED") {
                        if (!mayConfirmFinding || !query.isSuccess) return;
                        const previous = pendingConfirmations.current[finding.ordinal];
                        // The same revision may have been refreshed after a lost response.
                        // Replay the exact original request; clear only on success or a
                        // definitive conflict response from the server.
                        const attempt: { view: ReviewFindingsResponse; finding: ReviewFindingResponse; draft: Draft } = previous &&
                          previous.view.review_row_id === reviewRowId &&
                          previous.view.artifact_id === view.artifact_id &&
                          previous.view.artifact_version === view.artifact_version &&
                          previous.view.artifact_hash === view.artifact_hash &&
                          previous.view.document_revision_id === view.document_revision_id &&
                          previous.view.generation === view.generation &&
                          previous.view.fencing_token === view.fencing_token &&
                          previous.finding.finding_id === finding.finding_id
                          ? previous
                          : { view, finding, draft: { action, reason: "", proposedText: "", key: newKey() } };
                        pendingConfirmations.current[finding.ordinal] = attempt;
                        record.mutate(attempt);
                      } else {
                        delete pendingConfirmations.current[finding.ordinal];
                        delete pendingDraftSubmissions.current[finding.ordinal];
                        setDrafts((current) => ({
                          ...current,
                          [finding.ordinal]: { action, reason: "", proposedText: "", key: newKey() },
                        }));
                      }
                    }}
                  >
                    {ACTION_LABEL[action]}
                  </Button>
                ))}
              </div>
              {draft ? (
                <div className="mt-2 space-y-2">
                  <label className="block text-xs font-medium" htmlFor={`finding-reason-${finding.ordinal}`}>
                    Reason ({ACTION_LABEL[draft.action]})
                  </label>
                  <textarea
                    id={`finding-reason-${finding.ordinal}`}
                    data-testid={`finding-reason-${finding.ordinal}`}
                    className="w-full rounded border bg-background p-2"
                    rows={2}
                    value={draft.reason}
                    disabled={record.isPending}
                    onChange={(event) => {
                      const wasPending = Boolean(pendingDraftSubmissions.current[finding.ordinal]);
                      delete pendingDraftSubmissions.current[finding.ordinal];
                      setDrafts((current) => ({
                        ...current,
                        [finding.ordinal]: {
                          ...draft,
                          reason: event.target.value,
                          key: wasPending ? newKey() : draft.key,
                        },
                      }));
                    }}
                  />
                  {draft.action === "CORRECTION_PROPOSED" ? (
                    <>
                      <label className="block text-xs font-medium" htmlFor={`finding-text-${finding.ordinal}`}>
                        Proposed replacement text
                      </label>
                      <textarea
                        id={`finding-text-${finding.ordinal}`}
                        data-testid={`finding-text-${finding.ordinal}`}
                        className="w-full rounded border bg-background p-2"
                        rows={2}
                        value={draft.proposedText}
                        disabled={record.isPending}
                        onChange={(event) => {
                          const wasPending = Boolean(pendingDraftSubmissions.current[finding.ordinal]);
                          delete pendingDraftSubmissions.current[finding.ordinal];
                          setDrafts((current) => ({
                            ...current,
                            [finding.ordinal]: {
                              ...draft,
                              proposedText: event.target.value,
                              key: wasPending ? newKey() : draft.key,
                            },
                          }));
                        }}
                      />
                    </>
                  ) : null}
                  <Button
                    size="sm"
                    disabled={!valid || record.isPending}
                    data-testid={`finding-submit-${finding.ordinal}`}
                    onClick={() => {
                      // A background refetch may have advanced the visible ledger after an
                      // ambiguous response. Replaying with new CAS but old key is invalid.
                      const previous = pendingDraftSubmissions.current[finding.ordinal];
                      const attempt: PendingSubmission = previous &&
                        previous.view.review_row_id === reviewRowId &&
                        previous.draft.key === draft.key &&
                        previous.draft.action === draft.action &&
                        previous.draft.reason === draft.reason &&
                        previous.draft.proposedText === draft.proposedText
                        ? previous : { view, finding, draft };
                      pendingDraftSubmissions.current[finding.ordinal] = attempt;
                      record.mutate(attempt);
                    }}
                  >
                    Record provisional decision
                  </Button>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
      {derived ? (
        <div className="mt-3 rounded border border-emerald-500 p-2" role="status" data-testid={`derived-result-${reviewRowId}`}>
          <p className="font-medium">
            {derived.replayed ? "Corrected candidate already derived" : "Corrected candidate derived"}: version{" "}
            {derived.derived_artifact_version} (PROPOSED)
          </p>
          <p className="mt-1 text-xs" data-testid={`derived-counts-${reviewRowId}`}>
            Kept {derived.retained}, excluded {derived.excluded}, corrected {derived.corrected}. Derived from version{" "}
            {derived.source_artifact_version} at decision revision {derived.source_ledger_revision}.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Nothing was approved or trusted and no score was computed. The new version starts with every finding
            undecided: review it again, then approve or reject it as a separate decision.
          </p>
        </div>
      ) : null}
      {deriveRefusal ? (
        <p role="alert" className="mt-2 text-destructive" data-testid={`derive-refused-${reviewRowId}`}>
          {deriveRefusal}
        </p>
      ) : null}
      {needsDerivation && !derived && mayReview ? (
        <div className="mt-3 rounded border border-dashed p-2" data-testid={`derive-panel-${reviewRowId}`}>
          <p className="text-xs text-muted-foreground">
            You dismissed or corrected at least one finding. The analysis cannot be approved as it stands: derive a new
            proposed version that leaves out dismissed findings and applies your corrections.
          </p>
          {confirmingDerive ? (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="text-xs">
                This creates a new version as PROPOSED. It approves nothing and your current decisions are not carried
                over.
              </span>
              <Button
                size="sm"
                className="h-auto max-w-full whitespace-normal py-2 text-left"
                disabled={derive.isPending}
                data-testid={`derive-confirm-${reviewRowId}`}
                onClick={() => derive.mutate(view)}
              >
                Confirm: create corrected candidate
              </Button>
              <Button size="sm" variant="outline" disabled={derive.isPending} onClick={() => setConfirmingDerive(false)}>
                Cancel
              </Button>
            </div>
          ) : (
            <Button
              size="sm"
              className="mt-2 h-auto max-w-full whitespace-normal py-2 text-left"
              data-testid={`derive-start-${reviewRowId}`}
              onClick={() => {
                setDeriveRefusal(null);
                setConfirmingDerive(true);
              }}
            >
              Create corrected candidate from my decisions
            </Button>
          )}
        </div>
      ) : null}
    </section>
  );
}
