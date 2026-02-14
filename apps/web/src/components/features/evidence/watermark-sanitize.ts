/**
 * Test Suite ID: S3-03
 * Roadmap Reference: S3-03 Dynamic watermark (pseudonymized ID)
 */

export interface WatermarkPayloadInput {
  pseudonymId?: unknown;
  timestampIso?: unknown;
  environment?: unknown;
  note?: unknown;
  [key: string]: unknown;
}

export interface SafeWatermarkPayload {
  pseudonymId?: string;
  timestampIso?: string;
  environment?: string;
  note?: string;
}

function scrubPotentialPii(value: string): string {
  return value
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[redacted-email]")
    .replace(/\+?\d[\d()\-\s]{7,}\d/g, "[redacted-phone]")
    .replace(/\s+/g, " ")
    .trim();
}

function sanitizeString(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const normalized = scrubPotentialPii(value);
  return normalized.length > 0 ? normalized : undefined;
}

export function sanitizeWatermarkPayload(input: WatermarkPayloadInput): SafeWatermarkPayload {
  const safe: SafeWatermarkPayload = {};

  const pseudonymId = sanitizeString(input.pseudonymId);
  const timestampIso = sanitizeString(input.timestampIso);
  const environment = sanitizeString(input.environment);
  const note = sanitizeString(input.note);

  if (pseudonymId) safe.pseudonymId = pseudonymId;
  if (timestampIso) safe.timestampIso = timestampIso;
  if (environment) safe.environment = environment;
  if (note) safe.note = note;

  return safe;
}
