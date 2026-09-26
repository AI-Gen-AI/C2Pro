/**
 * PJ-01 step I judge: the Current State report after revision B.
 *
 * Pure: the harness captures the application's report response, the downloaded JSON and CSV, and
 * the Health rows the user sees, and asks this module whether they state six canonical Health
 * categories honestly, for one logical document, reflecting the latest analysed revision.
 */
import { CANONICAL_CATEGORIES } from "./health-evaluator";

export interface SectionLike {
  status: string;
  status_reason?: string | null;
  source_as_of?: string | null;
  data?: unknown;
}

export interface HealthCategoryLike {
  category: string;
  state: string;
  evidence_count: number;
  missing_data?: string[];
  gap?: string | null;
}

export interface HealthSectionLike extends SectionLike {
  data?: { computed_at: string; evidence_granularity: string; categories: HealthCategoryLike[] } | null;
}

export interface DocumentsSectionLike extends SectionLike {
  data?: { total: number; by_type: Record<string, number>; by_lifecycle_status?: Record<string, number> } | null;
}

export interface CurrentStateReportLike {
  report_schema_version?: string;
  generated_at?: string;
  sections: {
    documents?: DocumentsSectionLike;
    health?: HealthSectionLike;
    [section: string]: SectionLike | undefined;
  };
}

export interface ScreenHealthRow {
  category: string;
  state: string;
  evidenceCount: string;
}

export interface CurrentStateViolation {
  code: string;
  detail: string;
}

const LEGACY_DIMENSIONS = new Set(["contract", "risk", "documentation", "governance", "schedule", "cost", "deliverables"]);

export function evaluateCurrentStateReport(
  report: CurrentStateReportLike,
  expectation: { expectedDocumentTotal: number; latestRevisionAnalyzedAt?: string },
): CurrentStateViolation[] {
  const violations: CurrentStateViolation[] = [];
  if (!report.report_schema_version?.startsWith("current-state-report/v2")) {
    violations.push({ code: "SCHEMA_VERSION", detail: `report_schema_version ${report.report_schema_version}` });
  }

  const health = report.sections.health;
  if (!health || health.status !== "available" || !health.data) {
    violations.push({ code: "HEALTH_NOT_AVAILABLE", detail: `health status ${health?.status}: ${health?.status_reason ?? "no reason"}` });
  } else {
    const categories = health.data.categories ?? [];
    if (categories.map((item) => item.category).join() !== CANONICAL_CATEGORIES.join()) {
      violations.push({ code: "HEALTH_CATEGORY_SET", detail: categories.map((item) => item.category).join(", ") });
    }
    const data = health.data as Record<string, unknown>;
    const serialised = JSON.stringify(data);
    if ("dimensions" in data || categories.some((item) => LEGACY_DIMENSIONS.has(String(item.category).toLowerCase()))) {
      violations.push({ code: "LEGACY_HEALTH_TAXONOMY", detail: "legacy ADR-018 v0 dimensions surfaced as Health" });
    }
    if (/"[a-z_]*(score|composite|band)[a-z_]*"\s*:/i.test(serialised)) {
      violations.push({ code: "HEALTH_SCORE_FABRICATED", detail: "a numeric/composite Health score is present" });
    }
    for (const item of categories) {
      const dishonest =
        (item.state === "insufficient_evidence" && item.evidence_count > 0) || (item.state === "present" && item.evidence_count === 0);
      if (dishonest) {
        violations.push({ code: "HEALTH_DISHONEST_UNKNOWN", detail: `${item.category}: ${item.state} with ${item.evidence_count} evidence` });
      }
    }
    if (
      expectation.latestRevisionAnalyzedAt &&
      health.source_as_of &&
      new Date(health.source_as_of).getTime() < new Date(expectation.latestRevisionAnalyzedAt).getTime()
    ) {
      violations.push({
        code: "HEALTH_STALE_FOR_REVISION",
        detail: `health as of ${health.source_as_of} predates the latest revision analysis ${expectation.latestRevisionAnalyzedAt}`,
      });
    }
  }

  for (const [name, section] of Object.entries(report.sections)) {
    if (section && section.status !== "available" && !section.status_reason?.trim()) {
      violations.push({ code: "SECTION_WITHOUT_REASON", detail: `${name} is ${section.status} without a reason` });
    }
  }

  const documents = report.sections.documents?.data;
  if (!documents || documents.total !== expectation.expectedDocumentTotal || (documents.by_type.contract ?? 0) !== expectation.expectedDocumentTotal) {
    violations.push({
      code: "DOCUMENT_DUPLICATED",
      detail: `documents total ${documents?.total}, contracts ${documents?.by_type.contract} (expected ${expectation.expectedDocumentTotal})`,
    });
  }
  return violations;
}

type CsvRow = Record<string, string>;

export function parseCsv(text: string): CsvRow[] {
  const rows: string[][] = [];
  let field = "";
  let row: string[] = [];
  let quoted = false;
  const input = text.replace(/^\uFEFF/, "");
  for (let index = 0; index < input.length; index += 1) {
    const char = input[index];
    if (quoted) {
      if (char === '"' && input[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }
  if (field !== "" || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  const [header = [], ...body] = rows;
  return body.map((cells) => Object.fromEntries(header.map((name, index) => [name, cells[index] ?? ""])));
}

const factsOf = (categories: HealthCategoryLike[]): string =>
  categories.map((item) => `${item.category}:${item.state}:${item.evidence_count}`).join("|");

export function evaluateExportParity(
  report: CurrentStateReportLike,
  jsonText: string,
  csvText: string,
  screen: ScreenHealthRow[],
): CurrentStateViolation[] {
  const violations: CurrentStateViolation[] = [];
  const expected = factsOf(report.sections.health?.data?.categories ?? []);

  let jsonFacts: string;
  try {
    const parsed = JSON.parse(jsonText) as CurrentStateReportLike;
    jsonFacts = factsOf(parsed.sections?.health?.data?.categories ?? []);
  } catch {
    jsonFacts = "unparseable";
  }
  if (jsonFacts !== expected) violations.push({ code: "JSON_PARITY", detail: `json ${jsonFacts} != report ${expected}` });

  const byCategory = new Map<string, { state?: string; evidence_count?: string }>();
  for (const row of parseCsv(csvText)) {
    if (row.section !== "health" || row.record_type !== "item") continue;
    const facts = byCategory.get(row.record_id) ?? {};
    if (row.field === "state") facts.state = row.value;
    if (row.field === "evidence_count") facts.evidence_count = row.value;
    byCategory.set(row.record_id, facts);
  }
  const csvFacts = [...byCategory.entries()].map(([category, facts]) => `${category}:${facts.state}:${facts.evidence_count}`).join("|");
  if (csvFacts !== expected) violations.push({ code: "CSV_PARITY", detail: `csv ${csvFacts} != report ${expected}` });

  const screenFacts = screen.map((row) => `${row.category}:${row.state}:${row.evidenceCount}`).join("|");
  if (screenFacts !== expected) violations.push({ code: "SCREEN_PARITY", detail: `screen ${screenFacts} != report ${expected}` });
  return violations;
}
