/**
 * CategoryStatusBadge — ADR-009 §4.3, §18.
 *
 * Renders the per-category status with the ECOA color contract:
 *   - red (destructive) is RESERVED for `conflicting_evidence` only.
 *   - neutral gray for `insufficient_evidence` and `not_applicable`.
 *   - amber-orange for `processing_error`.
 *   - blue for `pending_documents`.
 *   - neutral gray for `not_applicable`.
 *   - success green for `scored`.
 */
import { cn } from "@/lib/utils";
import type { CategoryStatus } from "@/lib/api/contracts";

const STATUS_CONFIG: Record<
  CategoryStatus,
  { label: string; className: string; testid: string }
> = {
  scored: {
    label: "Scored",
    className: "bg-emerald-100 text-emerald-900 border-emerald-300 dark:bg-emerald-900/40 dark:text-emerald-100 dark:border-emerald-700",
    testid: "status-badge-success",
  },
  conflicting_evidence: {
    label: "Conflicting evidence",
    className: "bg-red-100 text-red-900 border-red-300 dark:bg-red-900/40 dark:text-red-100 dark:border-red-700",
    testid: "status-badge-destructive",
  },
  insufficient_evidence: {
    label: "Insufficient evidence",
    className: "bg-gray-100 text-gray-800 border-gray-300 dark:bg-gray-800/60 dark:text-gray-100 dark:border-gray-700",
    testid: "status-badge-neutral",
  },
  processing_error: {
    label: "Processing error",
    className: "bg-orange-100 text-orange-900 border-orange-400 dark:bg-orange-900/40 dark:text-orange-100 dark:border-orange-700",
    testid: "status-badge-error",
  },
  pending_documents: {
    label: "Pending documents",
    className: "bg-blue-100 text-blue-900 border-blue-300 dark:bg-blue-900/40 dark:text-blue-100 dark:border-blue-700",
    testid: "status-badge-info",
  },
  not_applicable: {
    label: "Not applicable",
    className: "bg-gray-100 text-gray-700 border-gray-300 dark:bg-gray-800/60 dark:text-gray-200 dark:border-gray-700",
    testid: "status-badge-not-applicable",
  },
};

export interface CategoryStatusBadgeProps {
  status: CategoryStatus;
  className?: string;
}

export function CategoryStatusBadge({ status, className }: CategoryStatusBadgeProps) {
  const cfg = STATUS_CONFIG[status];
  return (
    <span
      data-testid={cfg.testid}
      data-status={status}
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
        cfg.className,
        className,
      )}
    >
      {cfg.label}
    </span>
  );
}
