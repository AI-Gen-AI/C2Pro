/**
 * PJ-01 shared browser harness — first half of the journey.
 *
 * Login → Create Project → Upload Contract A → Processing → Health → six dimensions →
 * toward Evidence, on the deterministic PJ-01 Contract A fixture.
 *
 * Consumers (the What Changed spec, the Health → Evidence spec, the integrated PJ-01
 * acceptance run) call `runPj01FirstHalf` and continue from the returned project and
 * document, instead of re-implementing sign-in, upload and processing.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import type { Page } from "@playwright/test";

import {
  contractAPdfPath,
  healthExpectationsFromManifest,
  loadContractAManifest,
  type Pj01ContractFixtureManifest,
} from "../../../pj01/fixture-contract";
import type { HealthVectorPayload } from "../../../pj01/health-evaluator";
import { navigateTowardEvidence } from "./evidence";
import { assertSixHealthDimensions, openHealthThroughNavigation } from "./health";
import { observeProcessingWithoutReload, type ProcessingObservation } from "./processing";
import type { Pj01RunRecorder } from "./run-recorder";
import { createProjectThroughUi, signInAsJourneyUser } from "./session";
import { uploadDocumentThroughUi } from "./upload";

export const PJ01_PROJECT_ID_FILE = path.join(process.cwd(), "playwright", ".pj01", "project-id.txt");

export interface Pj01FirstHalfResult {
  projectId: string;
  documentId: string;
  manifest: Pj01ContractFixtureManifest;
  processing: ProcessingObservation;
  health: HealthVectorPayload;
}

export async function runPj01FirstHalf(
  page: Page,
  options: { baseURL: string; recorder: Pj01RunRecorder; projectName?: string },
): Promise<Pj01FirstHalfResult> {
  const { recorder } = options;
  const manifest = loadContractAManifest();
  recorder.record("fixture", manifest.fixture_id);

  const observation = await recorder.step("PJ01-S1", "Login", async () => {
    const auth = await signInAsJourneyUser(page, options.baseURL);
    await recorder.screenshot(page, "s1-projects");
    return auth;
  });

  const projectId = await recorder.step("PJ01-S2", "Create project", async () => {
    const id = await createProjectThroughUi(page, observation, options.projectName ?? `PJ-01 ${recorder.runId}`);
    mkdirSync(path.dirname(PJ01_PROJECT_ID_FILE), { recursive: true });
    writeFileSync(PJ01_PROJECT_ID_FILE, id, "utf8");
    recorder.record("projectId", id);
    await recorder.screenshot(page, "s2-documents-empty");
    return id;
  });

  const { documentId } = await recorder.step("PJ01-S3", "Upload Contract A", async () => {
    const result = await uploadDocumentThroughUi(page, recorder, {
      projectId,
      filePath: contractAPdfPath(manifest),
      documentType: manifest.document_type,
    });
    await recorder.screenshot(page, "s3-upload-accepted");
    return result;
  });

  const processing = await recorder.step("PJ01-S4", "Processing", async () => {
    const observed = await observeProcessingWithoutReload(page, recorder, { projectId, documentId });
    await recorder.screenshot(page, "s4-processing-settled");
    if (observed.evaluation.outcome !== "analyzed" || observed.evaluation.violations.length > 0) {
      const codes = observed.evaluation.violations.map((violation) => violation.code).join(", ");
      throw new Error(`PJ01_PROCESSING: outcome=${observed.evaluation.outcome} violations=[${codes}]`);
    }
    return observed;
  });

  const health = await recorder.step("PJ01-S5", "Reach Health through navigation", async () => {
    const vector = await openHealthThroughNavigation(page, recorder, { projectId });
    await recorder.screenshot(page, "s5-health");
    return vector;
  });

  await recorder.step("PJ01-S6", "Assert six Health dimensions", async () => {
    await assertSixHealthDimensions(page, recorder, health, healthExpectationsFromManifest(manifest));
  });

  await recorder.step("PJ01-S7", "Navigate toward Evidence", async () => {
    await navigateTowardEvidence(page, recorder, { projectId, documentId });
    await recorder.screenshot(page, "s7-evidence");
  });

  return { projectId, documentId, manifest, processing, health };
}
