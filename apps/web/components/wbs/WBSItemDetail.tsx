/**
 * WBSItemDetail Component - GREEN Phase Implementation
 *
 * Suite ID: TS-UAD-WBS-DETAIL-001
 * Phase: GREEN
 *
 * Implements WBS Item Detail component with full test compliance.
 * All 12 contract tests passing.
 */

import React, { useState } from "react";
import { severityToColor } from "@/lib/ui/severity-tokens";

export interface WBSItem {
  id: string;
  code: string;
  name: string;
  description?: string;
  level: number;
  completion: number;
  budget?: {
    amount: number;
    currency: string;
  } | null;
  startDate?: string;
  endDate?: string;
  parent?: {
    id: string;
    code: string;
    name: string;
  };
  children?: Array<{
    id: string;
    code: string;
    name: string;
    completion: number;
  }>;
  alerts?: Array<{
    id: string;
    severity: string;
    message: string;
  }>;
  documents?: Array<{
    id: string;
    name: string;
    type: string;
    url: string;
  }>;
}

export interface WBSItemDetailProps {
  item: WBSItem;
  onSave?: (item: WBSItem) => void;
  onNavigate?: (itemId: string) => void;
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
 * WBSItemDetail Component - GREEN Phase Implementation
 */
export const WBSItemDetail: React.FC<WBSItemDetailProps> = ({
  item,
  onSave,
  onNavigate,
}) => {
  const [isEditMode, setIsEditMode] = useState(false);
  const [editedItem, setEditedItem] = useState<WBSItem>(item);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Handle edit mode toggle
  const handleEdit = () => {
    setEditedItem(item);
    setErrors({});
    setIsEditMode(true);
  };

  // Handle cancel edit
  const handleCancel = () => {
    setEditedItem(item);
    setErrors({});
    setIsEditMode(false);
  };

  // Validate form
  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!editedItem.name || editedItem.name.trim() === "") {
      newErrors.name = "Name is required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle save
  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();

    if (validateForm() && onSave) {
      onSave(editedItem);
      setIsEditMode(false);
    }
  };

  // Handle navigation to parent
  const handleParentClick = () => {
    if (item.parent && onNavigate) {
      onNavigate(item.parent.id);
    }
  };

  // Handle navigation to child
  const handleChildClick = (childId: string) => {
    if (onNavigate) {
      onNavigate(childId);
    }
  };

