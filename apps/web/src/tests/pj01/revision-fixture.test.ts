/**
 * TS-UT-PJ01-FIXTURE-004 — Contract B manifest honours Contract A's revision_contract.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { FIXTURE_DIR, loadContractAManifest } from "./fixture-contract";
import { contractBPdfPath, loadContractBManifest, validateRevisionFixture } from "./revision-fixture";

const source = (name: string): string => readFileSync(path.join(FIXTURE_DIR, name), "utf8");

describe("PJ-01 Contract B revision fixture", () => {
  it("is a valid revision of Contract A with exactly the declared fact changes", () => {
    const a = loadContractAManifest();
    const b = loadContractBManifest();
    expect(b.revision_of).toBe(a.fixture_id);
    expect(contractBPdfPath(b).endsWith("contract-b.pdf")).toBe(true);
    expect(validateRevisionFixture(a, b, source(a.files.source_text), source(b.files.source_text))).toEqual([]);
  });

  it("rejects a revision that changes a no-change control fact or an undeclared sentence", () => {
    const a = loadContractAManifest();
    const b = loadContractBManifest();
    const sourceB = source(b.files.source_text);
    const brokenControl = sourceB.replace("governed by Spanish law", "governed by French law");
    const errors = validateRevisionFixture(a, b, source(a.files.source_text), brokenControl);
    expect(errors.some((error) => error.includes("governing_law"))).toBe(true);
    expect(errors.some((error) => error.includes("undeclared"))).toBe(true);
  });

  it("rejects a cause outside the canonical change vocabulary and a non-mutable changed fact", () => {
    const a = loadContractAManifest();
    const b = loadContractBManifest();
    const bad = {
      ...b,
      expected_revision_change: {
        ...b.expected_revision_change,
        change_cause: "PRICE_UPDATED",
        changed_facts: [...b.expected_revision_change.changed_facts, { key: "governing_law", clause_ordinal: 6, before_text: "x", after_text: "y" }],
      },
    };
    const errors = validateRevisionFixture(a, bad, source(a.files.source_text), source(b.files.source_text));
    expect(errors.some((error) => error.includes("PRICE_UPDATED"))).toBe(true);
    expect(errors.some((error) => error.includes("governing_law is not a mutable fact"))).toBe(true);
  });
});
