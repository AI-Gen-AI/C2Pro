import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

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
import { uploadDocumentThroughUi } from "../support/pj01/upload";
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
const JOURNEY_TIMEOUT_MS = 20 * 60_000;
const PROJECT_URL = /\/projects\/([0-9a-f-]{36})\/documents/;

function baseUrl(): string {
  return requireProductionOrigin(
    process.env.PROD_ACCEPTANCE_BASE_URL ?? "https://c2pro.io",
  );
}

async function createQualificationProject(
  page: Page,
  runId: string,
  label = "Primary",
): Promise<string> {
  await page.goto(`${baseUrl()}/projects`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: /projects/i })).toBeVisible({
    timeout: 30_000,
  });

  await page.getByRole("button", { name: /new project|create project/i }).first().click();
  const input = page.getByTestId("project-name-input");
  await expect(input).toBeEditable({ timeout: 15_000 });
  await input.fill(`P0c Qualification ${label} ${runId}`);
  await page.getByRole("button", { name: "Next step" }).click();
  await page.getByRole("button", { name: "Review project" }).click();

  const createButton = page.getByTestId("create-project-button");
  await expect(createButton).toBeEnabled({ timeout: 15_000 });
  const created = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/projects" &&
      response.ok(),
    { timeout: 60_000 },
  );
  await createButton.click();
  const response = await created;
  expect(response.status(), "project creation must be accepted").toBeLessThan(300);

  await page.waitForURL(PROJECT_URL, { timeout: 60_000 });
  await expect(page.getByTestId("documents-page")).toBeVisible({ timeout: 30_000 });
  const projectId = page.url().match(PROJECT_URL)?.[1];
  if (!projectId) throw new Error("P0C_PROD_PROJECT_ID_UNRESOLVED");
  return projectId;
}

interface NoChangeOutcome {
  eventId: string;
  sourceRevisionId: string;
  targetRevisionId: string;
}

async function assertIdenticalReuploadProducesHonestNoChange(
  page: Page,
  projectId: string,
  documentId: string,
): Promise<NoChangeOutcome> {
  type TimelineItem = {
    event_id: string;
    event_type: string;
    state: string;
    change_cause: string | null;
    document_id?: string | null;
    provenance?: {
      source_revision_id?: string | null;
      target_revision_id?: string | null;
    };
  };

  let outcome: TimelineItem | undefined;
  const onResponse = async (
    response: import("@playwright/test").Response,
  ): Promise<void> => {
    if (response.request().method() !== "GET" || !response.ok()) return;
    const pathname = new URL(response.url()).pathname.replace(/\/$/, "");
    if (pathname !== `/projects/${projectId}/timeline`) return;
    try {
      const body = (await response.json()) as { items?: TimelineItem[] };
      outcome = body.items?.find(
        (item) =>
          item.event_type === "revision.changed" &&
          item.document_id === documentId &&
          item.state === "ready" &&
          item.change_cause === null,
      );
    } catch {
      // A malformed timeline response cannot satisfy the negative proof.
    }
  };

  page.on("response", onResponse);
  try {
    await page.goto(`${baseUrl()}/projects/${projectId}/changes`, {
      waitUntil: "domcontentloaded",
    });
    const deadline = Date.now() + 180_000;
    while (!outcome && Date.now() < deadline) {
      await page.waitForTimeout(2_000);
    }
    if (!outcome) {
      throw new Error("P0C_PROD_NO_CHANGE_OUTCOME_MISSING");
    }

    const sourceRevisionId = String(outcome.provenance?.source_revision_id ?? "");
    const targetRevisionId = String(outcome.provenance?.target_revision_id ?? "");
    if (
      !sourceRevisionId ||
      !targetRevisionId ||
      sourceRevisionId === targetRevisionId
    ) {
      throw new Error("P0C_PROD_NO_CHANGE_REVISION_IDENTITY_INVALID");
    }

    const card = page.getByTestId(`change-item-${outcome.event_id}`);
    await expect(card).toBeVisible({ timeout: 30_000 });
    await expect(card.getByText("No material change found")).toBeVisible();

    return {
      eventId: outcome.event_id,
      sourceRevisionId,
      targetRevisionId,
    };
  } finally {
    page.off("response", onResponse);
  }
}