  // Handle input change
  const handleChange = (field: keyof WBSItem, value: string) => {
    setEditedItem((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <div style={{ padding: "24px", maxWidth: "800px" }}>
      {/* Header with Edit Button */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "24px",
        }}
      >
        <h1 style={{ margin: 0 }}>WBS Item Detail</h1>
        {!isEditMode && (
          <button
            onClick={handleEdit}
            style={{
              padding: "8px 16px",
              backgroundColor: "#3b82f6",
              color: "white",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            Edit
          </button>
        )}
      </div>

      {/* Parent Breadcrumb */}
      {item.parent && (
        <nav aria-label="Breadcrumb" style={{ marginBottom: "16px" }}>
          <div
            onClick={handleParentClick}
            style={{
              color: "#3b82f6",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            <span>←</span>
            <span>
              {item.parent.code} - {item.parent.name}
            </span>
          </div>
        </nav>
      )}

      {isEditMode ? (
        /* Edit Form */
        <form onSubmit={handleSave} role="form">
          <div style={{ marginBottom: "16px" }}>
            <label
              htmlFor="name"
              style={{ display: "block", marginBottom: "4px" }}
            >
              Name
            </label>
            <input
              id="name"
              type="text"
              value={editedItem.name}
              onChange={(e) => handleChange("name", e.target.value)}
              style={{
                width: "100%",
                padding: "8px",
                border: errors.name ? "1px solid #dc2626" : "1px solid #d1d5db",
                borderRadius: "4px",
              }}
            />
            {errors.name && (
              <span style={{ color: "#dc2626", fontSize: "14px" }}>
                {errors.name}
              </span>
            )}
          </div>

          <div style={{ marginBottom: "16px" }}>
            <label
              htmlFor="description"
              style={{ display: "block", marginBottom: "4px" }}
            >
              Description
            </label>
            <textarea
              id="description"
              value={editedItem.description || ""}
              onChange={(e) => handleChange("description", e.target.value)}
              style={{
                width: "100%",
                padding: "8px",
                border: "1px solid #d1d5db",
                borderRadius: "4px",
                minHeight: "100px",
              }}
            />
          </div>

          <div style={{ display: "flex", gap: "8px" }}>
            <button
              type="submit"
              style={{
                padding: "8px 16px",
                backgroundColor: "#16a34a",
                color: "white",
                border: "none",
                borderRadius: "4px",
                cursor: "pointer",
              }}
            >
              Save
            </button>
            <button
              type="button"
              onClick={handleCancel}
              style={{
                padding: "8px 16px",
                backgroundColor: "#6b7280",
                color: "white",
                border: "none",
                borderRadius: "4px",
                cursor: "pointer",
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        /* View Mode */
        <>
          {/* Item Details */}
          <div
            style={{
              backgroundColor: "#f9fafb",
              padding: "24px",
              borderRadius: "8px",
              marginBottom: "24px",
            }}
          >
            <div style={{ marginBottom: "16px" }}>
              <span
                style={{
                  fontSize: "24px",
                  fontWeight: 600,
                  color: "#111827",
                }}
              >
                {item.code}
              </span>
              <span
                style={{
                  fontSize: "24px",
                  fontWeight: 600,
                  color: "#111827",
                  marginLeft: "12px",
                }}
              >
                {item.name}
              </span>
            </div>

            {item.description && (
              <p style={{ color: "#4b5563", marginBottom: "16px" }}>
                {item.description}
              </p>
            )}

            {/* Dates */}
            <div
              style={{
                display: "flex",
                gap: "24px",
                marginBottom: "16px",
              }}
            >
              {item.startDate && (
                <div>
                  <span style={{ color: "#6b7280" }}>Start: </span>
                  <span>{item.startDate}</span>
                </div>
              )}
              {item.endDate && (
                <div>
                  <span style={{ color: "#6b7280" }}>End: </span>
                  <span>{item.endDate}</span>
                </div>
              )}
            </div>

            {/* Budget */}
            {item.budget && (
              <div>
                <span style={{ color: "#6b7280" }}>Budget: </span>
                <span style={{ fontWeight: 600 }}>
                  {formatCurrency(item.budget.amount, item.budget.currency)}
                </span>
              </div>
            )}
          </div>

          {/* Completion Chart */}
          <div style={{ marginBottom: "24px" }}>
            <h3 style={{ marginBottom: "12px" }}>Completion</h3>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "8px",
              }}
            >
              <span style={{ fontSize: "14px", color: "#6b7280" }}>
                Progress
              </span>
              <span
                style={{
                  fontSize: "18px",
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
                height: "12px",
                backgroundColor: "#e5e7eb",
                borderRadius: "6px",
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

          {/* Alerts Section */}
          {item.alerts && item.alerts.length > 0 && (
            <div style={{ marginBottom: "24px" }}>
              <h3 style={{ marginBottom: "12px" }}>Alerts</h3>
              {item.alerts.map((alert) => (
                <div
                  key={alert.id}
                  style={{
                    padding: "12px",
                    backgroundColor: "#fef3c7",
                    borderLeft: `4px solid ${severityToColor(alert.severity)}`,
                    borderRadius: "4px",
                    marginBottom: "8px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <span>{alert.message}</span>
                    <span
                      data-testid="alert-severity"
                      style={{
                        padding: "2px 8px",
                        backgroundColor: severityToColor(alert.severity),
                        color: "white",
                        borderRadius: "4px",
                        fontSize: "12px",
                      }}
                    >
                      {alert.severity}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Children List */}
          {item.children && item.children.length > 0 && (
            <div style={{ marginBottom: "24px" }}>
              <h3 style={{ marginBottom: "12px" }}>Children</h3>
              <div
                style={{
                  border: "1px solid #e5e7eb",
                  borderRadius: "8px",
                  overflow: "hidden",
                }}
              >
                {item.children.map((child) => (
                  <div
                    key={child.id}
                    onClick={() => handleChildClick(child.id)}
                    style={{
                      padding: "12px 16px",
                      borderBottom: "1px solid #e5e7eb",
                      cursor: "pointer",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      backgroundColor: "white",
                    }}
                  >
                    <span>
                      {child.code} - {child.name}
                    </span>
                    <span style={{ color: "#6b7280" }}>
                      {child.completion}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Documents Section */}
          {item.documents && item.documents.length > 0 && (
            <div>
              <h3 style={{ marginBottom: "12px" }}>Documents</h3>
              <div
                style={{ display: "flex", flexDirection: "column", gap: "8px" }}
              >
                {item.documents.map((doc) => (
                  <a
                    key={doc.id}
                    href={doc.url}
                    style={{
                      padding: "12px",
                      backgroundColor: "#eff6ff",
                      borderRadius: "4px",
                      color: "#3b82f6",
                      textDecoration: "none",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <span>📄</span>
                    <span>{doc.name}</span>
                  </a>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default WBSItemDetail;
