/**
 * Test Suite ID: TS-FRT-API-GEN-001
 *
 * Stable helpers around generated analysis endpoints.
 */

import type { StreamProjectProcessingApiV1AnalysisProjectsProjectIdProcessStreamGetParams } from "@/lib/api/generated/models";

export function getStreamProjectProcessingUrl(
  projectId: string,
  params?: StreamProjectProcessingApiV1AnalysisProjectsProjectIdProcessStreamGetParams,
): string {
  const base = "/api/v1/analysis/projects";
  let url = `${base}/${projectId}/process/stream`;
  if (params?.access_token) {
    url += `?access_token=${encodeURIComponent(params.access_token)}`;
  }
  return url;
}
