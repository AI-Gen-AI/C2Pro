export const EVIDENCE_TARGET_TYPES = [
  "CLAUSE",
  "DOCUMENT_SPAN",
  "STAKEHOLDER",
  "RACI",
  "WBS",
  "ALERT",
  "CHANGE",
  "OTHER",
] as const;

export type EvidenceTargetType = (typeof EVIDENCE_TARGET_TYPES)[number];

export interface SemanticEvidenceTarget {
  id: string;
  label: string;
  type: EvidenceTargetType;
}

export interface SourceEvidenceClause {
  id: string;
  clauseCode: string | null;
  label: string;
  page: number | null;
  startOffset: number | null;
  endOffset: number | null;
  revisionId?: string | null;
}

export type EvidenceAddressResolution =
  | {
      kind: "semantic";
      target: SemanticEvidenceTarget;
    }
  | {
      kind: "raw-clause";
      target: SourceEvidenceClause;
      targetType: "CLAUSE" | "DOCUMENT_SPAN";
    }
  | {
      kind: "document-fallback";
      target: SourceEvidenceClause;
    }
  | {
      kind: "unresolved";
    };

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function asNonNegativeInteger(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value >= 0
    ? value
    : null;
}

function asPage(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value >= 1
    ? value
    : null;
}

/**
 * Converts the authoritative document-detail clause records into stable source
 * targets. The generated API type is intentionally structural because clauses
 * carry extracted metadata, so this is the framework boundary that validates
 * only the fields needed to make an evidence link addressable.
 */
export function sourceEvidenceClausesFromDocumentDetail(
  clauses: Array<Record<string, unknown>> | null | undefined,
): SourceEvidenceClause[] {
  return (clauses ?? []).flatMap((clause) => {
    const id = asString(clause.id);
    if (!id) {
      return [];
    }

    const metadata = asRecord(clause.extracted_entities);
    const evidenceLocation = asRecord(metadata?.evidence_location);
    const clauseCode = asString(clause.clause_code);
    const revisionId = asString(clause.revision_id);
    const title = asString(clause.title);
    const fullText = asString(clause.full_text);

    return [
      {
        id,
        clauseCode,
        label: title ?? fullText ?? clauseCode ?? id,
        page: asPage(evidenceLocation?.page_number),
        startOffset: asNonNegativeInteger(clause.text_start_offset),
        endOffset: asNonNegativeInteger(clause.text_end_offset),
        ...(revisionId ? { revisionId } : {}),
      },
    ];
  });
}

/**
 * Resolves a user-visible evidence reference without assuming it is already a
 * semantic projection. Resolution is ordered: semantic target, raw source
 * clause/span, document fallback, then an explicit unresolved state.
 */
export function resolveEvidenceAddress({
  evidenceId,
  semanticTargets,
  sourceClauses,
  revisionId,
  documentRevisionId,
}: {
  evidenceId: string;
  semanticTargets: SemanticEvidenceTarget[];
  sourceClauses: SourceEvidenceClause[];
  revisionId?: string | null;
  documentRevisionId?: string | null;
}): EvidenceAddressResolution {
  // A pinned source must match BOTH the current PDF revision and the clause.
  // Never fall through to a current semantic projection on a stale revision.
  if (revisionId && revisionId !== documentRevisionId) {
    return { kind: "unresolved" };
  }
  if (!revisionId) {
    const semanticTarget = semanticTargets.find((target) => target.id === evidenceId);
    if (semanticTarget) {
      return { kind: "semantic", target: semanticTarget };
    }
  }

  const sourceClause = sourceClauses.find(
    (target) => target.id === evidenceId &&
      (!revisionId || target.revisionId === revisionId),
  );
  if (!sourceClause) {
    return { kind: "unresolved" };
  }

  if (!sourceClause.page) {
    return { kind: "document-fallback", target: sourceClause };
  }

  const hasDocumentSpan =
    sourceClause.startOffset !== null &&
    sourceClause.endOffset !== null &&
    sourceClause.endOffset > sourceClause.startOffset;

  return {
    kind: "raw-clause",
    target: sourceClause,
    targetType: hasDocumentSpan ? "DOCUMENT_SPAN" : "CLAUSE",
  };
}
