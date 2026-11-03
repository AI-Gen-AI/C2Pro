/**
 * PJ-01 revision-authority judge: what the application treats as the document's CURRENT state
 * while a newer revision is still waiting for its human (HITL) decision, and after it is approved.
 *
 * Pure: the browser harness captures the application's Health vector, the Evidence entities it
 * loaded from a supporting-clause link and the Current State report, and asks this module whether
 * they rest on the AUTHORIZED revision only. The expected revision identities come from the
 * fixture-bound revision events (blob hashes of the committed contract A and B files), never from
 * the Health or Current State answer being judged.
 */
import type { CurrentStateReportLike } from "./current-state-evaluator";

export interface EvidenceEntityLike {
  id: string;
  metadata?: { evidence_location?: { revision_id?: string | null } | null } | null;
}

export interface RevisionAuthorityViolation {
  code: string;
  detail: string;
}

/** `Z`-less ISO instants (naive UTC, as the API stores them) are read as UTC, not local time. */
export function parseInstant(value: string): number {
  return new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`).getTime();
}

export function revisionOfClause(entities: EvidenceEntityLike[], clauseId: string): string | null {
  const entity = entities.find((candidate) => candidate.id === clauseId);
  return entity?.metadata?.evidence_location?.revision_id ?? null;
}

/**
 * The supporting clause Health cites must belong to `expectedRevisionId`. A clause the Evidence
 * workspace cannot resolve is a violation too: an unresolved citation proves nothing.
 */
export function evaluateHealthEvidenceRevision(
  input: { clauseId: string; entities: EvidenceEntityLike[] },
  expectation: { expectedRevisionId: string; otherRevisionId?: string; phase: string },
): RevisionAuthorityViolation[] {
  const revision = revisionOfClause(input.entities, input.clauseId);
  if (revision === null) {
    return [
      {
        code: "EVIDENCE_CLAUSE_UNRESOLVED",
        detail: `${expectation.phase}: Health cites clause ${input.clauseId} but the Evidence workspace has no revision for it`,
      },
    ];
  }
  if (revision !== expectation.expectedRevisionId) {
    const which = revision === expectation.otherRevisionId ? "the OTHER revision" : "an unexpected revision";
    return [
      {
        code: "HEALTH_RESTS_ON_WRONG_REVISION",
        detail: `${expectation.phase}: Health cites a clause of ${which} (${revision}); authorized revision is ${expectation.expectedRevisionId}`,
      },
    ];
  }
  return [];
}

const documentsOf = (report: CurrentStateReportLike) => report.sections.documents?.data?.items ?? [];
const attentionKinds = (report: CurrentStateReportLike): string[] =>
  (report.sections.executive_summary?.data?.attention_items ?? []).map((item) => item.kind);

/**
 * Revision B uploaded and analysed but NOT yet approved: Current State must not present the
 * document as analysed, and must tell the reader that a revision is waiting.
 */
export function evaluatePendingRevisionCurrentState(report: CurrentStateReportLike): RevisionAuthorityViolation[] {
  const violations: RevisionAuthorityViolation[] = [];
  for (const item of documentsOf(report)) {
    if (item.lifecycle_status === "analyzed") {
      violations.push({
        code: "PENDING_REVISION_SHOWN_AS_ANALYZED",
        detail: `document ${item.id} is shown as analyzed while its latest revision still waits for approval`,
      });
    }
  }
  if (documentsOf(report).length === 0) {
    violations.push({ code: "PENDING_REVISION_DOCUMENT_MISSING", detail: "the documents section lists no document" });
  }
  if (!attentionKinds(report).includes("documents_awaiting_analysis")) {
    violations.push({
      code: "PENDING_REVISION_NOT_DISCLOSED",
      detail: `the summary does not say a document awaits analysis (attention: ${attentionKinds(report).join(", ") || "none"})`,
    });
  }
  const hitl = report.sections.hitl;
  if (!hitl || hitl.status !== "available") {
    violations.push({
      code: "PENDING_DECISION_NOT_DISCLOSED",
      detail: `the HITL section reads "${hitl?.status ?? "missing"}" while a review item awaits a decision`,
    });
  }
  return violations;
}

/**
 * Revision B approved: nothing may still read as pending, and Health must be recomputed AFTER the
 * human decision (an earlier snapshot is the pre-approval state).
 */
export function evaluateApprovedRevisionCurrentState(
  report: CurrentStateReportLike,
  expectation: { approvedAt: string },
): RevisionAuthorityViolation[] {
  const violations: RevisionAuthorityViolation[] = [];
  for (const item of documentsOf(report)) {
    if (item.lifecycle_status !== "analyzed") {
      violations.push({
        code: "APPROVED_REVISION_NOT_ANALYZED",
        detail: `document ${item.id} reads "${item.lifecycle_status}" after its revision was approved`,
      });
    }
  }
  if (attentionKinds(report).includes("documents_awaiting_analysis")) {
    violations.push({ code: "APPROVED_REVISION_STILL_PENDING", detail: "the summary still reports a document awaiting analysis" });
  }
  if (report.sections.hitl?.status === "available") {
    violations.push({ code: "APPROVED_DECISION_STILL_PENDING", detail: "the HITL section still lists a decision awaiting a human" });
  }
  const asOf = report.sections.health?.source_as_of;
  if (!asOf || parseInstant(asOf) < parseInstant(expectation.approvedAt)) {
    violations.push({
      code: "HEALTH_PREDATES_APPROVAL",
      detail: `health as of ${asOf ?? "(none)"} predates the approval at ${expectation.approvedAt}`,
    });
  }
  return violations;
}

export interface RevisionIdentity {
  revisionId: string;
  /** SHA-256 of the committed fixture file, never read from the answer being judged. */
  blobHash: string;
}

/**
 * Revision trace of the single document in Current State, against fixture-bound identities:
 * while B waits, A is the TRUSTED source and B is only pending; once B is approved B is trusted
 * and nothing is pending. A pending revision is never reported as trusted.
 */
export function evaluateCurrentStateRevisionTrace(
  report: CurrentStateReportLike,
  expectation: { trusted: RevisionIdentity; pending?: RevisionIdentity },
): RevisionAuthorityViolation[] {
  const violations: RevisionAuthorityViolation[] = [];
  const [item] = documentsOf(report);
  if (!item) {
    return [{ code: "REVISION_TRACE_DOCUMENT_MISSING", detail: "the documents section lists no document" }];
  }
  const same = (actual: { revision_id: string; blob_hash: string } | null | undefined, wanted: RevisionIdentity): boolean =>
    !!actual && actual.revision_id === wanted.revisionId && actual.blob_hash === wanted.blobHash;
  if (!same(item.trusted_revision, expectation.trusted)) {
    violations.push({
      code: "TRUSTED_REVISION_MISMATCH",
      detail: `trusted revision ${JSON.stringify(item.trusted_revision ?? null)} is not ${expectation.trusted.revisionId} (sha256 ${expectation.trusted.blobHash})`,
    });
  }
  if (expectation.pending) {
    if (!same(item.pending_revision, expectation.pending)) {
      violations.push({
        code: "PENDING_REVISION_MISMATCH",
        detail: `pending revision ${JSON.stringify(item.pending_revision ?? null)} is not ${expectation.pending.revisionId} (sha256 ${expectation.pending.blobHash})`,
      });
    }
  } else if (item.pending_revision) {
    violations.push({
      code: "PENDING_REVISION_AFTER_APPROVAL",
      detail: `revision ${item.pending_revision.revision_id} is still reported pending after the approval`,
    });
  }
  return violations;
}
