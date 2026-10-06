import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { contractAPdfPath, loadContractAManifest } from "../../pj01/fixture-contract";
import { contractBPdfPath, loadContractBManifest } from "../../pj01/revision-fixture";
import { observeProcessingWithoutReload } from "../support/pj01/processing";
import { uploadNewVersionThroughUi } from "../support/pj01/revision";
import { Pj01RunRecorder } from "../support/pj01/run-recorder";
import { assertWhatChangedThroughNavigation } from "../support/pj01/what-changed";
import {
  signInSyntheticProductionUser,
  signOutThroughUi,
} from "./support/prod-auth.synthetic";
import { requireProductionOrigin } from "./support/prod-preflight";

const RUN_OUTPUT = path.join(
  process.cwd(),
  "playwright",
  ".prod-p0c",
  "run.json",
);
const JOURNEY_TIMEOUT_MS = 12 * 60_000;

function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`PROD_P0C_MISSING_ENV:${name}`);
  return value;
}

function baseUrl(): string {
  return requireProductionOrigin(
    process.env.PROD_ACCEPTANCE_BASE_URL ?? "https://c2pro.io",
  );
}

function writeRunEvidence(value: Record<string, unknown>): void {
  const directory = path.dirname(RUN_OUTPUT);
  if (!existsSync(directory)) mkdirSync(directory, { recursive: true });
  writeFileSync(RUN_OUTPUT, JSON.stringify(value, null, 2), "utf8");
}

test.describe("Issue #686 P0c production qualification", () => {
  test.describe.configure({ mode: "serial", timeout: JOURNEY_TIMEOUT_MS });

  test("accepted P0b document evolves through revision B and What Changed", async ({
    page,
  }) => {
    const runId = requiredEnv("PROD_ACCEPTANCE_RUN_ID");
    const projectId = requiredEnv("PROD_P0C_PROJECT_ID");
    const documentId = requiredEnv("PROD_P0C_DOCUMENT_ID");
    const expectedSourceRevisionId = requiredEnv("PROD_P0C_SOURCE_REVISION_ID");

    const recorder = new Pj01RunRecorder({
      runId,
      rootDir: path.join(process.cwd(), "playwright", ".prod-p0c", "pj01"),
      mode: "strict",
    });
    const baseManifest = loadContractAManifest();
    const revisionManifest = loadContractBManifest();

    try {
      await recorder.step("P0C-PROD-S1", "Real production sign-in", async () => {
        await signInSyntheticProductionUser(page);
      });

      await recorder.step("P0C-PROD-S2", "Bind accepted P0b document", async () => {
        await page.goto(`${baseUrl()}/projects/${projectId}/documents`);
        await expect(page.getByTestId("documents-page")).toBeVisible({
          timeout: 30_000,
        });
        await expect(page.getByTestId(`document-row-${documentId}`)).toBeVisible({
          timeout: 30_000,
        });
      });

      const revision = await recorder.step(
        "P0C-PROD-S3",
        "Upload Contract B as revision of the same document",
        async () =>
          uploadNewVersionThroughUi(page, recorder, {
            projectId,
            documentId,
            filePath: contractBPdfPath(revisionManifest),
          }),
      );

      expect(revision.documentId).toBe(documentId);
      expect(revision.documentsListed).toBe(1);

      const processing = await recorder.step(
        "P0C-PROD-S4",
        "Observe revision B processing without reload",
        async () =>
          observeProcessingWithoutReload(page, recorder, {
            projectId,
            documentId,
          }),
      );
      expect(processing.evaluation.outcome).toBe("analyzed");
      expect(processing.evaluation.violations).toEqual([]);

      const whatChanged = await recorder.step(
        "P0C-PROD-S5",
        "Prove What Changed timeline/detail",
        async () =>
          assertWhatChangedThroughNavigation(page, recorder, {
            projectId,
            documentId,
            contractAPdf: contractAPdfPath(baseManifest),
            contractBPdf: contractBPdfPath(revisionManifest),
            base: baseManifest,
            revision: revisionManifest,
          }),
      );

      expect(whatChanged.sourceRevisionId).toBe(expectedSourceRevisionId);
      expect(whatChanged.targetRevisionId).not.toBe(expectedSourceRevisionId);
      expect(recorder.blockingFindings()).toEqual([]);

      await recorder.step(
        "P0C-PROD-S6",
        "Prove timeline durability after real relogin",
        async () => {
          await signOutThroughUi(page);
          await signInSyntheticProductionUser(page);
          await page.goto(`${baseUrl()}/projects/${projectId}/changes`);
          await expect(
            page.getByTestId(`change-item-${whatChanged.changeEventId}`),
          ).toBeVisible({ timeout: 60_000 });
        },
      );

      writeRunEvidence({
        schema: "c2pro-p0c-prod-run/v1",
        run_id: runId,
        project_id: projectId,
        document_id: documentId,
        source_revision_id: whatChanged.sourceRevisionId,
        target_revision_id: whatChanged.targetRevisionId,
        change_event_id: whatChanged.changeEventId,
        occurred_at: whatChanged.occurredAt,
        revision_version: revision.version,
        documents_listed: revision.documentsListed,
        processing_outcome: processing.evaluation.outcome,
        relogin_verified: true,
        blocking_findings: recorder.blockingFindings(),
      });
    } finally {
      recorder.write();
    }
  });
});
