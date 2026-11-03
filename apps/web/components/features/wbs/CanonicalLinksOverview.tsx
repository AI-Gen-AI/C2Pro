/**
 * S7: one glance at the three canonical source families (Budget, Schedule, Technical) and whether each has a
 * CURRENT human-approved link on the approved baseline. It shares the query keys of the two detailed panels, so it
 * adds no request; a family with no current link says so instead of implying coverage.
 */
"use client";

import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";
import { orvalApiClient } from "@/lib/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ProjectWBSAuthority } from "@/lib/api/generated/models";
import {
  canonicalStructuredLinksQueryKey,
  type CanonicalStructuredWBSLink,
} from "./CanonicalStructuredWBSLinksPanel";
import {
  canonicalTechnicalLinksQueryKey,
  type CanonicalTechnicalWBSLink,
} from "./CanonicalTechnicalWBSLinksPanel";

const FAMILIES = [
  { key: "budget", label: "Budget" },
  { key: "schedule", label: "Schedule" },
  { key: "technical", label: "Technical" },
] as const;

export function CanonicalLinksOverview({
  projectId,
  authority,
}: {
  projectId: string;
  authority: ProjectWBSAuthority | null;
}) {
  const { orgId, userId, isLoaded } = useAuth();
  const enabled = Boolean(isLoaded && userId && projectId);
  const structured = useQuery({
    queryKey: canonicalStructuredLinksQueryKey(orgId, userId, projectId),
    queryFn: () =>
      orvalApiClient<CanonicalStructuredWBSLink[]>({
        url: `/api/v1/projects/${encodeURIComponent(projectId)}/structured-wbs/canonical-links`,
        method: "GET",
      }),
    enabled,
    staleTime: 0,
    refetchOnMount: "always",
  });
  const technical = useQuery({
    queryKey: canonicalTechnicalLinksQueryKey(orgId, userId, projectId),
    queryFn: () =>
      orvalApiClient<CanonicalTechnicalWBSLink[]>({
        url: `/api/v1/projects/${encodeURIComponent(projectId)}/technical-wbs/canonical-links`,
        method: "GET",
      }),
    enabled,
    staleTime: 0,
    refetchOnMount: "always",
  });

  const settled = structured.isSuccess && technical.isSuccess;
  const failed = structured.isError || technical.isError;
  const onBaseline = (baselineId: string | null) =>
    Boolean(authority?.approved && baselineId && baselineId === authority.baseline_id);
  const currentOf = (family: (typeof FAMILIES)[number]["key"]): boolean => {
    if (family === "technical") {
      return (technical.data ?? []).some((row) => row.state === "CURRENT" && onBaseline(row.wbs_baseline_id));
    }
    return (structured.data ?? []).some(
      (row) => row.family === family && row.state === "CURRENT" && onBaseline(row.wbs_baseline_id),
    );
  };
  const count = FAMILIES.filter((family) => currentOf(family.key)).length;

  return (
    <Card data-testid="s7-links-overview" className="mt-4">
      <CardHeader>
        <CardTitle>Canonical links on the approved baseline</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {failed ? (
          <p role="alert" data-testid="s7-links-overview-error">
            Canonical links could not be verified. No current links are claimed.
          </p>
        ) : !settled ? (
          <p>Verifying canonical links…</p>
        ) : (
          <>
            <p data-testid="s7-links-overview-count">
              {count} of {FAMILIES.length} source families have a CURRENT human-approved link
            </p>
            <ul className="space-y-1">
              {FAMILIES.map((family) => (
                <li key={family.key} data-testid={`s7-overview-${family.key}`}>
                  {family.label}: {currentOf(family.key) ? "CURRENT" : "no current approved link"}
                </li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}
