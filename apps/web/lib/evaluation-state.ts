/**
 * "Not evaluated" is not "zero" and not "no issues".
 *
 * A null/missing coherence score means no coherence evaluation produced one. It must never be shown as 0, and an
 * empty alert list before any evaluation must never be read as "nothing requires attention".
 */
export const NOT_EVALUATED_LABEL = "Not evaluated";

export const ALERTS_NOT_EVALUATED_MESSAGE =
  "Alerts have not been evaluated yet: no coherence evaluation has run. An empty list here does not mean the project is free of issues.";

/** A finite number, or `null` when no score exists (never coerced to 0). */
export function scoreOrNull(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
