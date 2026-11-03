/**
 * ACC-01 S7: bounded human review of immutable Technical -> approved WBS.
 * The POST is audit-only; it MUST NOT be presented as canonical approval,
 * technical compliance assessment, or a change to the approved WBS.
 * Test Suite ID: TS-ACC01-S7-TECH-UI-001
 */
"use client";

import { useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useProjectDocuments } from "@/hooks/useProjectDocuments";
import {
  useGetDocumentEndpointApiV1DocumentsDocumentIdGet,
  useListDocumentRevisionStatusesEndpointApiV1DocumentsDocumentIdRevisionsGet,
} from "@/lib/api/generated/documents/documents";
import { useGetWbsBaselineApiV1ProjectsProjectIdWbsGovernanceBaselinesBaselineNoGet } from "@/lib/api/generated/wbs-governance/wbs-governance";
import type {
  ProjectWBSAuthority,
  TechnicalMappingDecision,
  TechnicalWBSReviewHistoryEntry,
  TechnicalWBSReviewRequest,
  TechnicalWBSReviewResponse,
} from "@/lib/api/generated/models";
import { orvalApiClient } from "@/lib/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CanonicalTechnicalWBSApprovalPanel } from "./CanonicalTechnicalWBSApprovalPanel";

type TechnicalClause = {
  id: string;
  clause_code: string;
  title: string | null;
  revision_id: string;
  full_text: string | null;
  text_start_offset: number;
  text_end_offset: number;
  extraction_model: string | null;
  extracted_entities?: { technical_requirement?: { source_section?: string } };
};

const HASH = /^[0-9a-f]{64}$/;

export function eligibleTechnicalClauses(
  rawClauses: unknown,
  trustedRevisionId: string,
): TechnicalClause[] {
  if (!Array.isArray(rawClauses) || !trustedRevisionId) return [];
  return rawClauses.filter((row): row is TechnicalClause => {
    if (!row || typeof row !== "object") return false;
    const c = row as Record<string, unknown>;
    const entities = c.extracted_entities;
    const tech =
      entities && typeof entities === "object"
        ? (entities as Record<string, unknown>).technical_requirement
        : null;
    const section =
      tech && typeof tech === "object"
        ? (tech as Record<string, unknown>).source_section
        : null;
    return (
      typeof c.id === "string" &&
      c.revision_id === trustedRevisionId &&
      c.extraction_model === "deterministic-technical-section-v1" &&
      typeof section === "string" &&
      section.trim().length > 0 &&
      Number.isInteger(c.text_start_offset) &&
      Number.isInteger(c.text_end_offset) &&
      (c.text_start_offset as number) >= 0 &&
      (c.text_end_offset as number) > (c.text_start_offset as number) &&
      typeof c.full_text === "string" &&
      c.full_text.length > 0
    );
  });
}

type Props = { projectId: string; authority: ProjectWBSAuthority | null };

