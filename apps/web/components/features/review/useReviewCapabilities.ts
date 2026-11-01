/**
 * S5-02: what the signed-in user may do on the project of ONE review (advisory).
 *
 * The server is the only authority: every action is re-validated there and answers 403/404 if the capability is
 * missing. This hook only lets the screen stop offering what would be refused.
 *
 * It costs NO request: the capabilities ride on the findings read (`ReviewFindingsResponse.capabilities`) that the
 * findings panel already makes when a review is expanded, and this hook only OBSERVES that cached read
 * (`enabled: false`). Until the panel has read it (collapsed card), or if the read failed, it is `undefined` and
 * nothing is hidden: a missing hint must never become a decision. (The API also serves
 * `GET /hitl/reviews/{row}/capabilities` for other consumers.)
 */
"use client";

import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";
import { listReviewFindingsApiV1HitlReviewsReviewRowIdFindingsGet } from "@/lib/api/generated/hitl-findings/hitl-findings";
import type { ReviewCapabilitiesSummary } from "@/lib/api/generated/models";

export const reviewFindingsKey = (orgId: string | null | undefined, userId: string | null | undefined, rowId: string) =>
  ["review-findings", orgId ?? null, userId ?? null, rowId] as const;

export function useReviewCapabilities(reviewRowId: string | null | undefined): ReviewCapabilitiesSummary | undefined {
  const { orgId, userId } = useAuth();
  const rowId = reviewRowId ?? "";
  const query = useQuery({
    queryKey: reviewFindingsKey(orgId, userId, rowId),
    queryFn: ({ signal }) => listReviewFindingsApiV1HitlReviewsReviewRowIdFindingsGet(rowId, signal),
    enabled: false, // observe only: the findings panel owns the request
  });
  return reviewRowId ? (query.data?.capabilities ?? undefined) : undefined;
}
