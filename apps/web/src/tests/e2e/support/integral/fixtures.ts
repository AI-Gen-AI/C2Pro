/**
 * Fixtures of the integral S1–S8 runner: the committed synthetic triplet (contract, budget, schedule, technical
 * specification) and the revision B of the contract. Pinned by SHA-256 so the run proves WHICH bytes the application
 * stored. No customer data, nothing generated at run time.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { sha256Hex } from "./ledger";

export const TRIPLET_DIR = path.join(process.cwd(), "src", "tests", "e2e", "test-data", "triplet");

export const FILES = {
  contractA: "triplet-contract.docx",
  contractB: "triplet-contract-b.docx",
  budget: "triplet-budget.xlsx",
  schedule: "triplet-schedule.xlsx",
  specification: "triplet-specification.docx",
  specificationRejected: "triplet-specification-rejected.docx",
} as const;

export const filePath = (name: string): string => path.join(TRIPLET_DIR, name);

interface TripletManifest {
  expected_rules: string[];
  expected_provisional: string[];
  sha256: Record<string, string>;
}

interface IntegralExtraManifest {
  contract_b: { sha256: string; added_sentence: string };
  specification_rejected: { sha256: string };
}

export const triplet = JSON.parse(readFileSync(path.join(TRIPLET_DIR, "triplet.manifest.json"), "utf8")) as TripletManifest;
export const extra = JSON.parse(
  readFileSync(path.join(TRIPLET_DIR, "integral.manifest.json"), "utf8"),
) as IntegralExtraManifest;
export const revisionB = extra.contract_b;

/** The pinned SHA-256 of a fixture, after proving the committed file still has it. */
export function pinnedSha(name: string): string {
  const pinned =
    name === FILES.contractB
      ? extra.contract_b.sha256
      : name === FILES.specificationRejected
        ? extra.specification_rejected.sha256
        : triplet.sha256[name];
  if (!pinned || !/^[0-9a-f]{64}$/.test(pinned)) throw new Error(`INTEGRAL_FIXTURE_NOT_PINNED: ${name}`);
  const actual = sha256Hex(readFileSync(filePath(name)));
  if (actual !== pinned) throw new Error(`INTEGRAL_FIXTURE_CHANGED: ${name} no longer has its pinned SHA-256`);
  return pinned;
}

/**
 * Row locators of the committed budget and schedule workbooks, as the product's own parser names them
 * (`ExcelFileParser`, verified against the pinned files by `test_integral_fixture_locators.py`).
 */
export const LOCATORS = {
  budget: "Presupuesto!2",
  schedule: "Plan!4",
} as const;

/** The technical specification clause the canonical link is proposed for (manifest: sections 4.1.2 and 4.2). */
export const TECHNICAL_SECTION = "4.1.2";
