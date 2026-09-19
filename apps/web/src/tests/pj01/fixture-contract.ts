/**
 * PJ-01 deterministic contract fixture contract.
 *
 * One vocabulary shared by every PJ-01 lane:
 * - categories: the six canonical single-document Health categories (`CANONICAL_CATEGORIES`);
 * - change causes: the P0c temporal vocabulary (`BUSINESS_STATE_CHANGED`, `NEWLY_DISCOVERED`)
 *   plus the browser-visible `NO_CHANGE`;
 * - clauses: ordinals of the segments ingestion persists (`_split_contract_into_clauses`).
 *
 * The backend conformance test (`apps/api/tests/unit/pj01/test_pj01_contract_fixture_conformance.py`)
 * proves the real pipeline produces `expected_health` for the committed PDF.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { CANONICAL_CATEGORIES, type CanonicalCategory, type HealthExpectations } from "./health-evaluator";

export const FIXTURE_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../e2e/test-data/pj01");
export const CONTRACT_A_MANIFEST = "contract-a.manifest.json";
export const FIXTURE_SCHEMA = "c2pro-pj01-contract-fixture/v1";
export const CHANGE_CAUSE_VOCABULARY = ["BUSINESS_STATE_CHANGED", "NEWLY_DISCOVERED", "NO_CHANGE"] as const;

export interface FixtureClause {
  ordinal: number;
  heading: string;
  categories: CanonicalCategory[];
  /** A sentence unique to this clause, for evidence highlighting/traceability assertions. */
  evidence_anchor?: string;
}

export interface FixtureFact {
  key: string;
  category: CanonicalCategory;
  clause_ordinal: number;
  /** Exact contract wording (whitespace-normalised) that carries the fact. */
  text: string;
  value: unknown;
}

export interface Pj01ContractFixtureManifest {
  schema: typeof FIXTURE_SCHEMA;
  fixture_id: string;
  derived_from: string;
  document_type: "contract";
  files: { pdf: string; source_text: string };
  generator: string;
  clauses: FixtureClause[];
  expected_health: {
    granularity: "clause" | "document";
    categories: Record<
      CanonicalCategory,
      { state: "present" | "insufficient_evidence"; evidence_clause_ordinals: number[] }
    >;
  };
  facts: FixtureFact[];
  revision_contract: {
    owner: string;
    change_cause_vocabulary: string[];
    mutable_fact_keys: string[];
    no_change_control_fact_keys: string[];
    rules: string[];
  };
  current_state_expectations: Record<string, unknown>;
}

export function loadContractAManifest(): Pj01ContractFixtureManifest {
  return JSON.parse(readFileSync(path.join(FIXTURE_DIR, CONTRACT_A_MANIFEST), "utf8")) as Pj01ContractFixtureManifest;
}

export function contractAPdfPath(manifest: Pj01ContractFixtureManifest = loadContractAManifest()): string {
  return path.join(FIXTURE_DIR, manifest.files.pdf);
}

const normalise = (text: string): string => text.replace(/\s+/g, " ").trim();