export function TechnicalWBSReviewPanel({ projectId, authority }: Props) {
  const { userId, orgId, isLoaded } = useAuth();
  const { documents, loading: documentsLoading, error: documentsError } =
    useProjectDocuments(projectId);
  const technicalDocuments = useMemo(
    () => documents.filter((doc) => (doc.type === "technical_spec" || doc.type === "specification") && doc.extension === "docx"),
    [documents],
  );
  // Every mount (including after a fresh Clerk sign-in) reads persisted
  // facts. These records are historical, never a current/canonical link.
  const reviewHistory = useQuery({
    // Never reuse another actor or organization cached audit responses.
    queryKey: ["technical-wbs-review-history", orgId, userId, projectId],
    queryFn: () =>
      orvalApiClient<TechnicalWBSReviewHistoryEntry[]>({
        url: `/api/v1/projects/${encodeURIComponent(projectId)}/technical-wbs/reviews`,
        method: "GET",
      }),
    // Personal Clerk tenants legitimately have no active organization.
    enabled: Boolean(isLoaded && userId && projectId),
  });
  const [documentId, setDocumentId] = useState("");
  const selectedDocumentId = technicalDocuments.some((doc) => doc.id === documentId)
    ? documentId
    : "";

  const revisions = useListDocumentRevisionStatusesEndpointApiV1DocumentsDocumentIdRevisionsGet(
    selectedDocumentId,
    { query: { enabled: Boolean(selectedDocumentId) } },
  );
  const trusted = (revisions.data ?? []).filter(
    (r) =>
      r.status === "available" &&
      r.is_current === true &&
      r.current_basis === "trusted" &&
      r.trust_state === "trusted",
  );
  // Never silently choose a revision when the trust reader conflicts.
  const trustedRevisionId = trusted.length === 1 ? trusted[0].revision_id : "";
  // The document row may already point to uploaded B while approved A remains current.
  // Only the immutable revision digest can be used for source identity.
  const trustedBlobHash = trusted.length === 1 ? (trusted[0].blob_hash ?? "") : "";
  const details = useGetDocumentEndpointApiV1DocumentsDocumentIdGet(
    selectedDocumentId,
    trustedRevisionId ? { revision_id: trustedRevisionId } : undefined,
    {
      query: {
        enabled: Boolean(selectedDocumentId && trustedRevisionId),
      },
    },
  );

  const baselineNo =
    authority?.approved && authority.display_state === "APPROVED_BASELINE" &&
    authority.baseline_id && authority.baseline_no
      ? authority.baseline_no
      : 0;
  const baseline = useGetWbsBaselineApiV1ProjectsProjectIdWbsGovernanceBaselinesBaselineNoGet(
    projectId,
    baselineNo,
    { query: { enabled: baselineNo > 0 } },
  );
  const validBaseline = Boolean(
    baselineNo > 0 &&
      baseline.data?.digest_verified === true &&
      baseline.data?.id === authority?.baseline_id &&
      baseline.data?.baseline_no === baselineNo
  );
  const source = details.data;
  const validDocument = Boolean(
    source &&
      source.project_id === projectId &&
      source.id === selectedDocumentId &&
      source.revision_id === trustedRevisionId &&
      (source.document_type === "technical_spec" || source.document_type === "specification") &&
      HASH.test(trustedBlobHash),
  );
  const clauses = validDocument
    ? eligibleTechnicalClauses(source?.clauses, trustedRevisionId)
    : [];

  const [clauseId, setClauseId] = useState("");
  const [nodeId, setNodeId] = useState("");
  const [decision, setDecision] =
    useState<TechnicalMappingDecision>("CONFIRMED_FOR_REVIEW");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState<TechnicalWBSReviewResponse | null>(null);
  const requestKey = useRef<{ fingerprint: string; key: string } | null>(null);

  const selectedClause = clauses.find((c) => c.id === clauseId);
  const selectedNode = validBaseline
    ? baseline.data?.nodes.find((n) => n.node_id === nodeId)
    : null;
  // The exact review must have reached the durable, authenticated GET before
  // the final human-approval action is even offered. No POST result alone can
  // bootstrap canonical authority.
  const confirmedReview = validBaseline && validDocument &&
      selectedClause && selectedNode && decision === "CONFIRMED_FOR_REVIEW"
    ? reviewHistory.data?.find((row) =>
        row.state === "HISTORICAL_AUDIT_ONLY" &&
        row.authority === "AUDIT_ONLY_NOT_CANONICAL_LINK" &&
        row.approved_canonical_link === false &&
        row.decision === "CONFIRMED_FOR_REVIEW" &&
        row.technical_document_id === selectedDocumentId &&
        row.technical_revision_id === trustedRevisionId &&
        row.source_clause_id === selectedClause.id &&
        row.proposed_wbs_baseline_id === authority?.baseline_id &&
        row.proposed_wbs_node_id === selectedNode.node_id
      )
    : undefined;
  const ready = Boolean(
    validBaseline &&
      validDocument &&
      !details.isLoading &&
      !revisions.isLoading &&
      !baseline.isLoading &&
      !details.isError &&
      !revisions.isError &&
      !baseline.isError &&
      selectedClause &&
      selectedNode &&
      reason.trim().length > 0 &&
      reason.trim().length <= 2000,
  );

  async function recordDecision() {
    if (!ready || busy || !selectedClause || !selectedNode || !trustedBlobHash) return;
    const fingerprint = [
      projectId, selectedDocumentId, trustedRevisionId, trustedBlobHash,
      authority?.baseline_id, selectedClause.id, selectedNode.node_id, decision,
      reason.trim(),
    ].join("|");
    // A transport retry of this exact human decision preserves its key.
    // Any change to source, revision, WBS, decision or reason gets a new key.
    if (requestKey.current?.fingerprint !== fingerprint) {
      requestKey.current = { fingerprint, key: crypto.randomUUID() };
    }
    const body: TechnicalWBSReviewRequest = {
      clause_id: selectedClause.id,
      expected_revision_id: trustedRevisionId,
      expected_blob_hash: trustedBlobHash,
      expected_wbs_baseline_id: authority!.baseline_id!,
      proposed_wbs_node_id: selectedNode.node_id,
      decision,
      idempotency_key: requestKey.current.key,
      reason: reason.trim(),
    };
    setBusy(true);
    setError("");
    setReceipt(null);
    try {
      const response = await orvalApiClient<TechnicalWBSReviewResponse>({
        url: `/api/v1/projects/${encodeURIComponent(projectId)}/technical-wbs/reviews`,
        method: "POST",
        data: body,
      });
      if (
        response.authority !== "AUDIT_ONLY_NOT_CANONICAL_LINK" ||
        response.approved_canonical_link !== false
      ) {
        throw new Error("The review receipt does not match audit-only authority.");
      }
      setReceipt(response);
      void reviewHistory.refetch();
    } catch {
      setError(
        "The review was not confirmed. Recheck the source and approved WBS; " +
        "an unauthorized, changed, or already-reviewed candidate must not be reused.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card data-testid="technical-wbs-review">
      <CardHeader>
        <CardTitle>Technical requirement → WBS review</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-muted-foreground">
          Record a human review against the exact trusted technical revision and
          approved scope baseline. This does not create an approved WBS link,
          determine technical compliance, or change Health.
        </p>
        {!authority?.approved || !validBaseline ? (
          <p data-testid="technical-wbs-no-baseline">
            An immutable approved WBS baseline is required before review.
          </p>
        ) : null}
        <label className="block space-y-1">
          <span>Technical specification</span>
          <select
            aria-label="Technical specification"
            disabled={busy}
            className="w-full rounded border bg-background p-2"
            value={selectedDocumentId}
            onChange={(e) => {
              setDocumentId(e.target.value);
              setClauseId("");
              setNodeId("");
              setReceipt(null);
            }}
          >
            <option value="">Choose a technical DOCX</option>
            {technicalDocuments.map((doc) => (
              <option key={doc.id} value={doc.id}>{doc.name}</option>
            ))}
          </select>
        </label>
        {documentsLoading ? <p>Loading documents…</p> : null}
        {documentsError ? <p role="alert">Document list unavailable.</p> : null}
        {selectedDocumentId && (!trustedRevisionId || !validDocument) ? (
          <p data-testid="technical-wbs-untrusted">
            No uniquely verified trusted-current technical revision with a source hash.
          </p>
        ) : null}
        <label className="block space-y-1">
          <span>Source requirement</span>
          <select
            aria-label="Source requirement"
            className="w-full rounded border bg-background p-2"
            value={clauses.some((clause) => clause.id === clauseId) ? clauseId : ""}
            onChange={(e) => { setClauseId(e.target.value); setReceipt(null); }}
            disabled={!validDocument || busy}
          >
            <option value="">Choose a source section</option>
            {clauses.map((clause) => (
              <option key={clause.id} value={clause.id}>
                {clause.clause_code}: {clause.title || clause.full_text}
              </option>
            ))}
          </select>
        </label>
        {selectedClause ? (
          <Link
            className="underline"
            href={
              `/projects/${encodeURIComponent(projectId)}/evidence` +
              `?documentId=${encodeURIComponent(selectedDocumentId)}` +
              `&revisionId=${encodeURIComponent(trustedRevisionId)}` +
              `&highlightId=${encodeURIComponent(selectedClause.id)}`
            }
          >
            Inspect immutable source
          </Link>
        ) : null}
        <label className="block space-y-1">
          <span>Approved WBS node</span>
          <select
            aria-label="Approved WBS node"
            className="w-full rounded border bg-background p-2"
            value={validBaseline && baseline.data?.nodes.some((n) => n.node_id === nodeId) ? nodeId : ""}
            onChange={(e) => { setNodeId(e.target.value); setReceipt(null); }}
            disabled={!validBaseline || busy}
          >
            <option value="">Choose an approved baseline node</option>
            {validBaseline && baseline.data?.nodes.map((n) => (
              <option key={n.node_id} value={n.node_id}>{n.code}: {n.name}</option>
            ))}
          </select>
        </label>
        <label className="block space-y-1">
          <span>Human decision</span>
          <select
            aria-label="Human decision"
            disabled={busy}
            className="w-full rounded border bg-background p-2"
            value={decision}
            onChange={(e) => {
              setDecision(e.target.value as TechnicalMappingDecision);
              setReceipt(null);
            }}
          >
            <option value="CONFIRMED_FOR_REVIEW">Confirm candidate for later approval</option>
            <option value="REJECTED">Reject proposed relation</option>
          </select>
        </label>
        <label className="block space-y-1">
          <span>Reviewer reason (required)</span>
          <textarea
            aria-label="Reviewer reason"
            disabled={busy}
            className="w-full rounded border bg-background p-2"
            rows={2}
            maxLength={2000}
            value={reason}
            onChange={(e) => { setReason(e.target.value); setReceipt(null); }}
          />
        </label>
        <Button
          type="button"
          disabled={!ready || busy}
          onClick={recordDecision}
          data-testid="technical-wbs-review-submit"
        >
          {busy ? "Recording…" : "Record audit-only review"}
        </Button>
        {error ? <p role="alert" data-testid="technical-wbs-review-error">{error}</p> : null}
        {receipt ? (
          <div data-testid="technical-wbs-review-receipt" role="status" className="rounded border p-3">
            <p>Review event: <code>{receipt.event_id}</code></p>
            <p>{receipt.replayed ? "Existing decision recovered." : "Human decision recorded."}</p>
            <p><strong>Not a canonical link; technical compliance not assessed.</strong></p>
          </div>
        ) : null}
        {confirmedReview ? (
          <CanonicalTechnicalWBSApprovalPanel
            key={confirmedReview.event_id}
            projectId={projectId}
            audit={confirmedReview}
          />
        ) : null}
        <section data-testid="technical-wbs-review-history" aria-label="My previous reviews">
          <h3 className="font-semibold">My previous reviews — historical audit only</h3>
          <p className="text-muted-foreground">
            These are your persisted review decisions, including superseded sources.
            They do not establish current WBS links, approval or compliance.
          </p>
          {reviewHistory.isLoading ? <p>Loading persisted reviews…</p> : null}
          {reviewHistory.isError ? (
            <p role="alert">Prior reviews could not be loaded.</p>
          ) : null}
          {reviewHistory.isSuccess && reviewHistory.data.length === 0 ? (
            <p>No review decisions recorded for this user in this project.</p>
          ) : null}
          {reviewHistory.isSuccess && reviewHistory.data.length > 0 ? (
            <ul className="space-y-2">
              {reviewHistory.data.map((item) => (
                <li key={item.event_id} className="rounded border p-2">
                  <p>
                    {item.decision === "REJECTED" ? "Rejected" : "Confirmed for later review"}
                    {" — "}{item.source_section}
                  </p>
                  <p>Reason: {item.reason}</p>
                  <p className="text-muted-foreground">WBS node: {item.proposed_wbs_node_id}</p>
                  <Link className="underline" href={
                    `/projects/${encodeURIComponent(projectId)}/evidence` +
                    `?documentId=${encodeURIComponent(item.technical_document_id)}` +
                    `&revisionId=${encodeURIComponent(item.technical_revision_id)}` +
                    `&highlightId=${encodeURIComponent(item.source_clause_id)}`
                  }>Inspect historical source</Link>
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      </CardContent>
    </Card>
  );
}
