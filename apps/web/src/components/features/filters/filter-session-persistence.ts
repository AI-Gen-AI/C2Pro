/**
 * Test Suite ID: S3-10
 * Roadmap Reference: S3-10 sessionStorage filter persistence
 */

export const FILTER_STORAGE_VERSION = "s3-10-v1";

interface PersistEnvelope<TFilters> {
  version: string;
  filters: TFilters;
}

interface LegacyEnvelope {
  version: "legacy-v1";
  severity?: string;
  owner_name?: string;
}

export interface HydrateResult<TFilters> {
  filters: TFilters;
  restoredDefaults: boolean;
}

export function makeFilterStorageKey(routeKey: string, projectId: string): string {
  return `filters:${routeKey}:${projectId}`;
}

export function persistFilters<TFilters extends Record<string, unknown>>(
  key: string,
  filters: TFilters,
): void {
  const envelope: PersistEnvelope<TFilters> = {
    version: FILTER_STORAGE_VERSION,
    filters,
  };
  sessionStorage.setItem(key, JSON.stringify(envelope));
}

function isLegacyEnvelope(value: unknown): value is LegacyEnvelope {
  if (!value || typeof value !== "object") return false;
  return (value as { version?: string }).version === "legacy-v1";
}

export function hydrateFiltersWithMeta<TFilters extends Record<string, unknown>>(
  key: string,
  defaults: TFilters,
): HydrateResult<TFilters> {
  const raw = sessionStorage.getItem(key);
  if (!raw) {
    return { filters: defaults, restoredDefaults: false };
  }

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (isLegacyEnvelope(parsed)) {
      const migrated = {
        ...defaults,
        severity: parsed.severity ? [parsed.severity] : [],
        owner: parsed.owner_name ?? "",
      } as TFilters;
      return { filters: migrated, restoredDefaults: false };
    }

    const current = parsed as PersistEnvelope<TFilters>;
    if (current.version === FILTER_STORAGE_VERSION && current.filters) {
      return { filters: current.filters, restoredDefaults: false };
    }

    return { filters: defaults, restoredDefaults: true };
  } catch {
    return { filters: defaults, restoredDefaults: true };
  }
}

export function hydrateFilters<TFilters extends Record<string, unknown>>(
  key: string,
  defaults: TFilters,
): TFilters {
  return hydrateFiltersWithMeta(key, defaults).filters;
}