export function validateFixtureManifest(manifest: Pj01ContractFixtureManifest, sourceText: string): string[] {
  const errors: string[] = [];
  const source = normalise(sourceText);
  const canonical = new Set<string>(CANONICAL_CATEGORIES);

  if (manifest.schema !== FIXTURE_SCHEMA) errors.push(`schema must be ${FIXTURE_SCHEMA}`);

  const ordinals = manifest.clauses.map((clause) => clause.ordinal);
  if (ordinals.some((ordinal, index) => ordinal !== index)) {
    errors.push("clause ordinals must be 0..n-1 in order");
  }

  // Clause sections of the source, delimited by the headings in order.
  const sections = new Map<number, string>();
  let cursor = 0;
  const starts: { ordinal: number; start: number }[] = [];
  for (const clause of manifest.clauses) {
    const start = source.indexOf(normalise(clause.heading), cursor);
    if (start < 0) {
      errors.push(`clause ${clause.ordinal} heading not found in order: ${clause.heading}`);
      continue;
    }
    starts.push({ ordinal: clause.ordinal, start });
    cursor = start + 1;
  }
  starts.forEach((entry, index) => {
    sections.set(entry.ordinal, source.slice(entry.start, starts[index + 1]?.start ?? source.length));
  });

  for (const clause of manifest.clauses) {
    for (const category of clause.categories) {
      if (!canonical.has(category)) errors.push(`clause ${clause.ordinal}: unknown category ${category}`);
    }
    if (clause.evidence_anchor) {
      const anchor = normalise(clause.evidence_anchor);
      const section = sections.get(clause.ordinal) ?? "";
      if (!section.includes(anchor)) errors.push(`clause ${clause.ordinal} evidence_anchor not in its clause`);
      if (source.indexOf(anchor) !== source.lastIndexOf(anchor)) {
        errors.push(`clause ${clause.ordinal} evidence_anchor is not unique in the contract`);
      }
    }
  }

  const expectedCategories = Object.keys(manifest.expected_health.categories);
  if (expectedCategories.sort().join() !== [...CANONICAL_CATEGORIES].sort().join()) {
    errors.push(`expected_health must list exactly ${CANONICAL_CATEGORIES.join(", ")}`);
  }
  for (const category of CANONICAL_CATEGORIES) {
    const expectation = manifest.expected_health.categories[category];
    if (!expectation) continue;
    const listed = manifest.clauses.filter((clause) => clause.categories.includes(category)).map((c) => c.ordinal);
    for (const ordinal of expectation.evidence_clause_ordinals) {
      const clause = manifest.clauses.find((candidate) => candidate.ordinal === ordinal);
      if (!clause) errors.push(`${category}: evidence clause ${ordinal} does not exist`);
      else if (!clause.categories.includes(category)) {
        errors.push(`${category}: clause ${ordinal} does not evidence ${category}`);
      }
    }
    if ([...listed].sort().join() !== [...expectation.evidence_clause_ordinals].sort().join()) {
      errors.push(`${category}: clause categories and expected evidence ordinals disagree`);
    }
    if (expectation.state === "present" && expectation.evidence_clause_ordinals.length === 0) {
      errors.push(`${category}: PRESENT requires evidence clauses`);
    }
    if (expectation.state === "insufficient_evidence" && expectation.evidence_clause_ordinals.length > 0) {
      errors.push(`${category}: INSUFFICIENT_EVIDENCE cannot list evidence clauses`);
    }
  }

  const factKeys = new Set<string>();
  for (const fact of manifest.facts) {
    if (factKeys.has(fact.key)) errors.push(`${fact.key}: duplicate fact key`);
    factKeys.add(fact.key);
    if (!canonical.has(fact.category)) errors.push(`${fact.key}: unknown category ${fact.category}`);
    const clause = manifest.clauses.find((candidate) => candidate.ordinal === fact.clause_ordinal);
    if (!clause) {
      errors.push(`${fact.key}: clause ${fact.clause_ordinal} does not exist`);
      continue;
    }
    if (!(sections.get(fact.clause_ordinal) ?? "").includes(normalise(fact.text))) {
      errors.push(`${fact.key}: text not in clause ${fact.clause_ordinal}`);
    }
    if (!clause.categories.includes(fact.category)) {
      errors.push(`${fact.key}: clause ${fact.clause_ordinal} does not evidence ${fact.category}`);
    }
  }

  const allowedCauses = new Set<string>(CHANGE_CAUSE_VOCABULARY);
  for (const cause of manifest.revision_contract.change_cause_vocabulary) {
    if (!allowedCauses.has(cause)) errors.push(`unknown change cause in revision_contract: ${cause}`);
  }
  for (const key of [
    ...manifest.revision_contract.mutable_fact_keys,
    ...manifest.revision_contract.no_change_control_fact_keys,
  ]) {
    if (!factKeys.has(key)) errors.push(`revision_contract references unknown fact ${key}`);
  }

  return errors;
}

export function healthExpectationsFromManifest(manifest: Pj01ContractFixtureManifest): HealthExpectations {
  return {
    granularity: manifest.expected_health.granularity,
    categories: Object.fromEntries(
      CANONICAL_CATEGORIES.map((category) => {
        const expectation = manifest.expected_health.categories[category];
        return [category, { state: expectation.state, evidenceCount: expectation.evidence_clause_ordinals.length }];
      }),
    ) as HealthExpectations["categories"],
  };
}
