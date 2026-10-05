import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import {
  contractAPdfPath,
  loadContractAManifest,
} from "../../pj01/fixture-contract";
import {
  contractBPdfPath,
  loadContractBManifest,
} from "../../pj01/revision-fixture";
import { observeProcessingWithoutReload } from "../support/pj01/processing";
import { uploadNewVersionThroughUi } from "../support/pj01/revision";
import { Pj01RunRecorder } from "../support/pj01/run-recorder";
import { createProjectThroughAuthenticatedUi } from "../support/pj01/session";
import { uploadDocumentThroughUi } from "../support/pj01/upload";
import { assertWhatChangedThroughNavigation } from "../support/pj01/what-changed";
import {
  signInSyntheticProductionUser,
  signOutThroughUi,
} from "./support/prod-auth.synthetic";

const OUTPUT = path.join(process.cwd(), "playwright", ".prod-p0c", "run.json");

function runId(): string {
  const value = process.env.PROD_ACCEPTANCE_RUN_ID?.trim();
  if (!value) throw new Error("P0C_PROD_MISSING_ENV:PROD_ACCEPTANCE_RUN_ID");
  return value;
}

function baseUrl(): string {
  return process.env.PROD_ACCEPTANCE_BASE_URL ?? "https://c2pro.io";
}

test.describe("P0c production qualification — What Changed", () => {
  test("@production-qualification two revisions remain durable after relogin", async ({
    page,
  }) => {
    test.setTimeout(12 * 60_000);

    const id = runId();
    const projectName = `ACCEPT-686-${id}`;
    const recorder = new Pj01RunRecorder({
      runId: id,
      rootDir: path.join(process.cwd(), "playwright", ".prod-p0c", "artifacts"),
      mode: "strict",
    });
    const contractA = loadContractAManifest();
    const contractB = loadContractBManifest();

    await recorder.step("P0C-PROD-01-AUTH", "Real production sign-in", async () => {
      await signInSyntheticProductionUser(page);
    });

    const projectId = await recorder.step(
      "P0C-PROD-01-PROJECT",
      "Create bounded synthetic project",
      async () => {
        const value = await createProjectThroughAuthenticatedUi(page, projectName);
        recorder.record("projectId", value);
        return value;
      },
    );

    const documentId = await recorder.step(
      "P0C-PROD-01-REV-A",
      "Upload Contract A through the real UI",
      async () => {
        const uploaded = await uploadDocumentThroughUi(page, recorder, {
          projectId,
          filePath: contractAPdfPath(contractA),
          documentType: contractA.document_type,
        });
        if (!uploaded.taskId) {
          throw new Error("P0C_REV_A_NOT_ENQUEUED");
        }
        return uploaded.documentId;
      },
    );

    await recorder.step(
      "P0C-PROD-01-REV-A-SETTLE",
      "Wait for revision A to settle",
      async () => {
        const observed = await observeProcessingWithoutReload(page, recorder, {
          projectId,
          documentId,
        });
        if (observed.evaluation.outcome !== "analyzed" || observed.evaluation.violations.length) {
          throw new Error(
            `P0C_REV_A_PROCESSING:${observed.evaluation.outcome}:${observed.evaluation.violations
              .map((item) => item.code)
              .join(",")}`,
          );
        }
      },
    );

    const revision = await recorder.step(
      "P0C-PROD-01-REV-B",
      "Upload Contract B as a new version of the same document",
      async () =>
        uploadNewVersionThroughUi(page, recorder, {
          projectId,
          documentId,
          filePath: contractBPdfPath(contractB),
        }),
    );
    expect(revision.documentId).toBe(documentId);
    expect(revision.documentsListed).toBe(1);

    await recorder.step(
      "P0C-PROD-01-REV-B-SETTLE",
      "Wait for revision B to settle",
      async () => {
        const observed = await observeProcessingWithoutReload(page, recorder, {
          projectId,
          documentId,
        });
        if (observed.evaluation.outcome !== "analyzed" || observed.evaluation.violations.length) {
          throw new Error(
            `P0C_REV_B_PROCESSING:${observed.evaluation.outcome}:${observed.evaluation.violations
              .map((item) => item.code)
              .join(",")}`,
          );
        }
      },
    );

    const firstObservation = await recorder.step(
      "P0C-PROD-01-WHAT-CHANGED",
      "Observe revision.changed and semantic detail",
      async () =>
        assertWhatChangedThroughNavigation(page, recorder, {
          projectId,
          documentId,
          contractAPdf: contractAPdfPath(contractA),
          contractBPdf: contractBPdfPath(contractB),
          base: contractA,
          revision: contractB,
        }),
    );

    await recorder.step(
      "P0C-PROD-01-RELOGIN",
      "Re-login and re-observe the same durable change",
      async () => {
        await signOutThroughUi(page);
        await signInSyntheticProductionUser(page);
        const projectLink = page.getByRole("link", { name: projectName }).first();
        await expect(projectLink).toBeVisible({ timeout: 30_000 });
        await projectLink.click();
        await page.waitForURL(new RegExp(`/projects/${projectId}/`), {
          timeout: 30_000,
        });

        const afterRelogin = await assertWhatChangedThroughNavigation(page, recorder, {
          projectId,
          documentId,
          contractAPdf: contractAPdfPath(contractA),
          contractBPdf: contractBPdfPath(contractB),
          base: contractA,
          revision: contractB,
        });
        expect(afterRelogin.changeEventId).toBe(firstObservation.changeEventId);
        expect(afterRelogin.sourceRevisionId).toBe(firstObservation.sourceRevisionId);
        expect(afterRelogin.targetRevisionId).toBe(firstObservation.targetRevisionId);
      },
    );

    const recorderPath = recorder.write();
    const classification = recorder.classification();
    if (classification !== "PASS") {
      throw new Error(`P0C_PRODUCTION_JOURNEY_NOT_PASS:${classification}`);
    }

    mkdirSync(path.dirname(OUTPUT), { recursive: true });
    writeFileSync(
      OUTPUT,
      JSON.stringify(
        {
          schema: "c2pro-p0c-production-run/v1",
          run_id: id,
          project_name: projectName,
          project_id: projectId,
          document_id: documentId,
          from_revision_id: firstObservation.sourceRevisionId,
          to_revision_id: firstObservation.targetRevisionId,
          change_event_id: firstObservation.changeEventId,
          change_occurred_at: firstObservation.occurredAt,
          relogin_verified: true,
          unchanged_controls_not_reported_changed: true,
          all_reported_changes_evidence_backed: true,
          recorder_path: path.relative(process.cwd(), recorderPath),
          classification,
        },
        null,
        2,
      ),
      "utf8",
    );
  });
});
