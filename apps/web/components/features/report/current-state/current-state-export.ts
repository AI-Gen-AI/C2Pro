/**
 * Test Suite ID: TS-P0D-REPORT-UI-004
 * Current State Report export.
 *
 * JSON is the exact backend payload. CSV flattens it into one row per section,
 * metric and item, stamps every row with report identity and generation time,
 * and keeps unknown values distinguishable from zero through `value_state`.
 */
import type { CurrentStateReport } from "@/lib/api/generated/models";

export const CSV_COLUMNS = [
  "report_schema_version",
  "generated_at",
  "project_id",
  "project_name",
  "project_code",
  "content_fingerprint",
  "section",
  "section_status",
  "status_reason",
  "source_domain",
  "source_as_of",
  "source_as_of_state",
  "evidence_tier",
  "evidence_note",
  "record_type",
  "record_id",
  "record_label",
  "field",
  "value",
  "value_state",
  "record_status",
  "record_due_at",
  "record_overdue",
  "record_evidence_tier",
  "record_source_ref",
] as const;

type Column = (typeof CSV_COLUMNS)[number];
type CsvRow = Partial<Record<Column, string>>;
type Cell = string | number | boolean | null | undefined;
type ItemRow = Omit<CsvRow, "value" | "value_state"> & { value?: Cell };
type Sections = CurrentStateReport["sections"];
type SectionKey = keyof Sections;

const SECTION_ORDER: SectionKey[] = [
  "executive_summary",
  "documents",
  "health",
  "missing_evidence",
  "coherence",
  "alerts",
  "hitl",
  "budget",
  "wbs",
  "stakeholders",
  "raci",
  "risks",
  "obligations",
  "schedule",
  "evidence_quality",
];

const NUMERIC = /^-?\d+(\.\d+)?$/;
// Spreadsheets evaluate a leading = + - @ (some after trimming whitespace), tab or CR.
const FORMULA_TRIGGER = /^(\s*[=+\-@]|[\t\r])/;
const MAX_FILENAME_PART = 80;
// A byte-order mark lets spreadsheet software read UTF-8 names correctly.
const UTF8_BOM = String.fromCharCode(0xfeff);

export function buildCurrentStateJson(report: CurrentStateReport): string {
  return JSON.stringify(report, null, 2);
}

export function buildCurrentStateCsv(report: CurrentStateReport): string {
  const identity: CsvRow = {
    report_schema_version: report.report_schema_version,
    generated_at: report.generated_at,
    project_id: report.project.id,
    project_name: report.project.name,
    project_code: report.project.code ?? "",
    content_fingerprint: report.content_fingerprint,
  };

  const lines = [CSV_COLUMNS.join(",")];
  for (const key of SECTION_ORDER) {
    for (const row of sectionRows(key, report.sections)) {
      const full: CsvRow = { ...identity, ...row };
      lines.push(CSV_COLUMNS.map((column) => escapeCell(full[column] ?? "")).join(","));
    }
  }
  return `${lines.join("\r\n")}\r\n`;
}

export function currentStateExportFilename(report: CurrentStateReport, extension: "json" | "csv"): string {
  const slug = sanitizeFilenamePart(report.project.code || report.project.id);
  const parsed = new Date(report.generated_at);
  const stamp = Number.isNaN(parsed.getTime())
    ? "undated"
    : parsed.toISOString().replace(/\.\d+Z$/, "Z").replace(/[-:]/g, "");
  return `current-state-report-${slug}-${stamp}.${extension}`;
}

