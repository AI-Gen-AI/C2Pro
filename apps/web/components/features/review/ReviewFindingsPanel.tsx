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
  listReviewFindingsApiV1HitlReviewsReviewRowIdFindingsGet,
  recordFindingDecisionApiV1HitlReviewsReviewRowIdFindingsDecisionsPost,
} from "@/lib/api/generated/hitl-findings/hitl-findings";
import type { ReviewFindingResponse, ReviewFindingsResponse } from "@/lib/api/generated/models";
import type { FindingDecisionAction } from "@/lib/api/generated/models/findingDecisionAction";

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
  review_unavailable: "This review is no longer open. Nothing was recorded.",
};

function refusalFrom(error: unknown): string {
  if (isAxiosError(error)) {
    const code = (error.response?.data as { detail?: { code?: string } } | undefined)?.detail?.code;
    if (code && REFUSAL[code]) return REFUSAL[code];
  }
  return "The decision could not be recorded.";
}

const needsReason = (action: FindingDecisionAction) => action !== "CONFIRMED";

function newKey(): string {
  return `finding-${globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`}`;
}

type Draft = { action: FindingDecisionAction; reason: string; proposedText: string; key: string };

export function ReviewFindingsPanel({ reviewRowId }: { reviewRowId: string }) {
  const { orgId, userId, isLoaded } = useAuth();
  const queryClient = useQueryClient();
  const queryKey = ["review-findings", orgId ?? null, userId ?? null, reviewRowId];
  const query = useQuery({
    queryKey,
    queryFn: ({ signal }) => listReviewFindingsApiV1HitlReviewsReviewRowIdFindingsGet(reviewRowId, signal),
    enabled: Boolean(isLoaded && userId),
    retry: false,
    staleTime: 0,
  });
  const [drafts, setDrafts] = useState<Record<number, Draft | undefined>>({});
  const [refusal, setRefusal] = useState<string | null>(null);

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
      {refusal ? (
        <p role="alert" className="mt-2 text-destructive" data-testid={`review-findings-refused-${reviewRowId}`}>
          {refusal}
        </p>
      ) : null}
      <ul className="mt-2 space-y-3">
        {view.findings.map((finding) => {
          const draft = drafts[finding.ordinal];
          const title = String(finding.risk.title ?? `Finding ${finding.ordinal + 1}`);
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
              {finding.risk.description ? (
                <p className="mt-1 text-muted-foreground">{String(finding.risk.description)}</p>
              ) : null}
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
                    disabled={record.isPending}
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
    </section>
  );
}
