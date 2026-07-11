/**
 * Test Suite ID: TS-FRT-API-GEN-001
 *
 * Stable helpers around generated analysis endpoints.
 */

export function getStreamProjectProcessingUrl(
  projectId: string,
  params?: { access_token?: string },
): string {
  const base = "/api/v1/analysis/projects";
  let url = `${base}/${projectId}/process/stream`;
  if (params?.access_token) {
    url += `?access_token=${encodeURIComponent(params.access_token)}`;
  }
  return url;
}
