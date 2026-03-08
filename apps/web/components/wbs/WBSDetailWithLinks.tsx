/**
 * WBSDetailWithLinks Component - Placeholder for RED Phase
 *
 * Suite ID: TS-INT-NAV-001
 * Phase: RED
 */

import React from "react";

export interface ProcurementItem {
  id: string;
  title: string;
  status: string;
  value: number;
}

export interface WBSItemWithProcurement {
  id: string;
  code: string;
  name: string;
  procurementItems?: ProcurementItem[];
}

export interface WBSDetailWithLinksProps {
  item: WBSItemWithProcurement;
  onNavigate?: (type: string, id: string) => void;
}

export const WBSDetailWithLinks: React.FC<WBSDetailWithLinksProps> = ({
  item,
  onNavigate,
}) => {
  return (
    <section
      aria-label={`WBS detail for ${item.name}`}
      style={{
        border: "1px solid #d7dee7",
        borderRadius: 20,
        padding: 24,
        background: "linear-gradient(180deg, #fcfdff 0%, #f3f7fb 100%)",
        boxShadow: "0 14px 40px rgba(17, 24, 39, 0.08)",
      }}
    >
      <header style={{ marginBottom: 18 }}>
        <p style={{ margin: 0, fontSize: 12, letterSpacing: "0.08em", color: "#6b7280" }}>
          WBS {item.code}
        </p>
        <h2 style={{ margin: "6px 0 0", fontSize: 24, color: "#0f172a" }}>{item.name}</h2>
      </header>

      <div
        style={{
          borderRadius: 16,
          padding: 18,
          background: "#ffffff",
          border: "1px solid #e5edf5",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 14,
          }}
        >
          <h3 style={{ margin: 0, fontSize: 18, color: "#111827" }}>Procurement Links</h3>
          <span style={{ fontSize: 13, color: "#64748b" }}>
            {item.procurementItems?.length ?? 0} linked items
          </span>
        </div>

        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 12 }}>
          {item.procurementItems?.map((procurementItem) => (
            <li
              key={procurementItem.id}
              style={{
                display: "grid",
                gridTemplateColumns: "1fr auto",
                gap: 12,
                padding: 14,
                borderRadius: 14,
                background: "#f8fafc",
                border: "1px solid #e2e8f0",
              }}
            >
              <div>
                <button
                  type="button"
                  onClick={() => onNavigate?.("procurement", procurementItem.id)}
                  style={{
                    padding: 0,
                    border: 0,
                    background: "none",
                    color: "#0f172a",
                    fontSize: 16,
                    fontWeight: 700,
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  {procurementItem.title}
                </button>
                <div style={{ marginTop: 6, fontSize: 13, color: "#475569" }}>
                  Status: {procurementItem.status}
                </div>
              </div>

              <strong style={{ alignSelf: "center", color: "#14532d" }}>
                {"€" + procurementItem.value.toLocaleString("en-US")}
              </strong>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
};

export default WBSDetailWithLinks;
