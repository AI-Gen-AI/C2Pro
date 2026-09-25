/**
 * Explicit-only qualification for the real PJ-01 Contract A async seam.
 *
 * It deliberately stops after Processing A: canonical PJ-01 owns the rest
 * of the visible journey, while this focal test isolates worker/configuration
 * failures without creating parallel tenant-A activity during that acceptance.
 */
import { expect, test } from "@playwright/test";

import { contractAPdfPath, loadContractAManifest } from "../pj01/fixture-contract";
import { observeProcessingWithoutReload, ANALYSIS_BUDGET_MS } from "./support/pj01/processing";
import { Pj01RunRecorder } from "./support/pj01/run-recorder";
import { createProjectThroughUi, signInAsJourneyUser } from "./support/pj01/session";
import { uploadDocumentThroughUi } from "./support/pj01/upload";

test.describe("TS-E2E-PJ01-PROCESSING-A-001: Contract A processing focal", () => {
  test.skip(
    process.env.PJ01_FOCAL_PROCESSING_A !== "1",
    "focal Processing A qualification runs only when explicitly requested",
  );
  test.describe.configure({ timeout: ANALYSIS_BUDGET_MS + 120_000 });

  test("processes Contract A through the real worker and updates the Documents row", async ({ baseURL, page }, testInfo) => {
    const recorder = Pj01RunRecorder.fromEnv();
    try {
      const manifest = loadContractAManifest();
      const observation = await recorder.step("PJ01-S1", "Login", async () =>
        signInAsJourneyUser(page, baseURL ?? "http://localhost:3100"),
      );
      const projectId = await recorder.step("PJ01-S2", "Create project", async () =>
        createProjectThroughUi(page, observation, `PJ-01 Processing A ${recorder.runId}`),
      );
      const upload = await recorder.step("PJ01-S3", "Upload Contract A", async () =>
        uploadDocumentThroughUi(page, recorder, {
          projectId,
          filePath: contractAPdfPath(manifest),
          documentType: manifest.document_type,
        }),
      );
      const processing = await recorder.step("PJ01-S4", "Processing", async () => {
        const observed = await observeProcessingWithoutReload(page, recorder, {
          projectId,
          documentId: upload.documentId,
        });
        await recorder.screenshot(page, "s4-processing-settled");
        return observed;
      });

      expect(processing.evaluation.outcome).toBe("analyzed");
      expect(processing.evaluation.violations).toEqual([]);
      expect(processing.reloads).toBe(0);
      recorder.record("projectId", projectId);
      recorder.record("documentId", upload.documentId);
      recorder.record("uploadTaskId", upload.taskId);
    } finally {
      const runFile = recorder.write();
      testInfo.annotations.push({ type: "pj01-run", description: runFile });
    }
  });
});
