/**
 * WBSItemCard Component - GREEN Phase Implementation
 *
 * Suite ID: TS-UAD-WBS-CARD-001
 * Phase: GREEN
 *
 * Implements WBS Item Card component with full test compliance.
 * All 12 contract tests passing.
 */

import React from "react";
import { severityToColor } from "@/lib/ui/severity-tokens";

export interface WBSItem {
  id: string;
  code: string;
  name: string;
  level: number;
  completion: number;
  budget?: {
    amount: number;
    currency: string;
  } | null;
  startDate?: string;
  endDate?: string;
  alerts?: Array<{
    id: string;
    severity: string;
    message: string;
  }>;
}

export interface WBSItemCardProps {
  item: WBSItem;
  onClick?: (item: WBSItem) => void;
  onEdit?: (item: WBSItem) => void;
  onDelete?: (item: WBSItem) => void;
  selected?: boolean;
  disabled?: boolean;
}

/**
 * Format currency amount
 */
const formatCurrency = (amount: number, currency: string): string => {
  const formatter = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
  return formatter.format(amount);
};

/**
 * WBSItemCard Component - GREEN Phase Implementation
 */
export const WBSItemCard: React.FC<WBSItemCardProps> = ({
  item,
  onClick,
  onEdit,
  onDelete,
  selected = false,
  disabled = false,
}) => {
  // Handle card click
  const handleClick = () => {
    if (!disabled && onClick) {
      onClick(item);
    }
  };

  // Handle edit click
  const handleEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onEdit) {
      onEdit(item);
    }
  };

  // Handle delete click
  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onDelete) {
      onDelete(item);
    }
  };

  return (
    <div
      data-testid="wbs-item-card"
      data-selected={selected}
      aria-selected={selected}
      aria-disabled={disabled}
      onClick={handleClick}
      style={{
        border: selected ? "2px solid #3b82f6" : "1px solid #e5e7eb",
        borderRadius: "8px",
        padding: "16px",
        backgroundColor: disabled ? "#f3f4f6" : "#ffffff",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.6 : 1,
        boxShadow: selected ? "0 0 0 2px #bfdbfe" : "none",
        transition: "all 0.2s ease",
      }}
    >
      {/* Header: Code and Name */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "12px",
        }}
      >
        <div>
          <span
            style={{
              fontSize: "14px",
              fontWeight: 600,
              color: "#374151",
              marginRight: "8px",
            }}
          >
            {item.code}
          </span>
          <span
            style={{
              fontSize: "16px",
              fontWeight: 500,
              color: "#111827",
            }}
          >
            {item.name}
          </span>
        </div>

        {/* Alert Badge */}
        {item.alerts && item.alerts.length > 0 && (
          <div
            data-testid="alert-badge"
            data-severity={item.alerts[0].severity}
            style={{
              padding: "4px 8px",
              borderRadius: "4px",
              backgroundColor: severityToColor(item.alerts[0].severity),
              color: "#ffffff",
              fontSize: "12px",
              fontWeight: 500,
            }}
            title={item.alerts[0].message}
          >
            {item.alerts.length > 1 ? `${item.alerts.length} alerts` : "Alert"}
          </div>
        )}
      </div>

      {/* Progress Bar */}
      <div style={{ marginBottom: "12px" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "4px",
          }}
        >
          <span style={{ fontSize: "12px", color: "#6b7280" }}>Completion</span>
          <span
            style={{
              fontSize: "14px",
              fontWeight: 600,
              color: "#374151",
            }}
          >
            {item.completion}%
          </span>
        </div>
        <div
          role="progressbar"
          aria-valuenow={item.completion}
          aria-valuemin={0}
          aria-valuemax={100}
          style={{
            width: "100%",
            height: "8px",
            backgroundColor: "#e5e7eb",
            borderRadius: "4px",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${item.completion}%`,
              height: "100%",
              backgroundColor:
                item.completion === 100
                  ? "#16a34a"
                  : item.completion > 50
                    ? "#3b82f6"
                    : item.completion > 25
                      ? "#ca8a04"
                      : "#dc2626",
              transition: "width 0.3s ease",
            }}
          />
        </div>
      </div>

      {/* Budget Info */}
      {item.budget && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            marginBottom: "12px",
            padding: "8px",
            backgroundColor: "#f9fafb",
            borderRadius: "4px",
          }}
        >
          <span style={{ fontSize: "12px", color: "#6b7280" }}>Budget:</span>
          <span
            style={{
              fontSize: "14px",
              fontWeight: 600,
              color: "#374151",
            }}
          >
            {formatCurrency(item.budget.amount, item.budget.currency)}
          </span>
        </div>
      )}

      {/* Action Buttons */}
      <div
        style={{
          display: "flex",
          gap: "8px",
          justifyContent: "flex-end",
        }}
      >
        <button
          aria-label="Edit item"
          onClick={handleEdit}
          disabled={disabled}
          style={{
            padding: "6px 12px",
            fontSize: "13px",
            border: "1px solid #d1d5db",
            borderRadius: "4px",
            backgroundColor: disabled ? "#f3f4f6" : "#ffffff",
            color: disabled ? "#9ca3af" : "#374151",
            cursor: disabled ? "not-allowed" : "pointer",
          }}
        >
          Edit
        </button>
        <button
          aria-label="Delete item"
          onClick={handleDelete}
          disabled={disabled}
          style={{
            padding: "6px 12px",
            fontSize: "13px",
            border: "1px solid #ef4444",
            borderRadius: "4px",
            backgroundColor: disabled ? "#f3f4f6" : "#fee2e2",
            color: disabled ? "#9ca3af" : "#dc2626",
            cursor: disabled ? "not-allowed" : "pointer",
          }}
        >
          Delete
        </button>
      </div>
    </div>
  );
};

export default WBSItemCard;
