/**
 * Test Suite ID: TS-FRT-API-GEN-001
 *
 * Stable helpers around generated analysis endpoints.
 */

export function getStreamProjectProcessingUrl(projectId: string): string {
  return `/api/v1/analysis/projects/${projectId}/process/stream`;
}
