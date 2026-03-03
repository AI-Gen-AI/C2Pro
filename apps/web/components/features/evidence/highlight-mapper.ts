/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
export type EvidenceSeverity = "critical" | "high" | "medium" | "low";

export interface EvidenceClauseAnchor {
  clauseId: string;
  page: number;
  startOffset: number;
  endOffset: number;
  severity?: EvidenceSeverity;
}

export interface EvidenceHighlight {
  id: string;
  clauseId: string;
  page: number;
  startOffset: number;
  endOffset: number;
  severity: EvidenceSeverity;
}

function isValidAnchor(anchor: EvidenceClauseAnchor): boolean {
  return (
    anchor.page >= 1 &&
    anchor.startOffset >= 0 &&
    anchor.endOffset > anchor.startOffset
  );
}

export function mapClausesToHighlights(
  anchors: EvidenceClauseAnchor[],
): EvidenceHighlight[] {
  return anchors
    .filter(isValidAnchor)
    .map((anchor, index) => ({
      id: `hl-${anchor.clauseId}-${index}`,
      clauseId: anchor.clauseId,
      page: anchor.page,
      startOffset: anchor.startOffset,
      endOffset: anchor.endOffset,
      severity: anchor.severity ?? "low",
    }))
    .sort((a, b) => {
      if (a.page !== b.page) return a.page - b.page;
      return a.startOffset - b.startOffset;
    });
}
