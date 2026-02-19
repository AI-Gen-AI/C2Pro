/**
 * Test Suite ID: S3-03
 * Roadmap Reference: S3-03 Dynamic watermark (pseudonymized ID)
 */

export interface WatermarkTokenInput {
  tenantId: string;
  userSeed: string;
  sessionNonce: string;
}

function hashToBase36(input: string): string {
  let hash = 2166136261;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }

  const unsigned = hash >>> 0;
  return unsigned.toString(36).toUpperCase().padStart(8, "0").slice(0, 8);
}

export function createWatermarkToken(input: WatermarkTokenInput): string {
  const composed = `${input.tenantId}|${input.userSeed}|${input.sessionNonce}`;
  return `USR-${hashToBase36(composed)}`;
}
