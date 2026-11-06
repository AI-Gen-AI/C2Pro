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
import { useState } from "react";
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
  CONFIRMED: "Confirm",
  DISMISSED: "Dismiss",
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

/** Explicit source-backed deadline vs an AI claim that no deadline exists. Advisory, never auto-decides. */
function contradictsVerifiedDeadline(risk: Record<string, unknown>): boolean {
  if (risk.source_quote_status !== "VERIFIED" || typeof risk.source_quote !== "string") return false;
  const quote = risk.source_quote;
  const claim = `${String(risk.title ?? "")} ${String(risk.description ?? "")}`;
  const deadline = /\bwithin\s+(?:(?:[a-z]+)\s+)?\(?\d{1,3}\)?\s+(?:calendar\s+)?days?\s+of\s+(?:written\s+)?notice\b/i;
  const missing = /\b(?:no|without|lacks?|lacking)\s+(?:(?:an?|the|agreed|defined|specified|clear)\s+){0,4}(?:rectification\s+)?(?:time\s?frame|deadline|period|cure\s+period)\b/i;
  return deadline.test(quote) && missing.test(claim);
}

function newKey(): string {
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  return `finding-${Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("")}`;
}

type Draft = { action: FindingDecisionAction; reason: string; proposedText: string; key: string };

/**
 * Where in the contract a finding comes from, kept apart from the generated description above it: the clause label the analysis
 * assigned and the contract text it rests on. The quote is shown only when the server verified it verbatim against the document;
 * otherwise the reviewer is told there is none and why, never a paraphrase presented as a citation.
 */
function ContractTrace({ ordinal, risk }: { ordinal: number; risk: Record<string, unknown> }) {
  const clause = typeof risk.clause_ref === "string" ? risk.clause_ref.trim() : "";
  const quote = typeof risk.source_quote === "string" ? risk.source_quote.trim() : "";
  const status = typeof risk.source_quote_status === "string" ? risk.source_quote_status : "";
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
          <figcaption className="mt-0.5 text-muted-foreground">Quoted from the contract (found verbatim in the document)</figcaption>
        </figure>
      ) : (
        <p className="mt-1 text-muted-foreground" data-testid={`finding-quote-missing-${ordinal}`}>
          {status === "NOT_FOUND_IN_DOCUMENT"
            ? "No verified quote: the text the analysis proposed was not found verbatim in the document, so it is not shown."
            : "No quote available for this finding."}
        </p>
      )}
    </div>
  );
}

export function ReviewFindingsPanel({ reviewRowId }: { reviewRowId: string }) {
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
  const [drafts, setDrafts] = useState<Record<number, Draft | undefined>>({});
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
    onSuccess: (_receipt, { finding }) => {
      setRefusal(null);
      setDrafts((current) => ({ ...current, [finding.ordinal]: undefined }));
      void queryClient.invalidateQueries({ queryKey });
    },
    onError: (error) => {
      setRefusal(refusalFrom(error));
      void queryClient.invalidateQueries({ queryKey });
    },
  });

  if (query.isLoading) return null;
  if (query.isError || !query.data) return null; // not a candidate-bound analysis review: nothing to decide here
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
        Decisions here are provisional notes by you. They do not approve, reject or trust the analysis: that remains the
        separate Approve / Reject decision.
      </p>
      {view.findings.length === 0 ? (
        <p className="mt-2 text-muted-foreground" data-testid={`review-findings-empty-${reviewRowId}`}>
          This candidate lists no individual findings to decide.
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
          const suggestion = [finding.risk.mitigation_suggestion, finding.risk.recommended_action, finding.risk.mitigation]
            .find((value) => typeof value === "string" && value.trim().length > 0);
          const conflict = contradictsVerifiedDeadline(finding.risk);
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
              {clause ? <p className="mt-1 text-xs text-muted-foreground">Contract clause {clause}</p> : null}
              <p className="mt-2 text-sm" data-testid={`finding-action-summary-${finding.ordinal}`}>
                <span className="font-medium">Suggested action: </span>
                {typeof suggestion === "string"
                  ? suggestion
                  : "No specific mitigation supplied. Verify the contractual basis before deciding."}
              </p>
              {conflict ? (
                <p role="alert" className="mt-2 rounded border border-amber-400 bg-amber-50 p-2 text-sm text-amber-900"
                  data-testid={`finding-source-conflict-${finding.ordinal}`}>
                  Possible contradiction: the verified contract quotation explicitly specifies a notice deadline,
                  while the AI description claims no deadline. Do not confirm this finding without correcting it.
                </p>
              ) : null}
              <details className="mt-2 rounded border border-dashed p-2" data-testid={`finding-evidence-${finding.ordinal}`}>
                <summary className="cursor-pointer text-sm font-medium">View evidence and full AI analysis</summary>
                {finding.risk.description ? (
                  <p className="mt-2 whitespace-pre-wrap text-muted-foreground" data-testid={`finding-description-${finding.ordinal}`}>
                    <span className="mr-1 text-xs font-medium uppercase tracking-wide">Analysis (AI-generated):</span>{" "}
                    {String(finding.risk.description)}
                  </p>
                ) : null}
                <ContractTrace ordinal={finding.ordinal} risk={finding.risk} />
              </details>
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
                    disabled={record.isPending || !mayReview || (action === "CONFIRMED" && conflict)}
                    title={action === "CONFIRMED" && conflict ? "The AI finding conflicts with the verified source. Propose a correction instead." : undefined}
                    data-testid={`finding-action-${finding.ordinal}-${action}`}
                    onClick={() => {
                      setRefusal(null);
                      if (action === "CONFIRMED") {
                        record.mutate({
                          view,
                          finding,
                          draft: { action, reason: "", proposedText: "", key: newKey() },
                        });
                      } else {
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
                    onChange={(event) =>
                      setDrafts((current) => ({ ...current, [finding.ordinal]: { ...draft, reason: event.target.value } }))
                    }
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
                        onChange={(event) =>
                          setDrafts((current) => ({
                            ...current,
                            [finding.ordinal]: { ...draft, proposedText: event.target.value },
                          }))
                        }
                      />
                    </>
                  ) : null}
                  <Button
                    size="sm"
                    disabled={!valid || record.isPending}
                    data-testid={`finding-submit-${finding.ordinal}`}
                    onClick={() => record.mutate({ view, finding, draft })}
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
              className="mt-2"
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
