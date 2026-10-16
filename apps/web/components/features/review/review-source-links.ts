/**
 * Typed read-only source addresses in an HITL item. Free-text critique is
 * never a source reference. Resolution is reverified by the evidence viewer.
 */
export interface ReviewSourceLink {
  key: string;
  label: string;
  href: string;
}

interface ParsedReviewSource {
  documentId: string;
  revisionId: string;
  clauseId: string;
  clauseCode: string | null;
}

function parseReviewSource(entry: unknown): ParsedReviewSource | null {
  if (!entry || typeof entry !== "object" || Array.isArray(entry)) return null;
  const ref = entry as Record<string, unknown>;
  const documentId =
    typeof ref.document_id === "string" ? ref.document_id.trim() : "";
  const revisionId =
    typeof ref.revision_id === "string" ? ref.revision_id.trim() : "";
  const clauseId =
    typeof ref.clause_id === "string" ? ref.clause_id.trim() : "";
  if (!documentId || !revisionId || !clauseId) return null;

  const clauseCode =
    typeof ref.clause_code === "string" &&
    /^[\p{L}\p{N}.§-]{1,32}$/u.test(ref.clause_code.trim())
      ? ref.clause_code.trim().replace(/^§/, "")
      : null;
  return { documentId, revisionId, clauseId, clauseCode };
}

function sourceLink(
  projectId: string,
  source: ParsedReviewSource,
  key: string,
): ReviewSourceLink {
  const query = new URLSearchParams({
    documentId: source.documentId,
    revisionId: source.revisionId,
    highlightId: source.clauseId,
  });
  return {
    key,
    label: source.clauseCode
      ? "Inspect cited clause §" + source.clauseCode
      : "Inspect cited source",
    href: "/projects/" + encodeURIComponent(projectId) +
      "/evidence?" + query.toString(),
  };
}

export function reviewSourceLinks(
  projectId: string,
  itemData: Record<string, unknown> | undefined,
): ReviewSourceLink[] {
  if (!projectId.trim() || !Array.isArray(itemData?.source_references)) return [];

  const seen = new Set<string>();
  return itemData.source_references.flatMap((entry): ReviewSourceLink[] => {
    const source = parseReviewSource(entry);
    if (!source) return [];
    const key = JSON.stringify([
      source.documentId, source.revisionId, source.clauseId,
    ]);
    if (seen.has(key)) return [];
    seen.add(key);
    return [sourceLink(projectId, source, key)];
  });
}
