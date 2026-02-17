/**
 * GlobalSearch Component - Placeholder for RED Phase
 *
 * Suite ID: TS-INT-NAV-001
 * Phase: RED
 */

import React from "react";

export interface SearchResult {
  type: string;
  id: string;
  title: string;
  module: string;
}

export interface GlobalSearchProps {
  onSearch?: (query: string) => Promise<SearchResult[]>;
  onSelect?: (type: string, id: string) => void;
  results?: SearchResult[];
}

export const GlobalSearch: React.FC<GlobalSearchProps> = () => {
  throw new Error(
    "GlobalSearch component not implemented. " +
      "This is expected during RED phase (TS-INT-NAV-001).",
  );
};

export default GlobalSearch;
