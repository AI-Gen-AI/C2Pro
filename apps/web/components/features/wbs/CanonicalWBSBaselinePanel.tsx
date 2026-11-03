/**
 * S7: the approved canonical WBS baseline, its revision (tree digest) and WHO approved it.
 *
 * Read-only. It reads the governed baseline list (`GET /wbs-governance/baselines`, tenant- and project-scoped by
 * the API) and shows the baseline the single authority resolver names as current. A baseline approved by the same
 * person who submitted it is labelled SELF_APPROVED_NOT_INDEPENDENT: it is never presented as an independent
 * separation of duties.
 */
"use client";

import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";
import { orvalApiClient } from "@/lib/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ProjectWBSAuthority } from "@/lib/api/generated/models";

export type CanonicalWBSBaseline = {
  id: string;
  baseline_no: number;
  parent_baseline_id: string | null;
  source_change_set_id: string;
  tree_digest: string;
  change_set_digest: string;
  node_count: number;
  self_approved: boolean;
  applied_at: string;
};

export function canonicalBaselinesQueryKey(
  orgId: string | null | undefined,
  userId: string | null | undefined,
  projectId: string,
) {
  return ["wbs-governance-baselines", orgId ?? null, userId ?? null, projectId] as const;
}

const short = (digest: string): string => digest.replace(/^sha256:/, "").slice(0, 12);

export function CanonicalWBSBaselinePanel({
  projectId,
  authority,
}: {
  projectId: string;
  authority: ProjectWBSAuthority | null;
}) {
  const { orgId, userId, isLoaded } = useAuth();
  const baselines = useQuery({
    queryKey: canonicalBaselinesQueryKey(orgId, userId, projectId),
    queryFn: () =>
      orvalApiClient<CanonicalWBSBaseline[]>({
        url: `/api/v1/projects/${encodeURIComponent(projectId)}/wbs-governance/baselines`,
        method: "GET",
      }),
    enabled: Boolean(isLoaded && userId && projectId && authority?.approved),
    staleTime: 0,
    refetchOnMount: "always",
  });

  if (!authority?.approved) {
    return (
      <Card data-testid="s7-baseline-panel" className="mt-4">
        <CardHeader>
          <CardTitle>Approved WBS baseline</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground" data-testid="s7-baseline-none">
          No approved WBS baseline: there is no canonical scope for links to rest on.
        </CardContent>
      </Card>
    );
  }

  const current = (baselines.data ?? []).find(
    (row) => row.id === authority.baseline_id || row.baseline_no === authority.baseline_no,
  );

  return (
    <Card data-testid="s7-baseline-panel" className="mt-4">
      <CardHeader>
        <CardTitle>Approved WBS baseline</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1 text-sm">
        <p data-testid="s7-baseline-label">
          {authority.scope_label} · state {authority.display_state}
        </p>
        {baselines.isLoading ? <p>Loading baseline approval…</p> : null}
        {baselines.isError ? (
          <p role="alert" data-testid="s7-baseline-error">
            The baseline approval could not be verified. No approval authority is claimed.
          </p>
        ) : null}
        {current ? (
          <>
            <p data-testid="s7-baseline-revision">
              Revision: baseline #{current.baseline_no} · tree digest{" "}
              <span className="font-mono">{short(current.tree_digest)}</span> · {current.node_count}{" "}
              {current.node_count === 1 ? "node" : "nodes"}
            </p>
            <p className="text-muted-foreground">Applied {current.applied_at.slice(0, 10)}</p>
            <p data-testid="s7-baseline-approval">
              {current.self_approved
                ? "Approval authority: a human who is also the submitter — SELF_APPROVED_NOT_INDEPENDENT. The requester and the approver are the same person; this is not an independent separation of duties."
                : "Approval authority: a human approver different from the submitter (independent approval)."}
            </p>
          </>
        ) : baselines.isSuccess ? (
          <p data-testid="s7-baseline-missing">
            The current baseline is not in the governed list: its approval authority cannot be shown.
          </p>
        ) : null}
        <p className="text-xs text-muted-foreground">
          An approved baseline is the canonical scope only. Its dates and budget are not schedule or cost authority.
        </p>
      </CardContent>
    </Card>
  );
}