export function downloadTextFile(filename: string, content: string, mimeType: string): void {
  const body = mimeType.startsWith("text/csv") ? UTF8_BOM + content : content;
  const url = URL.createObjectURL(new Blob([body], { type: mimeType }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  // Some browsers ignore clicks on detached links or cancel downloads whose URL
  // is revoked before they start, so attach first and revoke on the next tick.
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

// ---------------------------------------------------------------------------
// Row construction
// ---------------------------------------------------------------------------

function sectionRows(key: SectionKey, sections: Sections): CsvRow[] {
  const section = sections[key];
  const sectionRow: CsvRow = {
    section: key,
    section_status: section.status,
    status_reason: section.status_reason ?? "",
    source_domain: section.source_domain,
    source_as_of: section.source_as_of ?? "",
    source_as_of_state: section.source_as_of ? "known" : "null",
    evidence_tier: section.evidence_tier,
    evidence_note: section.evidence_note ?? "",
    record_type: "section",
  };
  return [sectionRow, ...detailRows(key, sections).map((row) => ({ ...sectionRow, ...row }))];
}

function metric(field: string, value: Cell): CsvRow {
  const known = value !== null && value !== undefined;
  return { record_type: "metric", field, value: known ? String(value) : "", value_state: known ? "known" : "null" };
}

function counts(prefix: string, values: Record<string, number> | undefined): CsvRow[] {
  return Object.entries(values ?? {}).map(([name, count]) => metric(`${prefix}.${name}`, count));
}

function item({ value, ...rest }: ItemRow): CsvRow {
  if (value === undefined) {
    return { record_type: "item", ...rest };
  }
  const known = value !== null;
  return { record_type: "item", ...rest, value: known ? String(value) : "", value_state: known ? "known" : "null" };
}

function namesOrNone(names: string[]): string {
  return names.length > 0 ? names.join("; ") : "none";
}

function detailRows(key: SectionKey, sections: Sections): CsvRow[] {
  switch (key) {
    case "executive_summary": {
      const data = sections.executive_summary.data;
      if (!data) return [];
      return [
        metric("document_count", data.document_count),
        // Lifecycle counts only: the polling "parsed" count includes analyzed documents and a
        // spreadsheet cannot carry that distinction (the JSON export keeps every field).
        metric("analyzed_document_count", data.analyzed_document_count),
        metric("awaiting_analysis_document_count", data.awaiting_analysis_document_count),
        ...data.attention_items.map((entry) =>
          item({ record_id: entry.kind, record_label: entry.message, field: entry.level, value: entry.section_key }),
        ),
      ];
    }
    case "documents": {
      const data = sections.documents.data;
      if (!data) return [];
      return [
        metric("total", data.total),
        metric("counts_are_partial", data.counts_are_partial),
        metric("truncated", data.truncated),
        ...counts("by_lifecycle_status", data.by_lifecycle_status),
        ...counts("by_type", data.by_type),
        ...data.items.map((document) =>
          item({
            record_id: document.id,
            record_label: document.filename,
            field: "document_type",
            value: document.document_type,
            record_status: document.lifecycle_status,
            record_source_ref: document.id,
          }),
        ),
      ];
    }
    case "health": {
      const data = sections.health.data;
      if (!data) return [];
      // The six canonical categories with the same facts the screen shows; no composite.
      return [
        metric("computed_at", data.computed_at),
        metric("evidence_granularity", data.evidence_granularity),
        ...data.categories.flatMap((category) => {
          const record = { record_id: category.category, record_label: category.category, record_status: category.state };
          return [
            item({ ...record, field: "state", value: category.state }),
            item({ ...record, field: "evidence_count", value: category.evidence_count }),
            item({ ...record, field: "missing_data", value: (category.missing_data ?? []).join("; ") }),
            item({ ...record, field: "gap", value: category.gap ?? null }),
          ];
        }),
      ];
    }
    case "missing_evidence": {
      const data = sections.missing_evidence.data;
      if (!data) return [];
      return data.items.map((gap) =>
        item({
          record_id: `${gap.source_domain}:${gap.subject}`,
          record_label: gap.description,
          field: gap.source_domain,
          value: gap.subject,
        }),
      );
    }
    case "coherence": {
      const data = sections.coherence.data;
      if (!data) return [];
      return [
        metric("score", data.score),
        metric("score_version", data.score_version),
        metric("score_reason", data.score_reason),
        metric("evaluation_alert_count", data.evaluation_alert_count),
        metric("last_activity_at", data.last_activity_at),
        metric("missing_dimensions", (data.missing_dimensions ?? []).join("; ")),
        ...Object.entries(data.sub_scores ?? {}).map(([name, score]) => metric(`sub_scores.${name}`, score)),
      ];
    }
    case "alerts": {
      const data = sections.alerts.data;
      if (!data) return [];
      return [
        metric("total", data.total),
        metric("open_count", data.open_count),
        metric("overdue_open_count", data.overdue_open_count),
        metric("truncated", data.truncated),
        ...counts("open_by_severity", data.open_by_severity),
        ...data.items.map((alert) =>
          item({
            record_id: alert.id,
            record_label: alert.title,
            field: "severity",
            value: alert.severity,
            record_status: alert.status,
            record_due_at: alert.sla_due_at ?? "",
            record_overdue: String(alert.overdue),
            record_evidence_tier: alert.evidence_tier,
            record_source_ref: alert.source_clause_id ?? "",
          }),
        ),
      ];
    }
    case "hitl": {
      const data = sections.hitl.data;
      if (!data) return [];
      return [
        metric("pending_count", data.pending_count),
        metric("overdue_count", data.overdue_count),
        metric("truncated", data.truncated),
        ...data.items.map((review) =>
          item({
            record_id: review.item_id,
            record_label: review.item_type,
            field: "impact_level",
            value: review.impact_level,
            record_status: review.status,
            record_due_at: review.sla_due_date,
            record_overdue: String(review.overdue),
          }),
        ),
      ];
    }
    case "budget": {
      const data = sections.budget.data;
      if (!data) return [];
      return [
        metric("item_count", data.item_count),
        metric("total_budget", data.total_budget),
        metric("spent_amount", data.spent_amount),
        metric("remaining_budget", data.remaining_budget),
        metric("currency", data.currency),
        ...data.notes.map((note) => ({ record_type: "note", record_label: note }) satisfies CsvRow),
        ...data.items.map((line) =>
          item({
            record_id: line.id,
            record_label: line.name,
            field: "amount",
            value: String(line.amount),
            record_status: line.code,
          }),
        ),
      ];
    }
    case "wbs": {
      const data = sections.wbs.data;
      if (!data) return [];
      return [
        metric("item_count", data.item_count),
        metric("root_count", data.root_count),
        metric("leaf_count", data.leaf_count),
        metric("max_level", data.max_level),
        metric("items_with_budget", data.items_with_budget),
        metric("items_with_planned_dates", data.items_with_planned_dates),
        metric("truncated", data.truncated),
        ...counts("by_item_type", data.by_item_type),
        ...data.roots.map((node) =>
          item({
            record_id: node.id,
            record_label: node.name,
            field: "code",
            value: node.code,
            record_evidence_tier: node.evidence_tier,
          }),
        ),
      ];
    }
    case "stakeholders": {
      const data = sections.stakeholders.data;
      if (!data) return [];
      return [
        metric("total", data.total),
        metric("key_player_count", data.key_player_count),
        metric("counts_are_partial", data.counts_are_partial),
        ...counts("by_quadrant", data.by_quadrant),
        ...data.items.map((person) =>
          item({
            record_id: person.id,
            record_label: person.name ?? "",
            field: "role",
            value: person.role ?? null,
            record_status: person.quadrant ?? "",
            record_evidence_tier: person.evidence_tier,
          }),
        ),
      ];
    }
    case "raci": {
      const data = sections.raci.data;
      if (!data) return [];
      return [
        metric("task_count", data.task_count),
        metric("assignment_count", data.assignment_count),
        metric("verified_assignment_count", data.verified_assignment_count),
        metric("tasks_without_accountable", data.tasks_without_accountable),
        ...data.tasks.map((task) =>
          item({
            record_id: task.task_code,
            record_label: task.task_name,
            field: "accountable",
            value: namesOrNone(task.accountable),
            record_status: `responsible: ${namesOrNone(task.responsible)}`,
          }),
        ),
      ];
    }
    case "evidence_quality": {
      const data = sections.evidence_quality.data;
      if (!data) return [];
      return data.rows.map((row) =>
        item({
          record_id: row.section_key,
          record_label: row.evidence_note ?? "",
          field: "evidence_tier",
          value: row.evidence_tier,
          record_status: row.status,
        }),
      );
    }
    default:
      return [];
  }
}

// ---------------------------------------------------------------------------
// Escaping
// ---------------------------------------------------------------------------

function escapeCell(raw: string): string {
  // Text that a spreadsheet would evaluate as a formula is prefixed so it stays text.
  const guarded = FORMULA_TRIGGER.test(raw) && !NUMERIC.test(raw) ? `'${raw}` : raw;
  return /[",\r\n]/.test(guarded) || guarded !== guarded.trim() ? `"${guarded.replace(/"/g, '""')}"` : guarded;
}

function sanitizeFilenamePart(value: string): string {
  const cleaned = value
    .replace(/[^A-Za-z0-9._-]+/g, "-")
    .replace(/\.{2,}/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^[.-]+|[.-]+$/g, "")
    .slice(0, MAX_FILENAME_PART)
    .replace(/[.-]+$/g, "");
  return cleaned || "project";
}
