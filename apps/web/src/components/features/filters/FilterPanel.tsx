/**
 * Test Suite ID: S3-10
 * Roadmap Reference: S3-10 sessionStorage filter persistence
 */
"use client";

import { useState } from "react";
import {
  hydrateFilters,
  makeFilterStorageKey,
} from "@/src/components/features/filters/filter-session-persistence";

interface FilterPanelProps {
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

export function FilterPanel({ routeKey, projectId }: FilterPanelProps) {
  const storageKey = makeFilterStorageKey(routeKey, projectId);
  const [filters, setFilters] = useState<FilterState>(() =>
    hydrateFilters(storageKey, DEFAULT_FILTERS),
  );

  const resetFilters = () => {
    sessionStorage.removeItem(storageKey);
    setFilters(DEFAULT_FILTERS);
  };

  return (
    <section aria-label="Filter panel">
      <button type="button" onClick={resetFilters}>
        Reset filters
      </button>
      <div data-testid="filter-state">
        severity: {filters.severity.length > 0 ? filters.severity.join(",") : "none"} | owner:{" "}
        {filters.owner || "none"}
      </div>
    </section>
  );
}