test("P0c production: fresh PJ-01 Contract A -> same-document B -> durable honest What Changed", async ({
  page,
}) => {
  test.setTimeout(JOURNEY_TIMEOUT_MS);

  const base = loadContractAManifest();
  const revisionManifest = loadContractBManifest();
  const runId = `p0c-${process.env.GITHUB_RUN_ID ?? "manual"}-${process.env.GITHUB_RUN_ATTEMPT ?? "1"}`;
  const recorder = new Pj01RunRecorder({
    runId,
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
    await recorder.step("P0C-PROD-S1", "Real production sign-in", async () => {
      await signInSyntheticProductionUser(page);
    });

    const projectId = await recorder.step(
      "P0C-PROD-S2",
      "Create a fresh synthetic qualification project",
      async () => createQualificationProject(page, runId, "Primary"),
    );
    recorder.record("projectId", projectId);

    const uploadA = await recorder.step(
      "P0C-PROD-S3",
      "Upload canonical PJ-01 Contract A",
      async () =>
        uploadDocumentThroughUi(page, recorder, {
          projectId,
          filePath: contractAPdfPath(base),
          documentType: base.document_type,
        }),
    );
    const documentId = uploadA.documentId;

    const processingA = await recorder.step(
      "P0C-PROD-S4",
      "Wait for Contract A analysis without reload workaround",
      async () =>
        observeProcessingWithoutReload(page, recorder, {
          projectId,
          documentId,
        }),
    );
    if (
      processingA.evaluation.outcome !== "analyzed" ||
      processingA.evaluation.violations.length > 0
    ) {
      throw new Error(
        `P0C_PROD_SOURCE_PROCESSING_FAILED:${processingA.evaluation.outcome}`,
      );
    }

    const revision = await recorder.step(
      "P0C-PROD-S5",
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

    const processingB = await recorder.step(
      "P0C-PROD-S6",
      "Wait for Contract B analysis without reload workaround",
      async () =>
        observeProcessingWithoutReload(page, recorder, {
          projectId,
          documentId,
        }),
    );
    if (
      processingB.evaluation.outcome !== "analyzed" ||
      processingB.evaluation.violations.length > 0
    ) {
      throw new Error(
        `P0C_PROD_REVISION_PROCESSING_FAILED:${processingB.evaluation.outcome}`,
      );
    }

    const first = await recorder.step(
      "P0C-PROD-S7",
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
      "P0C-PROD-S8",
      "Re-login through production auth",
      async () => {
        await signOutThroughUi(page);
        await signInSyntheticProductionUser(page);
      },
    );

    await page.goto(`${baseUrl()}/projects/${projectId}/documents`);
    await expect(page.getByTestId("documents-page")).toBeVisible({ timeout: 30_000 });

    const afterRelogin = await recorder.step(
      "P0C-PROD-S9",
      "Re-read What Changed after a fresh production session",
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

    const negativeProjectId = await recorder.step(
      "P0C-PROD-N1",
      "Create isolated no-change qualification project",
      async () => createQualificationProject(page, runId, "Negative"),
    );

    const negativeUpload = await recorder.step(
      "P0C-PROD-N2",
      "Upload Contract B as negative-case baseline",
      async () =>
        uploadDocumentThroughUi(page, recorder, {
          projectId: negativeProjectId,
          filePath: contractBPdfPath(revisionManifest),
          documentType: revisionManifest.document_type,
        }),
    );
    const negativeDocumentId = negativeUpload.documentId;

    const negativeBaselineProcessing = await recorder.step(
      "P0C-PROD-N3",
      "Analyze negative-case baseline",
      async () =>
        observeProcessingWithoutReload(page, recorder, {
          projectId: negativeProjectId,
          documentId: negativeDocumentId,
        }),
    );
    if (
      negativeBaselineProcessing.evaluation.outcome !== "analyzed" ||
      negativeBaselineProcessing.evaluation.violations.length > 0
    ) {
      throw new Error(
        `P0C_PROD_NEGATIVE_BASELINE_PROCESSING_FAILED:${negativeBaselineProcessing.evaluation.outcome}`,
      );
    }

    const identicalRevision = await recorder.step(
      "P0C-PROD-N4",
      "Re-upload identical Contract B as the same logical document",
      async () =>
        uploadNewVersionThroughUi(page, recorder, {
          projectId: negativeProjectId,
          documentId: negativeDocumentId,
          filePath: contractBPdfPath(revisionManifest),
        }),
    );
    if (
      identicalRevision.documentId !== negativeDocumentId ||
      identicalRevision.documentsListed !== 1
    ) {
      throw new Error("P0C_PROD_NEGATIVE_REVISION_IDENTITY_FAILED");
    }

    const negativeTargetProcessing = await recorder.step(
      "P0C-PROD-N5",
      "Analyze identical re-upload",
      async () =>
        observeProcessingWithoutReload(page, recorder, {
          projectId: negativeProjectId,
          documentId: negativeDocumentId,
        }),
    );
    if (
      negativeTargetProcessing.evaluation.outcome !== "analyzed" ||
      negativeTargetProcessing.evaluation.violations.length > 0
    ) {
      throw new Error(
        `P0C_PROD_NEGATIVE_TARGET_PROCESSING_FAILED:${negativeTargetProcessing.evaluation.outcome}`,
      );
    }

    const noChange = await recorder.step(
      "P0C-PROD-N6",
      "Prove identical content yields an honest no-change outcome",
      async () =>
        assertIdenticalReuploadProducesHonestNoChange(
          page,
          negativeProjectId,
          negativeDocumentId,
        ),
    );

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
          source_processing_outcome: processingA.evaluation.outcome,
          target_processing_outcome: processingB.evaluation.outcome,
          navigation_mode: recorder.mode,
          classification: recorder.classification(),
          negative_project_id: negativeProjectId,
          negative_document_id: negativeDocumentId,
          negative_source_revision_id: noChange.sourceRevisionId,
          negative_target_revision_id: noChange.targetRevisionId,
          negative_change_event_id: noChange.eventId,
          negative_source_processing_outcome:
            negativeBaselineProcessing.evaluation.outcome,
          negative_target_processing_outcome:
            negativeTargetProcessing.evaluation.outcome,
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
