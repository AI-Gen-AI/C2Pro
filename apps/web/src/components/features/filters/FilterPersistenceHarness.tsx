/**
 * Test Suite ID: S3-10
 * Roadmap Reference: S3-10 sessionStorage filter persistence
 */
"use client";

import { useEffect, useState } from "react";
import {
  hydrateFiltersWithMeta,
  makeFilterStorageKey,
  persistFilters,
} from "@/src/components/features/filters/filter-session-persistence";

interface FilterPersistenceHarnessProps {
  routeKey: string;
  projectId: string;
}

interface FilterState {
  severity: string[];
  owner: string;
}

const DEFAULT_FILTERS: FilterState = {
  severity: [],
  owner: "",
};

export function FilterPersistenceHarness({
  routeKey,
  projectId,
}: FilterPersistenceHarnessProps) {
  const storageKey = makeFilterStorageKey(routeKey, projectId);
  const hydrated = hydrateFiltersWithMeta(storageKey, DEFAULT_FILTERS);
  const [filters, setFilters] = useState<FilterState>(hydrated.filters);
  const [refetchState, setRefetchState] = useState("refetch:none|none");

  useEffect(() => {
    const severity = filters.severity[0] ?? "none";
    const owner = filters.owner || "none";
    setRefetchState(`refetch:${severity}|${owner}`);
  }, [filters]);

  const saveFilters = (next: FilterState) => {
    setFilters(next);
    persistFilters(storageKey, next);
  };

  return (
    <section aria-label="Filter persistence harness">
      <button
        type="button"
        onClick={() => saveFilters({ ...filters, severity: ["critical"] })}
      >
        Severity critical
      </button>
      <button
        type="button"
        onClick={() => saveFilters({ ...filters, severity: ["high"] })}
      >
        Severity high
      </button>
      <button
        type="button"
        onClick={() => saveFilters({ ...filters, owner: "legal" })}
      >
        Owner legal
      </button>

      <div data-testid="filter-state">
        severity: {filters.severity.length > 0 ? filters.severity.join(",") : "none"} | owner:{" "}
        {filters.owner || "none"}
      </div>
      <div data-testid="refetch-state">{refetchState}</div>
      {hydrated.restoredDefaults ? (
        <div role="status">Restored defaults from invalid persisted filters</div>
      ) : null}
    </section>
  );
}

