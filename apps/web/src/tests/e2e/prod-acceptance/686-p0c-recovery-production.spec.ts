import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { contractAPdfPath, loadContractAManifest } from "../../pj01/fixture-contract";
import { contractBPdfPath, loadContractBManifest } from "../../pj01/revision-fixture";
import { clickProjectTab } from "../support/pj01/health";
import { observeProcessingWithoutReload } from "../support/pj01/processing";
import { uploadNewVersionThroughUi } from "../support/pj01/revision";
import { Pj01RunRecorder } from "../support/pj01/run-recorder";
import { assertWhatChangedThroughNavigation } from "../support/pj01/what-changed";
import {
  signInSyntheticProductionUser,
  signOutThroughUi,
} from "./support/prod-auth.synthetic";
import { requireProductionOrigin } from "./support/prod-preflight";

const RUN_OUTPUT = path.join(process.cwd(), "playwright", ".prod-p0c", "run.json");
const JOURNEY_TIMEOUT_MS = 20 * 60_000;

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

test.describe("Issue #686 P0c production recovery", () => {
  test.describe.configure({ mode: "serial", timeout: JOURNEY_TIMEOUT_MS });

  test("recover failed revision B, prove What Changed, then prove semantic no-change C", async ({ page }) => {
    const runId = requiredEnv("PROD_ACCEPTANCE_RUN_ID");
    const projectId = requiredEnv("PROD_P0C_PROJECT_ID");
    const documentId = requiredEnv("PROD_P0C_DOCUMENT_ID");
    const sourceRevisionId = requiredEnv("PROD_P0C_SOURCE_REVISION_ID");
    const targetRevisionId = requiredEnv("PROD_P0C_TARGET_REVISION_ID");
    const targetGeneration = requiredEnv("PROD_P0C_TARGET_GENERATION");
    const noChangePdf = requiredEnv("PROD_P0C_NO_CHANGE_PDF");
    const expectedNoChangeSha256 = requiredEnv("PROD_P0C_NO_CHANGE_EXPECTED_SHA256");
    const noChangeFixtureSha256 = createHash("sha256")
      .update(readFileSync(noChangePdf))
      .digest("hex");
    expect(noChangeFixtureSha256).toBe(expectedNoChangeSha256);

    const recorder = new Pj01RunRecorder({
      runId,
      rootDir: path.join(process.cwd(), "playwright", ".prod-p0c", "pj01"),
      mode: "strict",
    });
    const baseManifest = loadContractAManifest();
    const revisionManifest = loadContractBManifest();

    try {
      await recorder.step("P0C-REC-S1", "Real production sign-in", async () => {
        await signInSyntheticProductionUser(page);
      });

      await recorder.step("P0C-REC-S2", "Retry existing failed revision B through UI", async () => {
        await page.goto(`${baseUrl()}/projects/${projectId}/documents`);
        const row = page.getByTestId(`document-row-${documentId}`);
        await expect(row).toBeVisible({ timeout: 30_000 });
        const retry = row.getByRole("button", { name: /^Retry processing / });
        await expect(retry).toBeVisible({ timeout: 30_000 });

        const routePattern = `**/projects/${projectId}/documents/${documentId}/reprocess*`;
        await page.route(routePattern, async (route) => {
          const url = new URL(route.request().url());
          url.searchParams.set("expected_revision_id", targetRevisionId);
          url.searchParams.set("expected_generation", targetGeneration);
          url.searchParams.set("expected_stage", "INGESTION");
          url.searchParams.set("expected_phase", "PENDING");
          url.searchParams.set("expected_outcome", "ingestion_failed");
          await route.continue({ url: url.toString() });
        });
        try {
          await retry.click();
        } finally {
          await page.unroute(routePattern);
        }
      });

      const processing = await recorder.step(
        "P0C-REC-S3",
        "Observe recovered revision B processing without reload",
        async () => observeProcessingWithoutReload(page, recorder, { projectId, documentId }),
      );
      expect(processing.evaluation.outcome).toBe("analyzed");
      expect(processing.evaluation.violations).toEqual([]);

      const whatChanged = await recorder.step(
        "P0C-REC-S4",
        "Prove What Changed A to recovered B",
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
      expect(whatChanged.sourceRevisionId).toBe(sourceRevisionId);
      expect(whatChanged.targetRevisionId).toBe(targetRevisionId);
      expect(recorder.blockingFindings()).toEqual([]);

      await recorder.step("P0C-REC-S5", "Prove timeline durability after real relogin", async () => {
        await signOutThroughUi(page);
        await signInSyntheticProductionUser(page);
        await page.goto(`${baseUrl()}/projects/${projectId}/changes`);
        await expect(page.getByTestId(`change-item-${whatChanged.changeEventId}`)).toBeVisible({
          timeout: 60_000,
        });
      });

      const noChange = await recorder.step(
        "P0C-REC-S6",
        "Prove byte-distinct parser-equivalent revision is NO_CHANGE",
        async () => {
          const uploaded = await uploadNewVersionThroughUi(page, recorder, {
            projectId,
            documentId,
            filePath: noChangePdf,
          });
          expect(uploaded.documentId).toBe(documentId);
          expect(uploaded.documentsListed).toBe(1);

          const processed = await observeProcessingWithoutReload(page, recorder, { projectId, documentId });
          expect(processed.evaluation.outcome).toBe("analyzed");
          expect(processed.evaluation.violations).toEqual([]);

          const timelineResponse = page.waitForResponse(
            (response) =>
              response.request().method() === "GET" &&
              response.ok() &&
              new RegExp(`/projects/${projectId}/timeline/?$`).test(new URL(response.url()).pathname),
            { timeout: 60_000 },
          );

          await clickProjectTab(page, recorder, projectId, "changes", "P0C_NO_CHANGE_TAB_NOT_NAVIGABLE");
          const payload = (await (await timelineResponse).json()) as {
            items?: Array<{
              event_id: string;
              event_type: string;
              state: string;
              change_cause: string | null;
              document_id: string | null;
              occurred_at: string;
              provenance?: Record<string, unknown>;
            }>;
          };
          const afterPositive = Date.parse(whatChanged.occurredAt);
          const outcome = (payload.items ?? [])
            .filter(
              (item) =>
                item.event_type === "revision.changed" &&
                item.document_id === documentId &&
                Date.parse(item.occurred_at) > afterPositive,
            )
            .sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at))[0];
          if (!outcome) throw new Error("P0C_NO_CHANGE_OUTCOME_MISSING");
          expect(outcome.state).toBe("ready");
          expect(outcome.change_cause).toBeNull();

          const source = String(outcome.provenance?.source_revision_id ?? "");
          const target = String(outcome.provenance?.target_revision_id ?? "");
          expect(source).toBe(targetRevisionId);
          if (!target || target === source) throw new Error("P0C_NO_CHANGE_REVISION_IDENTITY_INVALID");

          const card = page.getByTestId(`change-item-${outcome.event_id}`);
          await expect(card.getByText("No material change found")).toBeVisible({ timeout: 30_000 });
          await recorder.screenshot(page, "h3-no-material-change");

          return {
            eventId: outcome.event_id,
            sourceRevisionId: source,
            targetRevisionId: target,
            occurredAt: outcome.occurred_at,
            changeCause: outcome.change_cause,
            fixtureClass: "byte-distinct-parser-equivalent",
            fixtureSha256: noChangeFixtureSha256,
            processingOutcome: processed.evaluation.outcome,
          };
        },
      );

      expect(recorder.blockingFindings()).toEqual([]);
      writeRunEvidence({
        schema: "c2pro-p0c-prod-run/v1",
        run_id: runId,
        project_id: projectId,
        document_id: documentId,
        source_revision_id: whatChanged.sourceRevisionId,
        target_revision_id: whatChanged.targetRevisionId,
        change_event_id: whatChanged.changeEventId,
        occurred_at: whatChanged.occurredAt,
        documents_listed: 1,
        processing_outcome: processing.evaluation.outcome,
        relogin_verified: true,
        no_change_event_id: noChange.eventId,
        no_change_source_revision_id: noChange.sourceRevisionId,
        no_change_target_revision_id: noChange.targetRevisionId,
        no_change_occurred_at: noChange.occurredAt,
        no_change_change_cause: noChange.changeCause,
        no_change_fixture_class: noChange.fixtureClass,
        no_change_fixture_sha256: noChange.fixtureSha256,
        no_change_processing_outcome: noChange.processingOutcome,
        blocking_findings: recorder.blockingFindings(),
      });
    } finally {
      recorder.write();
    }
  });
});
