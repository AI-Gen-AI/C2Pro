/**
 * Typed read-only source addresses in an HITL item. Free-text critique is
 * never a source reference. Resolution is reverified by the evidence viewer.
 */
export interface ReviewSourceLink {
  key: string;
  label: string;
  href: string;
}

export function reviewSourceLinks(
  projectId: string,
  itemData: Record<string, unknown> | undefined,
): ReviewSourceLink[] {
  if (!projectId.trim() || !Array.isArray(itemData?.source_references)) return [];
  const results: ReviewSourceLink[] = [];
  const seen = new Set<string>();
  for (const entry of itemData.source_references) {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) continue;
    const ref = entry as Record<string, unknown>;
    const documentId =
      typeof ref.document_id === "string" ? ref.document_id.trim() : "";
    const revisionId =
      typeof ref.revision_id === "string" ? ref.revision_id.trim() : "";
    const clauseId =
      typeof ref.clause_id === "string" ? ref.clause_id.trim() : "";
    if (!documentId || !revisionId || !clauseId) continue;
    const key = JSON.stringify([documentId, revisionId, clauseId]);
    if (seen.has(key)) continue;
    seen.add(key);
    const clauseCode =
      typeof ref.clause_code === "string" &&
      /^[\p{L}\p{N}.§-]{1,32}$/u.test(ref.clause_code.trim())
        ? ref.clause_code.trim().replace(/^§/, "")
        : null;
    const query = new URLSearchParams({
      documentId,
      revisionId,
      highlightId: clauseId,
    });
    results.push({
      key,
      label: clauseCode ? "Inspect cited clause §" + clauseCode : "Inspect cited source",
      href: "/projects/" + encodeURIComponent(projectId) +
        "/evidence?" + query.toString(),
    });
  }
  return results;
}
