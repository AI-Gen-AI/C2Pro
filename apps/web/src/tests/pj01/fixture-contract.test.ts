/**
 * TS-UT-PJ01-FIXTURE-001 — the PJ-01 Contract A fixture contract is internally consistent.
 *
 * The backend half (`apps/api/tests/unit/pj01/test_pj01_contract_fixture_conformance.py`)
 * proves the real ingestion + Health pipeline produces exactly these expectations.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { CANONICAL_CATEGORIES } from "./health-evaluator";
import {
  FIXTURE_DIR,
  healthExpectationsFromManifest,
  loadContractAManifest,
  validateFixtureManifest,
  type Pj01ContractFixtureManifest,
} from "./fixture-contract";

const manifest = loadContractAManifest();
const sourceText = readFileSync(path.join(FIXTURE_DIR, manifest.files.source_text), "utf8");

function clone(): Pj01ContractFixtureManifest {
  return JSON.parse(JSON.stringify(manifest)) as Pj01ContractFixtureManifest;
}

describe("PJ-01 Contract A fixture manifest", () => {
  it("is valid against its source text", () => {
    expect(validateFixtureManifest(manifest, sourceText)).toEqual([]);
  });

  it("expects all six canonical categories PRESENT, each evidenced by exactly one clause", () => {
    expect(Object.keys(manifest.expected_health.categories).sort()).toEqual([...CANONICAL_CATEGORIES].sort());
    for (const category of CANONICAL_CATEGORIES) {
      const expectation = manifest.expected_health.categories[category];
      expect(expectation.state).toBe("present");
      expect(expectation.evidence_clause_ordinals).toHaveLength(1);
    }
    expect(manifest.expected_health.granularity).toBe("clause");
  });

  it("carries facts for every category so later revisions and Current State can assert on them", () => {
    for (const category of CANONICAL_CATEGORIES) {
      expect(manifest.facts.some((fact) => fact.category === category), category).toBe(true);
    }
  });

  it("reserves the What Changed vocabulary for the revision fixture owner without inventing a new one", () => {
    expect(manifest.revision_contract.change_cause_vocabulary).toEqual([
      "BUSINESS_STATE_CHANGED",
      "NEWLY_DISCOVERED",
      "NO_CHANGE",
    ]);
  });

  it("exposes health expectations in the evaluator's shape", () => {
    const expectations = healthExpectationsFromManifest(manifest);
    expect(expectations.granularity).toBe("clause");
    expect(expectations.categories?.BUDGET).toEqual({ state: "present", evidenceCount: 1 });
  });

  it("rejects an expectation pointing at a clause that does not evidence the category", () => {
    const broken = clone();
    broken.expected_health.categories.SCOPE.evidence_clause_ordinals = [2];
    expect(validateFixtureManifest(broken, sourceText)).toContainEqual(expect.stringContaining("SCOPE"));
  });

  it("rejects a fact whose text is not inside its clause", () => {
    const broken = clone();
    broken.facts[0] = { ...broken.facts[0], clause_ordinal: 1 };
    expect(validateFixtureManifest(broken, sourceText)).toContainEqual(expect.stringContaining(broken.facts[0].key));
  });

  it("rejects a clause heading missing from the source text", () => {
    const broken = clone();
    broken.clauses[1] = { ...broken.clauses[1], heading: "1. - NOT IN THE CONTRACT" };
    expect(validateFixtureManifest(broken, sourceText)).toContainEqual(expect.stringContaining("heading"));
  });

  it("rejects an unknown change-cause vocabulary entry", () => {
    const broken = clone();
    broken.revision_contract.change_cause_vocabulary = ["BUSINESS_STATE_CHANGED", "SOMETHING_ELSE"];
    expect(validateFixtureManifest(broken, sourceText)).toContainEqual(expect.stringContaining("SOMETHING_ELSE"));
  });
});
