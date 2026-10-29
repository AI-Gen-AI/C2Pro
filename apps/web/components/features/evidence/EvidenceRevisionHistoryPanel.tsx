"use client";

import { useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  useGetDocumentEntitiesEndpointApiV1DocumentsDocumentIdEntitiesGet,
  useListDocumentRevisionStatusesEndpointApiV1DocumentsDocumentIdRevisionsGet,
} from "@/lib/api/generated/documents/documents";
import type { RevisionStatus } from "@/lib/api/generated/models";

type SelectedRevision = { documentId: string; revisionId: string };

// A current revision is only authoritative when the trusted-current resolver
// explicitly establishes its basis, not from a stale is_current flag alone.
function isTrustedCurrent(revision: RevisionStatus): boolean {
  return (
    revision.status === "available" &&
    revision.trust_state === "trusted" &&
    revision.is_current === true &&
    revision.current_basis === "trusted"
  );
}

function revisionLabel(revision: RevisionStatus): string {
  if (revision.status !== "available") return "Status unavailable";
  if (isTrustedCurrent(revision)) return "Trusted current";
  if (revision.trust_state === "proposed") return "Proposed — not trusted";
  if (revision.trust_state === "trusted" && revision.is_current) {
    return "Trusted artifact — current authority unresolved";
  }
  if (revision.trust_state === "trusted") {
    return "Trusted artifact — not current";
  }
  if (revision.trust_state === "rejected") return "Rejected — historical";
  if (revision.trust_state === "superseded") return "Superseded — historical";
  return "Artifact trust not established";
}

/**
 * PQ-HITL-03: an explicitly revision-scoped *read-only* inspection surface.
 * IMPORTANT: these preview rows must never feed the authoritative graph,
 * entity-approval controls, current Health/Coherence, alert counts or exports.
 */
