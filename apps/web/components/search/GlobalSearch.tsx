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

export const GlobalSearch: React.FC<GlobalSearchProps> = ({
  onSearch,
  onSelect,
  results = [],
}) => {
  const [query, setQuery] = React.useState("");

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSearch?.(query);
  };

  return (
    <section
      aria-label="Global search"
      style={{
        borderRadius: 20,
        padding: 24,
        background: "linear-gradient(135deg, #111827 0%, #1f2937 50%, #0f766e 100%)",
        color: "#f8fafc",
      }}
    >
      <form onSubmit={handleSubmit}>
        <label htmlFor="global-search-input" style={{ display: "block", marginBottom: 10, fontWeight: 700 }}>
          Search across modules
        </label>
        <input
          id="global-search-input"
          placeholder="Search projects, procurement, documents..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          style={{
            width: "100%",
            borderRadius: 14,
            border: "1px solid rgba(255,255,255,0.24)",
            padding: "14px 16px",
            background: "rgba(255,255,255,0.12)",
            color: "#f8fafc",
          }}
        />
      </form>

      <ul style={{ listStyle: "none", margin: "18px 0 0", padding: 0, display: "grid", gap: 12 }}>
        {results.map((result) => (
          <li
            key={`${result.type}-${result.id}`}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              padding: 14,
              borderRadius: 14,
              background: "rgba(255,255,255,0.1)",
              border: "1px solid rgba(255,255,255,0.16)",
            }}
          >
            <button
              type="button"
              onClick={() => onSelect?.(result.type, result.id)}
              style={{
                padding: 0,
                border: 0,
                background: "none",
                color: "#f8fafc",
                fontSize: 16,
                fontWeight: 700,
                textAlign: "left",
                cursor: "pointer",
              }}
            >
              {result.title}
            </button>
            <span style={{ fontSize: 13, color: "#bfdbfe" }}>{result.module}</span>
          </li>
        ))}
      </ul>
    </section>
  );
};

export default GlobalSearch;
