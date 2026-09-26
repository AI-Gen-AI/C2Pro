/**
 * PJ-01 Contract B: a real revision of Contract A under its `revision_contract`.
 *
 * The backend conformance test (`apps/api/tests/unit/pj01/test_pj01_contract_b_revision_conformance.py`)
 * proves the real pipeline derives `expected_revision_change` from the two committed PDFs; this module
 * lets the browser harness read the same expectations and guards the fixture contract itself.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import {
  CHANGE_CAUSE_VOCABULARY,
  FIXTURE_DIR,
  type Pj01ContractFixtureManifest,
} from "./fixture-contract";

export const CONTRACT_B_MANIFEST = "contract-b.manifest.json";

export interface RevisionChangedFact {
  key: string;
  clause_ordinal: number;
  before_text: string;
  after_text: string;
  after_value?: unknown;
}

export interface Pj01RevisionFixtureManifest {
  schema: Pj01ContractFixtureManifest["schema"];
  fixture_id: string;
  revision_of: string;
  derived_from: string;
  document_type: "contract";
  files: { pdf: string; source_text: string };
  generator: string;
  expected_health: Pj01ContractFixtureManifest["expected_health"];
  expected_revision_change: {
    change_cause: string;
    modified_clause_ordinals: number[];
    unchanged_clause_ordinals: number[];
    changed_facts: RevisionChangedFact[];
    no_change_control_fact_keys: string[];
    identical_reupload?: { change_cause: null; browser_label: string; note: string };
  };
}

export function loadContractBManifest(): Pj01RevisionFixtureManifest {
  return JSON.parse(readFileSync(path.join(FIXTURE_DIR, CONTRACT_B_MANIFEST), "utf8")) as Pj01RevisionFixtureManifest;
}

export function contractBPdfPath(manifest: Pj01RevisionFixtureManifest = loadContractBManifest()): string {
  return path.join(FIXTURE_DIR, manifest.files.pdf);
}

const normalise = (text: string): string => text.replace(/\s+/g, " ").trim();

export function validateRevisionFixture(
  base: Pj01ContractFixtureManifest,
  revision: Pj01RevisionFixtureManifest,
  baseSource: string,
  revisionSource: string,
): string[] {
  const errors: string[] = [];
  const change = revision.expected_revision_change;
  const sourceA = normalise(baseSource);
  const sourceB = normalise(revisionSource);

  if (revision.revision_of !== base.fixture_id) {
    errors.push(`revision_of must be ${base.fixture_id}`);
  }
  if (!(CHANGE_CAUSE_VOCABULARY as readonly string[]).includes(change.change_cause)) {
    errors.push(`unknown change cause ${change.change_cause}`);
  }

  const mutable = new Set(base.revision_contract.mutable_fact_keys);
  for (const fact of change.changed_facts) {
    if (!mutable.has(fact.key)) errors.push(`${fact.key} is not a mutable fact`);
    if (!sourceA.includes(normalise(fact.before_text))) errors.push(`${fact.key}: before_text not in the base contract`);
    if (!sourceB.includes(normalise(fact.after_text))) errors.push(`${fact.key}: after_text not in the revision`);
    if (sourceB.includes(normalise(fact.before_text))) errors.push(`${fact.key}: before_text still present in the revision`);
  }

  const baseFacts = new Map(base.facts.map((fact) => [fact.key, fact.text]));
  for (const key of change.no_change_control_fact_keys) {
    const text = baseFacts.get(key);
    if (!text) errors.push(`${key}: unknown control fact`);
    else if (!sourceB.includes(normalise(text))) errors.push(`${key}: no-change control fact changed`);
  }

  const linesA = baseSource.split(/\r?\n/);
  const linesB = revisionSource.split(/\r?\n/);
  if (linesA.length !== linesB.length) errors.push("the revision must keep every line (headings and sentences)");
  linesA.forEach((lineA, index) => {
    const lineB = linesB[index] ?? "";
    if (lineA === lineB) return;
    const declared = change.changed_facts.some(
      (fact) => normalise(lineA).includes(normalise(fact.before_text)) && normalise(lineB).includes(normalise(fact.after_text)),
    );
    if (!declared) errors.push(`line ${index + 1}: undeclared change`);
  });

  return errors;
}
