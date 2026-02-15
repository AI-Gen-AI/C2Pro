/**
 * Test Suite ID: S3-07
 * Roadmap Reference: S3-07 Severity badge + Stakeholder Map + RACI
 */
"use client";

type KnownSeverity = "critical" | "high" | "medium" | "low";

interface SeverityBadgeProps {
  severity: KnownSeverity | string;
}

function normalizeSeverity(severity: string): string {
  const value = severity.toLowerCase();
  if (value === "critical" || value === "high" || value === "medium" || value === "low") {
    return value;
  }
  return "unknown";
}

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  const normalized = normalizeSeverity(severity);
  const label = normalized.charAt(0).toUpperCase() + normalized.slice(1);

  return (
    <span
      data-testid={`severity-badge-${normalized}`}
      className={`severity-${normalized}`}
      aria-label={`Severity ${label}`}
    >
      {label}
    </span>
  );
}

