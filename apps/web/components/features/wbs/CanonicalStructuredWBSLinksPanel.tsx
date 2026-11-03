/**
 * S7: durable, human-approved Budget / Schedule source-row → canonical WBS links.
 *
 * The API revalidates, on every read, that the source revision is still trusted-current, that its bytes still hash
 * to the approved SHA-256 and that the approved WBS baseline and node are unchanged. A historical approval is never
 * presented as current. The panel shows exactly what a person needs to verify the source: document revision, SHA-256
 * and the exact locator (sheet!row), and leads to the original revision.
 */
"use client";

import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { orvalApiClient } from "@/lib/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export type CanonicalStructuredWBSLink = {
  event_id: string;
  family: "budget" | "schedule";
  approved_at: string;
  source_document_id: string | null;
  source_revision_id: string | null;
  source_locator: string;
  source_blob_hash: string;
  wbs_baseline_id: string | null;
  wbs_node_id: string | null;
  state: "CURRENT" | "STALE_SOURCE" | "STALE_WBS" | "STALE_BOTH" | "UNVERIFIED";
  authority: "EXPLICIT_HUMAN_CANONICAL_LINK";
  source_assessment: "NOT_ASSESSED";
};

export function canonicalStructuredLinksQueryKey(
  orgId: string | null | undefined,
  userId: string | null | undefined,
  projectId: string,
) {
  return ["structured-wbs-canonical-links", orgId ?? null, userId ?? null, projectId] as const;
}

const FAMILY_LABEL = { budget: "Budget row", schedule: "Schedule activity" } as const;

const STALE_REASON: Record<Exclude<CanonicalStructuredWBSLink["state"], "CURRENT">, string> = {
  STALE_SOURCE: "Source revision no longer has verified trusted-current authority or its row changed",
  STALE_WBS: "The approved WBS baseline or node has changed",
  STALE_BOTH: "Source and approved WBS authorities have changed",
  UNVERIFIED: "The approval event or the original bytes can no longer be verified",
};

export function CanonicalStructuredWBSLinksPanel({ projectId }: { projectId: string }) {
  const { orgId, userId, isLoaded } = useAuth();
  const links = useQuery({
    queryKey: canonicalStructuredLinksQueryKey(orgId, userId, projectId),
    queryFn: () =>
      orvalApiClient<CanonicalStructuredWBSLink[]>({
        url: `/api/v1/projects/${encodeURIComponent(projectId)}/structured-wbs/canonical-links`,
        method: "GET",
      }),
    enabled: Boolean(isLoaded && userId && projectId),
    staleTime: 0,
    refetchOnMount: "always",
  });
  const rows = links.data ?? [];
  const current = rows.filter((row) => row.state === "CURRENT");
  const historical = rows.filter((row) => row.state !== "CURRENT");

  function rowView(row: CanonicalStructuredWBSLink) {
    const sourceLink =
      row.source_document_id && row.source_revision_id
        ? `/projects/${encodeURIComponent(projectId)}/evidence` +
          `?documentId=${encodeURIComponent(row.source_document_id)}` +
          `&revisionId=${encodeURIComponent(row.source_revision_id)}`
        : null;
    return (
      <li
        key={row.event_id}
        className="rounded-md border p-3 text-sm"
        data-testid={`s7-${row.state === "CURRENT" ? "current" : "historical"}-structured-link-${row.family}`}
      >
        <p className="font-medium">
          {row.state === "CURRENT"
            ? `Current approved link — ${FAMILY_LABEL[row.family]}`
            : `Historical approved event — ${FAMILY_LABEL[row.family]}, not currently authoritative`}
        </p>
        <p>
          Locator: <span className="font-mono">{row.source_locator}</span>
        </p>
        <p className="text-muted-foreground">
          Revision <span className="font-mono">{row.source_revision_id ?? "unavailable"}</span>
        </p>
        <p className="text-muted-foreground">
          SHA-256 <span className="font-mono break-all">{row.source_blob_hash}</span>
        </p>
        {row.state !== "CURRENT" ? (
          <p data-testid="s7-structured-stale-reason" className="text-muted-foreground">
            {STALE_REASON[row.state]}
          </p>
        ) : null}
        <p className="text-muted-foreground">Approval event: {row.event_id}</p>
        <p className="text-muted-foreground">Source content: NOT ASSESSED</p>
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
    <Card data-testid="s7-canonical-structured-links" className="mt-4">
      <CardHeader>
        <CardTitle>Approved Budget / Schedule → WBS links</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          These approvals are persisted across sessions and re-verified against the trusted source revision, its
          original bytes and the approved WBS baseline on every read. A link does not approve costs, dates or any
          score.
        </p>
        {links.isLoading ? <p>Loading persisted canonical links…</p> : null}
        {links.isError ? (
          <p role="alert" data-testid="s7-structured-links-error">
            Canonical approvals could not be verified. No current links are claimed.
          </p>
        ) : null}
        {links.isSuccess ? (
          <>
            <p data-testid="s7-current-structured-links-count">
              {current.length} currently authoritative Budget / Schedule links
            </p>
            {rows.length === 0 ? <p>No canonical Budget / Schedule approvals recorded.</p> : null}
            {current.length > 0 ? <ul className="space-y-2">{current.map(rowView)}</ul> : null}
            {historical.length > 0 ? (
              <section className="space-y-2">
                <h3 className="font-semibold">Previously approved — not current</h3>
                <ul className="space-y-2">{historical.map(rowView)}</ul>
              </section>
            ) : null}
          </>
        ) : null}
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => void links.refetch()}
          disabled={!isLoaded || !userId || links.isFetching}
        >
          Refresh canonical status
        </Button>
      </CardContent>
    </Card>
  );
}
