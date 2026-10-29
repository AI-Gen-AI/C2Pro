/**
 * S7: current canonical Technical→WBS links are a read projection of durable
 * approval events, not React state or audit-only decisions.
 * Every mount queries the authenticated backend (including after relogin).
 */
"use client";

import { useMemo } from "react";
import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import type { WBSTreeItem } from "@/hooks/useWBSTree";
import type { ProjectWBSAuthority } from "@/lib/api/generated/models";
import { orvalApiClient } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export type CanonicalTechnicalLink = {
  event_id: string;
  occurred_at: string;
  review_event_id: string;
  technical_document_id: string;
  technical_revision_id: string;
  source_clause_id: string;
  source_section: string;
  wbs_baseline_id: string;
  wbs_node_id: string;
  current_state: "CURRENT_VERIFIED" | "HISTORICAL_NOT_CURRENT";
  state_reason: string;
  authority: "EXPLICIT_HUMAN_CANONICAL_LINK";
  approval: "APPROVE_CANONICAL_LINK";
  technical_assessment: "NOT_ASSESSED";
};

export function canonicalTechnicalLinksKey(
  orgId: string | null | undefined,
  userId: string | null | undefined,
  projectId: string,
) {
  return ["technical-wbs-canonical-links", orgId ?? "personal", userId ?? "", projectId] as const;
}

function namesByNode(items: WBSTreeItem[]): Map<string, string> {
  const map = new Map<string, string>();
  function visit(nodes: WBSTreeItem[]) {
    for (const node of nodes) {
      map.set(node.id, `${node.code}: ${node.name}`);
      visit(node.children);
    }
  }
  visit(items);
  return map;
}

type Props = {
  projectId: string;
  authority: ProjectWBSAuthority | null;
  items: WBSTreeItem[];
};

export function CanonicalTechnicalWBSLinksPanel({ projectId, authority, items }: Props) {
  const { userId, orgId, isLoaded } = useAuth();
  const key = canonicalTechnicalLinksKey(orgId, userId, projectId);
  const query = useQuery({
    queryKey: key,
    queryFn: () => orvalApiClient<CanonicalTechnicalLink[]>({
      url: `/api/v1/projects/${encodeURIComponent(projectId)}/technical-wbs/canonical-links`,
      method: "GET",
    }),
    enabled: Boolean(isLoaded && userId && projectId),
  });
  const nodes = useMemo(() => namesByNode(items), [items]);
  const links = query.data ?? [];
  const isCurrent = (item: CanonicalTechnicalLink) =>
    item.current_state === "CURRENT_VERIFIED" &&
    item.authority === "EXPLICIT_HUMAN_CANONICAL_LINK" &&
    item.approval === "APPROVE_CANONICAL_LINK" &&
    item.technical_assessment === "NOT_ASSESSED" &&
    authority?.approved === true &&
    authority.baseline_id === item.wbs_baseline_id &&
    nodes.has(item.wbs_node_id);
  const currentCount = links.filter(isCurrent).length;

  return (
    <Card data-testid="technical-wbs-canonical-links">
      <CardHeader>
        <CardTitle>Technical → WBS approved links</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p className="text-muted-foreground">
          Reconstructed from durable, explicit human approvals. Only links with
          a currently trusted technical revision and the active approved WBS
          baseline are marked current. Technical compliance remains not assessed.
        </p>
        {query.isLoading ? <p>Loading recorded approvals…</p> : null}
        {query.isError ? (
          <p role="alert" data-testid="technical-wbs-canonical-read-error">
            Approved link history could not be verified. No current association is claimed.
          </p>
        ) : null}
        {query.isSuccess ? (
          <>
            <p data-testid="technical-wbs-current-count" className="font-medium">
              {currentCount} currently verified Technical link{currentCount === 1 ? "" : "s"} (in this page of history)
            </p>
            {links.length === 0 ? (
              <p data-testid="technical-wbs-canonical-empty">
                No approved Technical→WBS events in this project history.
              </p>
            ) : (
              <ul className="space-y-2">
                {links.map((link) => {
                  const current = isCurrent(link);
                  return (
                    <li key={link.event_id} data-testid="technical-wbs-canonical-item"
                        className="space-y-2 rounded border p-3">
                      <p data-testid={`technical-wbs-link-state-${link.event_id}`} className="font-semibold">
                        {current ? "Approved and currently verified" : "Approved historically — not verified current"}
                      </p>
                      <p>Technical section {link.source_section} → WBS {nodes.get(link.wbs_node_id) ?? link.wbs_node_id}</p>
                      <p className="text-muted-foreground">
                        {current
                          ? "Explicit link approval is current; technical compliance NOT ASSESSED."
                          : "The original approval is retained, but its source or WBS authority is not currently verified."}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Approval event: <code>{link.event_id}</code>
                      </p>
                      <Link className="inline-block text-primary underline-offset-4 hover:underline"
                        href={
                          `/projects/${encodeURIComponent(projectId)}/evidence` +
                          `?documentId=${encodeURIComponent(link.technical_document_id)}` +
                          `&revisionId=${encodeURIComponent(link.technical_revision_id)}` +
                          `&highlightId=${encodeURIComponent(link.source_clause_id)}`
                        }>
                        Inspect exact original source revision
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </>
        ) : null}
        <Button type="button" variant="outline" size="sm"
          data-testid="technical-wbs-refresh-approved"
          disabled={!isLoaded || !userId || query.isFetching}
          onClick={() => void query.refetch()}>
          Refresh approved links
        </Button>
      </CardContent>
    </Card>
  );
}
