import path from "node:path";

import { expect, test } from "@playwright/test";

import { observeAuth } from "../support/p0b-auth";
import { clickProjectTab } from "../support/pj01/health";
import { observeProcessingWithoutReload } from "../support/pj01/processing";
import { uploadNewVersionThroughUi } from "../support/pj01/revision";
import {
  runPj01FirstHalf,
  runPj01SecondHalf,
} from "../support/pj01/journey";
import { Pj01RunRecorder } from "../support/pj01/run-recorder";
import { assertWhatChangedThroughNavigation } from "../support/pj01/what-changed";
import {
  contractAPdfPath,
} from "../../pj01/fixture-contract";
import {
  contractBPdfPath,
  loadContractBManifest,
} from "../../pj01/revision-fixture";
import {
  signInSyntheticProductionUser,
  signOutThroughUi,
} from "./support/prod-auth.synthetic";
import { requireProductionOrigin } from "./support/prod-preflight";

const JOURNEY_TIMEOUT_MS = 35 * 60_000;

test.describe("Issue #686 P0c production qualification", () => {
  test.describe.configure({ mode: "serial", timeout: JOURNEY_TIMEOUT_MS });

  test("real production user proves two-revision What Changed durability", async ({
    page,
  }, testInfo) => {
    const runId = process.env.P0C_PROD_RUN_ID;
    if (!runId) throw new Error("P0C_PROD_MISSING_ENV:P0C_PROD_RUN_ID");

    const baseURL = requireProductionOrigin(
      process.env.PROD_ACCEPTANCE_BASE_URL ?? "https://c2pro.io",
    );
    const recorder = new Pj01RunRecorder({
      runId,
      rootDir: path.join(process.cwd(), "playwright", ".prod-p0c"),
      mode: "strict",
    });

    try {
      await signInSyntheticProductionUser(page);

      // Install the canonical PJ-01 auth continuity observer after production
      // authentication, then make one ordinary protected navigation so bearer
      // and tenant continuity are observed by the same helper used by PJ-01.
      const authObservation = observeAuth(page, baseURL);
      await page.goto(`${baseURL}/projects`);
      await expect(page.getByRole("heading", { name: /projects/i })).toBeVisible({
        timeout: 30_000,
      });

      const first = await runPj01FirstHalf(page, {
        baseURL,
        recorder,
        projectName: `P0c PROD ${runId}`,
        authObservation,
      });
      const second = await runPj01SecondHalf(page, { recorder, first });

      recorder.record("p0cProduction", {
        projectId: first.projectId,
        documentId: first.documentId,
        sourceRevisionId: second.whatChanged.sourceRevisionId,
        targetRevisionId: second.whatChanged.targetRevisionId,
        changeEventId: second.whatChanged.changeEventId,
        occurredAt: second.whatChanged.occurredAt,
      });

      // Durability cannot be inferred from React memory. Sign out through the
      // real UI, authenticate again, and prove the same persisted change from a
      // fresh browser session state.
      await signOutThroughUi(page);
      await signInSyntheticProductionUser(page);
      const revisionManifest = loadContractBManifest();
      const afterRelogin = await assertWhatChangedThroughNavigation(page, recorder, {
        projectId: first.projectId,
        documentId: first.documentId,
        contractAPdf: contractAPdfPath(first.manifest),
        contractBPdf: contractBPdfPath(revisionManifest),
        base: first.manifest,
        revision: revisionManifest,
      });

      expect(afterRelogin.changeEventId).toBe(second.whatChanged.changeEventId);
      expect(afterRelogin.sourceRevisionId).toBe(second.whatChanged.sourceRevisionId);
      expect(afterRelogin.targetRevisionId).toBe(second.whatChanged.targetRevisionId);
      recorder.record("p0cReloginVerified", true);

      // Build step provides a byte-distinct PDF whose parser-visible text is
      // proven identical to Contract B. It must create a real new revision but
      // still produce NO_CHANGE; metadata-only byte drift may never fabricate a
      // business change.
      const noChangePdf = process.env.P0C_NO_CHANGE_PDF;
      if (!noChangePdf) throw new Error("P0C_PROD_MISSING_ENV:P0C_NO_CHANGE_PDF");
      await recorder.step("P0C-N1", "Semantically identical revision remains no material change", async () => {
        await uploadNewVersionThroughUi(page, recorder, {
          projectId: first.projectId,
          documentId: first.documentId,
          filePath: noChangePdf,
        });
        const processed = await observeProcessingWithoutReload(page, recorder, {
          projectId: first.projectId,
          documentId: first.documentId,
        });
        if (processed.evaluation.outcome !== "analyzed" || processed.evaluation.violations.length > 0) {
          throw new Error(`P0C_NO_CHANGE_PROCESSING_FAILED:${processed.evaluation.outcome}`);
        }

        const timelineResponse = page.waitForResponse(
          (response) =>
            response.request().method() === "GET" &&
            response.ok() &&
            new RegExp(`/projects/${first.projectId}/timeline/?import path from "node:path";

import { expect, test } from "@playwright/test";

import { observeAuth } from "../support/p0b-auth";
import { clickProjectTab } from "../support/pj01/health";
import { observeProcessingWithoutReload } from "../support/pj01/processing";
import { uploadNewVersionThroughUi } from "../support/pj01/revision";
import {
  runPj01FirstHalf,
  runPj01SecondHalf,
} from "../support/pj01/journey";
import { Pj01RunRecorder } from "../support/pj01/run-recorder";
import { assertWhatChangedThroughNavigation } from "../support/pj01/what-changed";
import {
  contractAPdfPath,
} from "../../pj01/fixture-contract";
import {
  contractBPdfPath,
  loadContractBManifest,
} from "../../pj01/revision-fixture";
import {
  signInSyntheticProductionUser,
  signOutThroughUi,
} from "./support/prod-auth.synthetic";
import { requireProductionOrigin } from "./support/prod-preflight";

const JOURNEY_TIMEOUT_MS = 35 * 60_000;

test.describe("Issue #686 P0c production qualification", () => {
  test.describe.configure({ mode: "serial", timeout: JOURNEY_TIMEOUT_MS });

  test("real production user proves two-revision What Changed durability", async ({
    page,
  }, testInfo) => {
    const runId = process.env.P0C_PROD_RUN_ID;
    if (!runId) throw new Error("P0C_PROD_MISSING_ENV:P0C_PROD_RUN_ID");

    const baseURL = requireProductionOrigin(
      process.env.PROD_ACCEPTANCE_BASE_URL ?? "https://c2pro.io",
    );
    const recorder = new Pj01RunRecorder({
      runId,
      rootDir: path.join(process.cwd(), "playwright", ".prod-p0c"),
      mode: "strict",
    });

    try {
      await signInSyntheticProductionUser(page);

      // Install the canonical PJ-01 auth continuity observer after production
      // authentication, then make one ordinary protected navigation so bearer
      // and tenant continuity are observed by the same helper used by PJ-01.
      const authObservation = observeAuth(page, baseURL);
      await page.goto(`${baseURL}/projects`);
      await expect(page.getByRole("heading", { name: /projects/i })).toBeVisible({
        timeout: 30_000,
      });

      const first = await runPj01FirstHalf(page, {
        baseURL,
        recorder,
        projectName: `P0c PROD ${runId}`,
        authObservation,
      });
      const second = await runPj01SecondHalf(page, { recorder, first });

      recorder.record("p0cProduction", {
        projectId: first.projectId,
        documentId: first.documentId,
        sourceRevisionId: second.whatChanged.sourceRevisionId,
        targetRevisionId: second.whatChanged.targetRevisionId,
        changeEventId: second.whatChanged.changeEventId,
        occurredAt: second.whatChanged.occurredAt,
      });

      // Durability cannot be inferred from React memory. Sign out through the
      // real UI, authenticate again, and prove the same persisted change from a
      // fresh browser session state.
      await signOutThroughUi(page);
      await signInSyntheticProductionUser(page);
      const revisionManifest = loadContractBManifest();
      const afterRelogin = await assertWhatChangedThroughNavigation(page, recorder, {
        projectId: first.projectId,
        documentId: first.documentId,
        contractAPdf: contractAPdfPath(first.manifest),
        contractBPdf: contractBPdfPath(revisionManifest),
        base: first.manifest,
        revision: revisionManifest,
      });

      expect(afterRelogin.changeEventId).toBe(second.whatChanged.changeEventId);
      expect(afterRelogin.sourceRevisionId).toBe(second.whatChanged.sourceRevisionId);
      expect(afterRelogin.targetRevisionId).toBe(second.whatChanged.targetRevisionId);
).test(
              new URL(response.url()).pathname,
            ),
          { timeout: 60_000 },
        );
        await clickProjectTab(page, recorder, first.projectId, "changes", "P0C_NO_CHANGE_TAB_NOT_NAVIGABLE");
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
        const priorAt = Date.parse(second.whatChanged.occurredAt);
        const noChange = (payload.items ?? [])
          .filter(
            (item) =>
              item.event_type === "revision.changed" &&
              item.document_id === first.documentId &&
              Date.parse(item.occurred_at) > priorAt,
          )
          .sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at))[0];
        if (!noChange) throw new Error("P0C_NO_CHANGE_OUTCOME_MISSING");
        expect(noChange.state).toBe("ready");
        expect(noChange.change_cause).toBeNull();
        const card = page.getByTestId(`change-item-${noChange.event_id}`);
        await expect(card.getByText("No material change found")).toBeVisible({
          timeout: 30_000,
        });
        recorder.record("p0cNoChange", {
          eventId: noChange.event_id,
          targetRevisionId: String(noChange.provenance?.target_revision_id ?? ""),
          changeCause: noChange.change_cause,
          browserLabel: revisionManifest.expected_revision_change.identical_reupload?.browser_label ?? null,
          fixtureClass: "byte-distinct-parser-equivalent",
        });
      });

      expect(recorder.blockingFindings(), "no blocking P0c findings").toEqual([]);
    } finally {
      const runFile = recorder.write();
      testInfo.annotations.push(
        { type: "p0c-classification", description: recorder.classification() },
        { type: "p0c-run", description: runFile },
      );
    }
  });
});
