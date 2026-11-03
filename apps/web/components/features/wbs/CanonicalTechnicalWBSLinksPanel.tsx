/**
 * S7: read-only durable canonical Technical→WBS links.
 * The authenticated backend revalidates trusted source + current approved WBS
 * every time; historical approval events must never be presented as current.
 */
"use client";

import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { orvalApiClient } from "@/lib/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export type CanonicalTechnicalWBSLink = {
  event_id: string;
  review_event_id: string | null;
  approved_at: string;
  technical_document_id: string | null;
  technical_revision_id: string | null;
  source_clause_id: string | null;
  source_section: string;
  source_blob_hash: string;
  wbs_baseline_id: string | null;
  wbs_node_id: string | null;
  wbs_code: string | null;
  wbs_name: string | null;
  state: "CURRENT" | "STALE_SOURCE" | "STALE_WBS" | "STALE_BOTH" | "UNVERIFIED";
  authority: "EXPLICIT_HUMAN_CANONICAL_LINK";
  approved_canonical_link: true;
  technical_assessment: "NOT_ASSESSED";
};

export function canonicalTechnicalLinksQueryKey(
  orgId: string | null | undefined,
  userId: string | null | undefined,
  projectId: string,
) {
  return ["technical-wbs-canonical-links", orgId ?? null, userId ?? null, projectId] as const;
}

const STALE_REASON: Record<Exclude<CanonicalTechnicalWBSLink["state"], "CURRENT">, string> = {
  STALE_SOURCE: "Source revision no longer has verified trusted-current authority",
  STALE_WBS: "The approved WBS baseline or node has changed",
  STALE_BOTH: "Source and approved WBS authorities have changed",
  UNVERIFIED: "The approval event no longer has complete verifiable provenance",
};

export function CanonicalTechnicalWBSLinksPanel({ projectId }: { projectId: string }) {
  const { orgId, userId, isLoaded } = useAuth();
  const links = useQuery({
    queryKey: canonicalTechnicalLinksQueryKey(orgId, userId, projectId),
    queryFn: () => orvalApiClient<CanonicalTechnicalWBSLink[]>({
      url: `/api/v1/projects/${encodeURIComponent(projectId)}/technical-wbs/canonical-links`,
      method: "GET",
    }),
    enabled: Boolean(isLoaded && userId && projectId),
    staleTime: 0,
    refetchOnMount: "always",
  });
  const rows = links.data ?? [];
  const current = rows.filter((row) => row.state === "CURRENT");
  const historical = rows.filter((row) => row.state !== "CURRENT");

  function rowView(row: CanonicalTechnicalWBSLink) {
    const sourceLink = row.technical_document_id && row.technical_revision_id && row.source_clause_id
      ? `/projects/${encodeURIComponent(projectId)}/evidence` +
        `?documentId=${encodeURIComponent(row.technical_document_id)}` +
        `&revisionId=${encodeURIComponent(row.technical_revision_id)}` +
        `&highlightId=${encodeURIComponent(row.source_clause_id)}`
      : null;
    return (
      <li key={row.event_id} className="rounded-md border p-3 text-sm"
          data-testid={row.state === "CURRENT" ? "s7-current-canonical-link" : "s7-historical-canonical-link"}>
        <p className="font-medium">
          {row.state === "CURRENT" ? "Current approved link" : "Historical approved event — not currently authoritative"}
        </p>
        <p>Technical section {row.source_section}</p>
        <p>WBS: {row.state === "CURRENT" && row.wbs_code
          ? `${row.wbs_code} — ${row.wbs_name ?? "Unnamed node"}`
          : `previous node ${row.wbs_node_id ?? "unavailable"}`}</p>
        {row.state !== "CURRENT" ? (
          <p data-testid="s7-canonical-stale-reason" className="text-muted-foreground">
            {STALE_REASON[row.state]}
          </p>
        ) : null}
        <p className="text-muted-foreground">Approval event: {row.event_id}</p>
        <p className="text-muted-foreground">Technical compliance: NOT ASSESSED</p>
        {sourceLink ? (
          <Link className="text-primary underline underline-offset-2" href={sourceLink}>
            Inspect original approved source revision
          </Link>
        ) : (
          <p className="text-muted-foreground">Original source cannot be addressed from this event.</p>
        )}
      </li>
    );
  }

  return (
    <Card data-testid="s7-canonical-technical-links" className="mt-4">
      <CardHeader>
        <CardTitle>Approved Technical → WBS links</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          These approvals are persisted across sessions. Current status is independently
          verified against the live trusted technical revision and approved WBS baseline.
          An approved link does not itself assess technical compliance.
        </p>
        {links.isLoading ? <p>Loading persisted canonical links…</p> : null}
        {links.isError ? (
          <p role="alert" data-testid="s7-canonical-links-error">
            Canonical approvals could not be verified. No current links are claimed.
          </p>
        ) : null}
        {links.isSuccess ? (
          <>
            <p data-testid="s7-current-links-count">
              {current.length} currently authoritative technical links
            </p>
            {rows.length === 0 ? <p>No canonical Technical → WBS approvals recorded.</p> : null}
            {current.length > 0 ? <ul className="space-y-2">{current.map(rowView)}</ul> : null}
            {historical.length > 0 ? (
              <section className="space-y-2">
                <h3 className="font-semibold">Previously approved — not current</h3>
                <ul className="space-y-2">{historical.map(rowView)}</ul>
              </section>
            ) : null}
          </>
        ) : null}
        <Button type="button" size="sm" variant="outline"
          onClick={() => void links.refetch()} disabled={!isLoaded || !userId || links.isFetching}>
          Refresh canonical status
        </Button>
      </CardContent>
    </Card>
  );
}
