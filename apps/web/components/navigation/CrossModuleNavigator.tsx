/**
 * CrossModuleNavigator Component - Placeholder for RED Phase
 *
 * Suite ID: TS-INT-NAV-001
 * Phase: RED
 */

import React from "react";

export interface CrossModuleNavigatorProps {
  coherenceData?: {
    category: string;
    score: number;
    issues: number;
  };
  onNavigate?: (type: string, id: string) => void;
}

export const CrossModuleNavigator: React.FC<CrossModuleNavigatorProps> = ({
  coherenceData,
  onNavigate,
}) => {
  if (!coherenceData) {
    return null;
  }

  return (
    <section
      aria-label="Cross module navigator"
      style={{
        display: "grid",
        gap: 12,
        padding: 24,
        borderRadius: 20,
        background: "linear-gradient(135deg, #eff6ff 0%, #ffffff 55%, #ecfeff 100%)",
        border: "1px solid #bfdbfe",
      }}
    >
      <div style={{ fontSize: 13, letterSpacing: "0.08em", textTransform: "uppercase", color: "#1d4ed8" }}>
        Coherence
      </div>
      <button
        type="button"
        onClick={() => onNavigate?.("coherence", coherenceData.category)}
        style={{
          justifySelf: "start",
          padding: "14px 18px",
          borderRadius: 16,
          border: "1px solid #93c5fd",
          background: "#ffffff",
          cursor: "pointer",
          color: "#0f172a",
          boxShadow: "0 12px 24px rgba(37, 99, 235, 0.12)",
        }}
      >
        <strong style={{ display: "block", fontSize: 30, lineHeight: 1 }}>{coherenceData.score}</strong>
        <span style={{ display: "block", marginTop: 6, fontSize: 14 }}>
          {coherenceData.category} · {coherenceData.issues} issues
        </span>
      </button>
    </section>
  );
};

export default CrossModuleNavigator;
