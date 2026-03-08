/**
 * AlertDetailWithLinks Component - Placeholder for RED Phase
 *
 * Suite ID: TS-INT-NAV-001
 * Phase: RED
 */

import React from "react";

export interface AffectedEntity {
  type: string;
  id: string;
  name: string;
}

export interface AlertWithEntities {
  id: string;
  severity: string;
  message: string;
  affectedEntities?: AffectedEntity[];
}

export interface AlertDetailWithLinksProps {
  alert: AlertWithEntities;
  onNavigate?: (type: string, id: string) => void;
}

export const AlertDetailWithLinks: React.FC<AlertDetailWithLinksProps> = ({
  alert,
  onNavigate,
}) => {
  return (
    <section
      aria-label={`Alert detail for ${alert.id}`}
      style={{
        borderRadius: 20,
        padding: 24,
        background: "linear-gradient(135deg, #fff7ed 0%, #ffffff 55%, #f8fafc 100%)",
        border: "1px solid #fed7aa",
        boxShadow: "0 16px 36px rgba(124, 45, 18, 0.08)",
      }}
    >
      <header style={{ marginBottom: 18 }}>
        <div style={{ fontSize: 13, fontWeight: 700, textTransform: "uppercase", color: "#c2410c" }}>
          {alert.severity} severity alert
        </div>
        <p style={{ margin: "8px 0 0", fontSize: 18, color: "#111827" }}>
          Cross-module impact detected for downstream records.
        </p>
      </header>

      <div
        style={{
          borderRadius: 16,
          padding: 18,
          background: "#ffffff",
          border: "1px solid #ffedd5",
        }}
      >
        <h3 style={{ margin: "0 0 14px", fontSize: 18, color: "#111827" }}>Affected Entities</h3>
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 12 }}>
          {alert.affectedEntities?.map((entity) => (
            <li
              key={`${entity.type}-${entity.id}`}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                padding: 12,
                borderRadius: 14,
                background: "#fffaf5",
                border: "1px solid #fed7aa",
              }}
            >
              <button
                type="button"
                onClick={() => onNavigate?.(entity.type, entity.id)}
                style={{
                  padding: 0,
                  border: 0,
                  background: "none",
                  fontSize: 16,
                  fontWeight: 700,
                  color: "#7c2d12",
                  cursor: "pointer",
                  textAlign: "left",
                }}
              >
                {entity.name}
              </button>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  color: "#9a3412",
                }}
              >
                {entity.type}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
};

export default AlertDetailWithLinks;