export function EvidenceRevisionHistoryPanel({
  documentId,
  projectId,
}: {
  documentId: string | null;
  projectId?: string;
}) {
  const [selection, setSelection] = useState<SelectedRevision | null>(null);
  const revisionsQuery =
    useListDocumentRevisionStatusesEndpointApiV1DocumentsDocumentIdRevisionsGet(
      documentId ?? "",
      { query: { enabled: Boolean(documentId) } },
    );
  const revisions = revisionsQuery.data ?? [];
  const selectedRevisionId =
    selection?.documentId === documentId &&
    revisions.some((revision) => revision.revision_id === selection.revisionId)
      ? selection.revisionId
      : null;
  const selectedRevision = revisions.find(
    (revision) => revision.revision_id === selectedRevisionId,
  );
  const clausesQuery =
    useGetDocumentEntitiesEndpointApiV1DocumentsDocumentIdEntitiesGet(
      documentId ?? "",
      { revision_id: selectedRevisionId },
      { query: { enabled: Boolean(documentId && selectedRevisionId) } },
    );
  const clauses = (clausesQuery.data ?? []).filter(
    (entity) => entity.type === "clause",
  );
  const trustedCurrentRevision = revisions.find(isTrustedCurrent);
  const comparingProposal = selectedRevision?.trust_state === "proposed" &&
    Boolean(trustedCurrentRevision && trustedCurrentRevision.revision_id !== selectedRevisionId);
  const baselineRevisionId = comparingProposal ? trustedCurrentRevision?.revision_id ?? null : null;
  // Read the approved A independently from the proposed B. This is a
  // source-by-source preview, not an inferred semantic diff or an approval.
  const baselineClausesQuery =
    useGetDocumentEntitiesEndpointApiV1DocumentsDocumentIdEntitiesGet(
      documentId ?? "",
      { revision_id: baselineRevisionId },
      { query: { enabled: Boolean(documentId && baselineRevisionId) } },
    );
  const baselineClauses = (baselineClausesQuery.data ?? []).filter(
    (entity) => entity.type === "clause",
  );
  const hasTrustedCurrent = Boolean(trustedCurrentRevision);

  if (!documentId) return null;

  return (
    <Card data-testid="revision-history-readonly" className="border-border/80">
      <CardHeader>
        <CardTitle>Revision-scoped evidence</CardTitle>
        <p className="text-sm text-muted-foreground">
          Read-only historical/proposed preview — never changes trusted current
          evidence, graph, Health, Coherence or active alerts.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {revisionsQuery.isLoading ? (
          <p className="text-sm">Loading revision history…</p>
        ) : revisionsQuery.isError ? (
          <p role="alert" className="text-sm text-destructive">
            Revision history could not be loaded. No extraction conclusion is available.
          </p>
        ) : revisions.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No revision history is available for this document. This is not
            evidence that zero clauses were extracted.
          </p>
        ) : (
          <>
            {!hasTrustedCurrent ? (
              <p className="text-sm text-muted-foreground">
                No trusted-current revision is available in this view. Stored
                historical or proposed clauses may still exist.
              </p>
            ) : null}
            <div className="flex flex-wrap gap-2">
              {revisions.map((revision) => (
                <Button
                  key={revision.revision_id}
                  type="button"
                  size="sm"
                  variant={
                    selectedRevisionId === revision.revision_id
                      ? "default"
                      : "outline"
                  }
                  aria-pressed={selectedRevisionId === revision.revision_id}
                  onClick={() =>
                    setSelection({
                      documentId,
                      revisionId: revision.revision_id,
                    })
                  }
                >
                  Revision {revision.rev_no ?? "unknown"} — {revisionLabel(revision)}
                </Button>
              ))}
            </div>
            {selectedRevision?.trust_state === "proposed" ? (
              <div data-testid="revision-proposal-warning" className="rounded-md border border-amber-500/30 p-3 text-sm">
                Revision {selectedRevision.rev_no ?? "unknown"} is proposed and is not authorized for current Health, Coherence, alerts or exports.
                {trustedCurrentRevision ? (
                  <span> The approved revision {trustedCurrentRevision.rev_no ?? "unknown"} remains trusted current.</span>
                ) : (
                  <span> No trusted current revision can be verified; no approved baseline is assumed.</span>
                )}
              </div>
            ) : null}
            {selectedRevision ? (
              <div
                data-testid="revision-specific-preview"
                className="rounded-md border border-border/70 p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{revisionLabel(selectedRevision)}</Badge>
                  <span className="text-xs text-muted-foreground">
                    Revision ID: {selectedRevision.revision_id}
                  </span>
                </div>
                {comparingProposal && trustedCurrentRevision ? (
                  <div data-testid="revision-a-b-comparison" className="mt-3 space-y-2 rounded-md border p-3">
                    <p className="font-medium">Approved A vs proposed B — original clause excerpts</p>
                    <p className="text-xs text-muted-foreground">
                      Read-only parallel sources, not a verified change diff. Only an approved human decision can change the trusted current revision.
                    </p>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div data-testid="revision-approved-baseline" className="rounded border p-2">
                        <p className="mb-2 font-medium">Approved revision {trustedCurrentRevision.rev_no ?? "unknown"} (A)</p>
                        {baselineClausesQuery.isLoading ? <p>Loading approved evidence…</p>
                          : baselineClausesQuery.isError ? <p role="alert">Approved revision evidence unavailable.</p>
                          : <>
                            <p>{baselineClauses.length} stored source clauses</p>
                            <ul className="mt-2 space-y-1">
                              {baselineClauses.slice(0, 3).map((clause) => (
                                <li key={clause.id} className="whitespace-pre-wrap rounded bg-muted/40 p-2">{clause.text}</li>
                              ))}
                            </ul>
                          </>}
                      </div>
                      <div data-testid="revision-proposed-source" className="rounded border p-2">
                        <p className="mb-2 font-medium">Proposed revision {selectedRevision.rev_no ?? "unknown"} (B)</p>
                        {clausesQuery.isLoading ? <p>Loading proposed evidence…</p>
                          : clausesQuery.isError ? <p role="alert">Proposed revision evidence unavailable.</p>
                          : <>
                            <p>{clauses.length} stored source clauses</p>
                            <ul className="mt-2 space-y-1">
                              {clauses.slice(0, 3).map((clause) => (
                                <li key={clause.id} className="whitespace-pre-wrap rounded bg-muted/40 p-2">{clause.text}</li>
                              ))}
                            </ul>
                          </>}
                      </div>
                    </div>
                    {projectId ? (
                      <Link className="inline-block text-sm font-medium text-primary underline-offset-4 hover:underline"
                        href={`/projects/${encodeURIComponent(projectId)}/changes`}>
                        View recorded comparisons in What Changed
                      </Link>
                    ) : null}
                  </div>
                ) : null}
                {clausesQuery.isLoading ? (
                  <p className="mt-2 text-sm">Loading this revision’s clauses…</p>
                ) : clausesQuery.isError ? (
                  <p role="alert" className="mt-2 text-sm text-destructive">
                    This revision’s evidence is unavailable. No absence of
                    extraction can be inferred.
                  </p>
                ) : (
                  <>
                    <p className="mt-2 text-sm">
                      {clauses.length} stored clauses in this selected revision
                    </p>
                    {clauses.length === 0 ? (
                      <p className="mt-2 text-xs text-muted-foreground">
                        No clause rows returned for this revision. This says
                        nothing about any other revision.
                      </p>
                    ) : (
                      <ul className="mt-2 max-h-72 space-y-2 overflow-y-auto text-sm">
                        {clauses.map((clause) => (
                          <li key={clause.id} className="rounded bg-muted/40 p-2">
                            {clause.text}
                          </li>
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
