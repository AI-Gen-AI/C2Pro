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
import { assertWhatChangedThroughNavigation } from "../support/pj01/what-changed";
import {
  signInSyntheticProductionUser,
  signOutThroughUi,
} from "./support/prod-auth.synthetic";
import { requireProductionOrigin } from "./support/prod-preflight";

const OUTPUT = path.join(
  process.cwd(),
  "playwright",
  ".prod-acceptance",
  "p0c-run.json",
);
const JOURNEY_TIMEOUT_MS = 15 * 60_000;

function required(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`P0C_PROD_MISSING_ENV:${name}`);
  return value;
}

function baseUrl(): string {
  return requireProductionOrigin(
    process.env.PROD_ACCEPTANCE_BASE_URL ?? "https://c2pro.io",
  );
}

test("P0c production: same-document revision B produces durable honest What Changed", async ({
  page,
}) => {
  test.setTimeout(JOURNEY_TIMEOUT_MS);

  const projectId = required("P0C_ACCEPTANCE_PROJECT_ID");
  const documentId = required("P0C_ACCEPTANCE_DOCUMENT_ID");
  const expectedSourceRevisionId = required("P0C_ACCEPTANCE_SOURCE_REVISION_ID");
  const base = loadContractAManifest();
  const revisionManifest = loadContractBManifest();
  const recorder = new Pj01RunRecorder({
    runId: `p0c-${process.env.GITHUB_RUN_ID ?? "manual"}-${process.env.GITHUB_RUN_ATTEMPT ?? "1"}`,
    rootDir: path.join(
      process.cwd(),
      "playwright",
      ".prod-acceptance",
      "p0c",
    ),
    mode: "strict",
  });

  let succeeded = false;
  try {
    await signInSyntheticProductionUser(page);
    await page.goto(`${baseUrl()}/projects/${projectId}/documents`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId(`document-row-${documentId}`)).toBeVisible({
      timeout: 30_000,
    });

    const revision = await recorder.step(
      "P0C-PROD-S1",
      "Upload Contract B as a new version of the same document",
      async () =>
        uploadNewVersionThroughUi(page, recorder, {
          projectId,
          documentId,
          filePath: contractBPdfPath(revisionManifest),
        }),
    );
    if (revision.documentId !== documentId || revision.documentsListed !== 1) {
      throw new Error("P0C_PROD_REVISION_IDENTITY_FAILED");
    }

    const processing = await recorder.step(
      "P0C-PROD-S2",
      "Wait for revision B analysis without reload workaround",
      async () =>
        observeProcessingWithoutReload(page, recorder, {
          projectId,
          documentId,
        }),
    );
    if (
      processing.evaluation.outcome !== "analyzed" ||
      processing.evaluation.violations.length > 0
    ) {
      throw new Error(
        `P0C_PROD_REVISION_PROCESSING_FAILED:${processing.evaluation.outcome}`,
      );
    }

    const first = await recorder.step(
      "P0C-PROD-S3",
      "Validate timeline and semantic change detail",
      async () =>
        assertWhatChangedThroughNavigation(page, recorder, {
          projectId,
          documentId,
          contractAPdf: contractAPdfPath(base),
          contractBPdf: contractBPdfPath(revisionManifest),
          base,
          revision: revisionManifest,
        }),
    );

    if (first.sourceRevisionId !== expectedSourceRevisionId) {
      throw new Error(
        `P0C_PROD_SOURCE_REVISION_DRIFT:expected=${expectedSourceRevisionId};observed=${first.sourceRevisionId}`,
      );
    }
    if (first.targetRevisionId === first.sourceRevisionId) {
      throw new Error("P0C_PROD_TARGET_REVISION_NOT_DISTINCT");
    }

    const initialBlockers = recorder.blockingFindings();
    if (initialBlockers.length > 0) {
      throw new Error(
        `P0C_PROD_BLOCKING_FINDINGS:${initialBlockers
          .map((finding) => finding.code)
          .join(",")}`,
      );
    }

    await recorder.step(
      "P0C-PROD-S4",
      "Re-login and prove the same change is durable",
      async () => {
        await signOutThroughUi(page);
        await signInSyntheticProductionUser(page);
        await page.goto(`${baseUrl()}/projects/${projectId}/documents`, {
          waitUntil: "domcontentloaded",
        });
      },
    );

    const afterRelogin = await recorder.step(
      "P0C-PROD-S5",
      "Re-read What Changed after fresh production session",
      async () =>
        assertWhatChangedThroughNavigation(page, recorder, {
          projectId,
          documentId,
          contractAPdf: contractAPdfPath(base),
          contractBPdf: contractBPdfPath(revisionManifest),
          base,
          revision: revisionManifest,
        }),
    );

    if (
      afterRelogin.changeEventId !== first.changeEventId ||
      afterRelogin.sourceRevisionId !== first.sourceRevisionId ||
      afterRelogin.targetRevisionId !== first.targetRevisionId
    ) {
      throw new Error("P0C_PROD_RELOGIN_DURABILITY_MISMATCH");
    }

    const blockers = recorder.blockingFindings();
    if (blockers.length > 0) {
      throw new Error(
        `P0C_PROD_BLOCKING_FINDINGS_AFTER_RELOGIN:${blockers
          .map((finding) => finding.code)
          .join(",")}`,
      );
    }

    mkdirSync(path.dirname(OUTPUT), { recursive: true });
    writeFileSync(
      OUTPUT,
      JSON.stringify(
        {
          schema: "c2pro-p0c-prod-run/v1",
          project_id: projectId,
          document_id: documentId,
          source_revision_id: first.sourceRevisionId,
          target_revision_id: first.targetRevisionId,
          change_event_id: first.changeEventId,
          occurred_at: first.occurredAt,
          relogin_verified: true,
          documents_listed_after_revision: revision.documentsListed,
          processing_outcome: processing.evaluation.outcome,
          navigation_mode: recorder.mode,
          classification: recorder.classification(),
        },
        null,
        2,
      ),
      "utf8",
    );
    succeeded = true;
  } finally {
    recorder.write();
    if (!succeeded) {
      // The recorder is the bounded failure artifact. Never fabricate p0c-run.json.
    }
  }
});
