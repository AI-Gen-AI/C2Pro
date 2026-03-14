/**
 * WBSAlertBadge Component
 *
 * Displays alert badges with color coding based on severity levels.
 * Supports count display, icons, and accessibility features.
 *
 * Test Suite: TS-UAD-WBS-COLOR-001
 * Phase: GREEN
 */

import React from "react";

/** Alert severity levels */
export type AlertSeverity = "none" | "low" | "medium" | "high" | "critical";

/** Props for WBSAlertBadge component */
export interface WBSAlertBadgeProps {
  /** Severity level of the alert */
  severity: AlertSeverity;
  /** Number of alerts (displays when > 1) */
  count?: number;
  /** Whether to show the severity icon */
  showIcon?: boolean;
}

/** Configuration for each severity level */
const SEVERITY_CONFIG: Record<
  AlertSeverity,
  {
    label: string;
    bgColor: string;
    textColor: string;
    icon: string;
  }
> = {
  none: {
    label: "No Alerts",
    bgColor: "#6B7280", // gray-500
    textColor: "#FFFFFF", // white
    icon: "✓",
  },
  low: {
    label: "Low Alert",
    bgColor: "#3B82F6", // blue-500
    textColor: "#FFFFFF", // white
    icon: "ℹ",
  },
  medium: {
    label: "Medium Alert",
    bgColor: "#EAB308", // yellow-500
    textColor: "#000000", // black for contrast
    icon: "⚠",
  },
  high: {
    label: "High Alert",
    bgColor: "#F97316", // orange-500
    textColor: "#FFFFFF", // white
    icon: "▲",
  },
  critical: {
    label: "Critical Alert",
    bgColor: "#DC2626", // red-600
    textColor: "#FFFFFF", // white
    icon: "✕",
  },
};

/**
 * Calculate contrast ratio between two colors
 * WCAG AA requires 4.5:1 for normal text
 */
function getContrastRatio(hex1: string, hex2: string): number {
  const luminance = (hex: string): number => {
    const rgb = parseInt(hex.slice(1), 16);
    const r = (rgb >> 16) & 0xff;
    const g = (rgb >> 8) & 0xff;
    const b = rgb & 0xff;

    const [lr, lg, lb] = [r, g, b].map((c) => {
      c /= 255;
      return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    });

    return 0.2126 * lr + 0.7152 * lg + 0.0722 * lb;
  };

  const l1 = luminance(hex1);
  const l2 = luminance(hex2);

  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);

  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * WBS Alert Badge Component
 *
 * Renders an alert badge with appropriate styling based on severity level.
 */
export function WBSAlertBadge({
  severity,
  count,
  showIcon = false,
}: WBSAlertBadgeProps): React.JSX.Element {
  const config = SEVERITY_CONFIG[severity];

  // Calculate contrast ratio for accessibility
  const contrastRatio = getContrastRatio(config.bgColor, config.textColor);
  const isContrastCompliant = contrastRatio >= 4.5;

  // Build aria-label
  const ariaLabel =
    count && count > 1 ? `${count} ${config.label}s` : config.label;

  return (
    <span
      data-testid="wbs-alert-badge"
      data-severity={severity}
      data-contrast-compliant={isContrastCompliant.toString()}
      data-count={count && count > 1 ? count : undefined}
      aria-label={ariaLabel}
      role="status"
      className={`alert-badge alert-${severity}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        padding: "4px 8px",
        borderRadius: "4px",
        backgroundColor: config.bgColor,
        color: config.textColor,
        fontSize: "14px",
        fontWeight: 500,
      }}
    >
      {showIcon && (
        <span
          data-testid={`alert-icon-${severity}`}
          style={{ display: "inline-flex" }}
          aria-hidden="true"
        >
          {config.icon}
        </span>
      )}
      {count && count > 1 && <span>{count}</span>}
    </span>
  );
}

export default WBSAlertBadge;
