/**
 * S7: separate, explicit human approval of an ALREADY persisted Technical→WBS audit.
 * Audit-only review is NEVER treated as canonical authority.
 * The authenticated backend is responsible for final project, tenant, revision,
 * original blob hash, WBS scope and idempotency verification.
 */
"use client";

import { useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import { canonicalTechnicalLinksKey } from "./CanonicalTechnicalWBSLinksPanel";
import type { TechnicalWBSReviewHistoryEntry } from "@/lib/api/generated/models";
import { orvalApiClient } from "@/lib/api/client";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type CanonicalApprovalResponse = {
  event_id: string;
  replayed: boolean;
  technical_document_id: string;
  technical_revision_id: string;
  source_clause_id: string;
  wbs_baseline_id: string;
  wbs_node_id: string;
  authority: "EXPLICIT_HUMAN_CANONICAL_LINK";
  approved_canonical_link: true;
  technical_assessment: "NOT_ASSESSED";
};

type Props = {
  projectId: string;
  /** A persisted audit returned by the authenticated review-history GET. */
  audit: TechnicalWBSReviewHistoryEntry;
};

export function CanonicalTechnicalWBSApprovalPanel({ projectId, audit }: Props) {
  const { orgId, userId } = useAuth();
  const queryClient = useQueryClient();
  const [approvalReason, setApprovalReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [pending, setPending] = useState(false);
  const [unknownOutcome, setUnknownOutcome] = useState(false);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState<CanonicalApprovalResponse | null>(null);
  const request = useRef<{ fingerprint: string; key: string } | null>(null);

  const isReviewEligible =
    audit.decision === "CONFIRMED_FOR_REVIEW" &&
    audit.authority === "AUDIT_ONLY_NOT_CANONICAL_LINK" &&
    audit.approved_canonical_link === false &&
    audit.state === "HISTORICAL_AUDIT_ONLY";
  const reason = approvalReason.trim();
  const canSubmit = isReviewEligible && !pending && !unknownOutcome && !receipt &&
    confirmed && reason.length > 0 && reason.length <= 2000;

  async function approveCanonicalLink() {
    if (!canSubmit) return;
    const fingerprint = [
      projectId, audit.event_id, audit.technical_revision_id,
      audit.source_clause_id, audit.proposed_wbs_baseline_id,
      audit.proposed_wbs_node_id, reason,
    ].join("|");
    if (request.current?.fingerprint !== fingerprint) {
      request.current = { fingerprint, key: crypto.randomUUID() };
    }
    setPending(true);
    setError("");
    try {
      const result = await orvalApiClient<CanonicalApprovalResponse>({
        method: "POST",
        url: `/api/v1/projects/${encodeURIComponent(projectId)}/technical-wbs/canonical-links`,
        data: {
          review_event_id: audit.event_id,
          expected_wbs_baseline_id: audit.proposed_wbs_baseline_id,
          expected_wbs_node_id: audit.proposed_wbs_node_id,
          approval: "APPROVE_CANONICAL_LINK",
          idempotency_key: request.current.key,
          reason,
        },
      });
      // Client response checks only prevent false UI receipts; backend remains
      // the sole authority for source/WBS trust and event persistence.
      if (result.approved_canonical_link !== true ||
          result.authority !== "EXPLICIT_HUMAN_CANONICAL_LINK" ||
          result.technical_assessment !== "NOT_ASSESSED" ||
          result.technical_document_id !== audit.technical_document_id ||
          result.technical_revision_id !== audit.technical_revision_id ||
          result.source_clause_id !== audit.source_clause_id ||
          result.wbs_baseline_id !== audit.proposed_wbs_baseline_id ||
          result.wbs_node_id !== audit.proposed_wbs_node_id) {
        throw new Error("Server receipt did not match the reviewed canonical source and WBS.");
      }
      setReceipt(result);
      setConfirmed(false);
      // The approval event is now in the durable backend, but the independent
      // WBS read projection must be fetched again (including after a relogin).
      void queryClient.invalidateQueries({
        queryKey: canonicalTechnicalLinksKey(orgId, userId, projectId),
      });
    } catch {
      // A transport error can occur after the backend committed the immutable
      // event. Do not encourage repeated approval without checking persistence.
      setUnknownOutcome(true);
      setError("Approval outcome needs verification against the persisted event. Do not submit this decision again without checking its status.");
    } finally {
      setPending(false);
    }
  }

  return (
    <Card data-testid="technical-wbs-canonical-approval" className="border-border/80">
      <CardContent className="space-y-3 pt-5 text-sm">
        <h3 className="font-semibold">Final Technical → WBS approval</h3>
        <p className="text-muted-foreground">
          This is a separate, explicit human action. The earlier audit did not
          approve a canonical link or assess technical compliance.
        </p>
        <p data-testid="technical-wbs-canonical-target" className="text-muted-foreground">
          Audit {audit.event_id} · section {audit.source_section} ·
          WBS node {audit.proposed_wbs_node_id}
        </p>
        <label className="block space-y-1">
          <span>Reason for final approval (required)</span>
          <textarea
            aria-label="Reason for final approval"
            rows={2}
            maxLength={2000}
            className="w-full rounded border bg-background p-2"
            value={approvalReason}
            disabled={pending || Boolean(receipt) || unknownOutcome}
            onChange={(event) => setApprovalReason(event.target.value)}
          />
        </label>
        <label className="flex items-start gap-2">
          <input
            type="checkbox"
            aria-label="Confirm explicit canonical approval"
            checked={confirmed}
            disabled={pending || Boolean(receipt) || unknownOutcome}
            onChange={(event) => setConfirmed(event.target.checked)}
          />
          <span>I explicitly approve this exact reviewed technical source to this
            approved WBS node; I understand this does not assess compliance.</span>
        </label>
        <Button
          type="button"
          data-testid="technical-wbs-canonical-submit"
          disabled={!canSubmit}
          onClick={() => void approveCanonicalLink()}
        >
          {pending ? "Recording final approval…" : "Approve canonical Technical → WBS link"}
        </Button>
        {error ? <p role="alert" data-testid="technical-wbs-canonical-error">{error}</p> : null}
        {receipt ? (
          <div data-testid="technical-wbs-canonical-receipt" role="status" className="rounded border p-3">
            <p>Canonical association approved and recorded.</p>
            <p>Approval event: <code>{receipt.event_id}</code></p>
            <p>{receipt.replayed ? "Identical decision safely replayed." : "New explicit decision accepted."}</p>
            <p>Technical compliance remains NOT ASSESSED; Health is not recalculated by this approval.</p>
          <p>Refresh the Technical → WBS approved links panel to verify current authority.</p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
