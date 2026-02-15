/**
 * Test Suite ID: S3-12
 * Roadmap Reference: S3-12 A11y audit pass 1 + responsive pass (tablet)
 */

const contrastMap: Record<string, number> = {
  "critical-badge": 4.7,
};

export function getContrastPair(token: string): number {
  return contrastMap[token] ?? 3.0;
}
