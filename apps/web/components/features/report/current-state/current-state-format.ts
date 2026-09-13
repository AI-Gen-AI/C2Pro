/**
 * Test Suite ID: TS-P0D-REPORT-UI-001
 * Labels and formatting for the Current State Report.
 */

/** Shared honest-null wording: unknown is never rendered as 0 or 0%. */
export const UNKNOWN_LABEL = "Unknown / Insufficient evidence";

export const SECTION_LABELS: Record<string, string> = {
  executive_summary: "Summary",
  documents: "Documents",
  health: "Health",
  missing_evidence: "Missing evidence",
  coherence: "Coherence",
  alerts: "Alerts",
  hitl: "Awaiting decision",
  budget: "Budget",
  wbs: "WBS",
  stakeholders: "Stakeholders",
  raci: "RACI",
  risks: "Risks",
  obligations: "Obligations",
  schedule: "Schedule",
  evidence_quality: "Evidence quality",
};

export const STATUS_LABELS: Record<string, string> = {
  available: "Available",
  empty: "Nothing recorded",
  unavailable: "Unavailable",
  not_modeled: "Not modeled yet",
  error: "Could not load",
};

export const STATUS_CLASSES: Record<string, string> = {
  available:
    "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  empty: "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300",
  unavailable:
    "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300",
  not_modeled:
    "border-dashed border-slate-300 bg-transparent text-slate-600 dark:border-slate-700 dark:text-slate-400",
  error: "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200",
};

export const TIER_LABELS: Record<string, string> = {
  strong_linked: "Strong source link",
  weak_linked: "Weak source link",
  unlinked: "No source link",
  unavailable: "No data to assess",
};

export const TIER_CLASSES: Record<string, string> = {
  strong_linked:
    "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  weak_linked: "border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-200",
  unlinked: "border-slate-300 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300",
  unavailable: "border-dashed border-slate-300 bg-transparent text-muted-foreground dark:border-slate-700",
};

export const LEVEL_LABELS: Record<string, string> = {
  critical: "Critical",
  warning: "Warning",
  info: "Info",
};

export const LEVEL_CLASSES: Record<string, string> = {
  critical: "border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200",
  warning: "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200",
  info: "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300",
};

export function sectionLabel(key: string): string {
  return SECTION_LABELS[key] ?? key;
}

/** The document register is itself the source record, not a clause link. */
export function tierLabel(sectionKey: string, tier: string): string {
  if (sectionKey === "documents" && tier === "strong_linked") {
    return "Source document record";
  }
  return TIER_LABELS[tier] ?? tier;
}

export function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(date);
}

export function formatMoney(value: string | number, currency: string): string {
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) {
    return String(value);
  }
  return new Intl.NumberFormat("en", { style: "currency", currency }).format(amount);
}

export function formatScore(score: number | null | undefined): string {
  return score === null || score === undefined ? UNKNOWN_LABEL : String(Math.round(score));
}

export function humanize(value: string): string {
  const spaced = value.replace(/_/g, " ").toLowerCase();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
