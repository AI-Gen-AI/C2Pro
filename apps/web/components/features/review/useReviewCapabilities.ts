/**
 * S5-02: what the signed-in user may do on the project of ONE review (advisory).
 *
 * The server is the only authority: every action is re-validated there and answers 403/404 if the capability is
 * missing. This hook only lets the screen stop offering what would be refused. While loading, or if the read itself
 * fails, nothing is hidden (`undefined`): a failed hint must never become a decision.
 */
"use client";

import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";
import { getReviewCapabilitiesApiV1HitlReviewsReviewRowIdCapabilitiesGet } from "@/lib/api/generated/hitl-findings/hitl-findings";
import type { ReviewCapabilitiesResponse } from "@/lib/api/generated/models";

export function useReviewCapabilities(reviewRowId: string | null | undefined): ReviewCapabilitiesResponse | undefined {
  const { orgId, userId, isLoaded } = useAuth();
  const query = useQuery({
    queryKey: ["review-capabilities", orgId ?? null, userId ?? null, reviewRowId ?? null],
    queryFn: ({ signal }) =>
      getReviewCapabilitiesApiV1HitlReviewsReviewRowIdCapabilitiesGet(reviewRowId as string, signal),
    enabled: Boolean(isLoaded && userId && reviewRowId),
    retry: false,
    staleTime: 0,
  });
  return query.data;
}
