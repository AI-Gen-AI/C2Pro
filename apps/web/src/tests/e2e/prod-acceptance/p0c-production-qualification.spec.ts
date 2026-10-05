import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Response } from "@playwright/test";

import {
  contractAPdfPath,
  loadContractAManifest,
} from "../../pj01/fixture-contract";
import {
  contractBPdfPath,
  loadContractBManifest,
} from "../../pj01/revision-fixture";
import { ANALYSIS_BUDGET_MS, observeProcessingWithoutReload } from "../support/pj01/processing";
import { uploadNewVersionThroughUi } from "../support/pj01/revision";
import { Pj01RunRecorder } from "../support/pj01/run-recorder";
import { assertWhatChangedThroughNavigation } from "../support/pj01/what-changed";
import { signInSyntheticProductionUser } from "./support/prod-auth.synthetic";

const OUTPUT_DIR = path.join(process.cwd(), "playwright", ".p0c-prod");
const RUN_OUTPUT = path.join(OUTPUT_DIR, "run.json");
const TIMELINE_OUTPUT = path.join(OUTPUT_DIR, "timeline.json");
const DETAIL_OUTPUT = path.join(OUTPUT_DIR, "change-detail.json");

function requiredEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`P0C_PROD_MISSING_ENV:${name}`);
  return value;
}

function sha256(file: string): string {
  return createHash("sha256").update(readFileSync(file)).digest("hex");
}

function writeJson(file: string, value: unknown): void {
  if (!existsSync(OUTPUT_DIR)) mkdirSync(OUTPUT_DIR, { recursive: true });
  writeFileSync(file, JSON.stringify(value, null, 2), "utf8");
}

function expectedBackendOrigin(): string {
  const raw = requiredEnv("P0C_EXPECTED_BACKEND_ORIGIN");
  const parsed = new URL(raw);
  if (parsed.protocol !== "https:" || parsed.username || parsed.password || parsed.pathname !== "/") {
    throw new Error("P0C_PROD_BACKEND_ORIGIN_INVALID");
  }
  return parsed.origin;
}

test.describe("P0c production qualification — continuation of accepted P0b project", () => {
  test.describe.configure({ mode: "serial", timeout: ANALYSIS_BUDGET_MS + 600_000 });

  test("revision B of the accepted document produces truthful What Changed evidence", async ({ page }) => {
    const runId = requiredEnv("P0C_QUAL_RUN_ID");
    const projectId = requiredEnv("P0C_QUAL_PROJECT_ID");
    const documentId = requiredEnv("P0C_QUAL_DOCUMENT_ID");
    const sourceRevisionId = requiredEnv("P0C_QUAL_SOURCE_REVISION_ID");
    const backendOrigin = expectedBackendOrigin();

    const base = loadContractAManifest();
    const revisionManifest = loadContractBManifest();
    const contractA = contractAPdfPath(base);
    const contractB = contractBPdfPath(revisionManifest);
    const sourceBlobHash = sha256(contractA);
    const targetBlobHash = sha256(contractB);

    const recorder = new Pj01RunRecorder({
      runId,
      rootDir: path.join(OUTPUT_DIR, "pj01"),
      mode: "strict",
    });
    recorder.record("qualification", "P0c");
    recorder.record("projectId", projectId);
    recorder.record("documentId", documentId);
    recorder.record("expectedSourceRevisionId", sourceRevisionId);

    const timelineBodies: unknown[] = [];
    const detailBodies: unknown[] = [];
    const captureResponse = async (response: Response): Promise<void> => {
      if (!response.ok() || response.request().method() !== "GET") return;
      const pathname = new URL(response.url()).pathname;
      try {
        if (new RegExp(`/projects/${projectId}/timeline/?$`).test(pathname)) {
          timelineBodies.push(await response.json());
          return;
        }
        if (new RegExp(`/projects/${projectId}/documents/${documentId}/changes/[0-9a-f-]{36}/?$`).test(pathname)) {
          detailBodies.push(await response.json());
        }
      } catch {
        // Capture is supporting evidence only; the canonical PJ-01 evaluator
        // still fails the run if the actual product response is unusable.
      }
    };
    page.on("response", captureResponse);

    try {
      await recorder.step("P0C-P1", "Sign in to production qualification tenant", async () => {
        await signInSyntheticProductionUser(page);
        await expect(page.getByRole("heading", { name: /projects/i })).toBeVisible({ timeout: 30_000 });
      });

      await recorder.step("P0C-P2", "Open accepted P0b project", async () => {
        await page.goto(`${process.env.PROD_ACCEPTANCE_BASE_URL ?? "https://c2pro.io"}/projects/${projectId}/documents`);
        await page.waitForURL(new RegExp(`/projects/${projectId}/documents`), { timeout: 30_000 });
        await expect(page.getByTestId("documents-page")).toBeVisible({ timeout: 30_000 });
        await expect(page.getByTestId(`document-row-${documentId}`)).toBeVisible({ timeout: 30_000 });
      });

      const acceptedRevisionResponse = page.waitForResponse(
        (response) =>
          response.request().method() === "PATCH" &&
          new RegExp(`/documents/${documentId}/file/?$`).test(new URL(response.url()).pathname),
        { timeout: 120_000 },
      );

      const revision = await recorder.step("P0C-P3", "Upload Contract B as revision of same logical document", async () =>
        uploadNewVersionThroughUi(page, recorder, {
          projectId,
          documentId,
          filePath: contractB,
        }),
      );

      const accepted = await acceptedRevisionResponse;
      expect(new URL(accepted.url()).origin, "revision upload must hit the observed production backend").toBe(backendOrigin);
      expect(revision.documentId).toBe(documentId);
      expect(revision.documentsListed).toBe(1);

      const revisionProcessing = await recorder.step("P0C-P4", "Wait for revision B analysis without reload workaround", async () => {
        const observed = await observeProcessingWithoutReload(page, recorder, { projectId, documentId });
        if (observed.evaluation.outcome !== "analyzed" || observed.evaluation.violations.length > 0) {
          const codes = observed.evaluation.violations.map((item) => item.code).join(",");
          throw new Error(`P0C_PROD_REVISION_PROCESSING_FAILED:outcome=${observed.evaluation.outcome};violations=${codes}`);
        }
        return observed;
      });

      const whatChanged = await recorder.step("P0C-P5", "Validate What Changed through canonical PJ-01 evaluator", async () =>
        assertWhatChangedThroughNavigation(page, recorder, {
          projectId,
          documentId,
          contractAPdf: contractA,
          contractBPdf: contractB,
          base,
          revision: revisionManifest,
        }),
      );

      expect(whatChanged.sourceRevisionId, "What Changed must start from the accepted P0b revision A").toBe(sourceRevisionId);
      expect(whatChanged.targetRevisionId).not.toBe(sourceRevisionId);
      expect(recorder.blockingFindings(), "no blocking P0c findings").toEqual([]);

      // Let response handlers finish serialising the API bodies captured while
      // the canonical UI evaluator was exercising the timeline/detail surfaces.
      await page.waitForTimeout(100);
      expect(timelineBodies.length, "timeline API capture").toBeGreaterThan(0);
      expect(detailBodies.length, "change-detail API capture").toBeGreaterThan(0);

      writeJson(TIMELINE_OUTPUT, timelineBodies.at(-1));
      writeJson(DETAIL_OUTPUT, detailBodies.at(-1));
      writeJson(RUN_OUTPUT, {
        schema: "c2pro-p0c-production-run/v1",
        run_id: runId,
        project_id: projectId,
        document_id: documentId,
        from_revision_id: whatChanged.sourceRevisionId,
        to_revision_id: whatChanged.targetRevisionId,
        change_event_id: whatChanged.changeEventId,
        occurred_at: whatChanged.occurredAt,
        source_blob_hash: sourceBlobHash,
        target_blob_hash: targetBlobHash,
        negative_control: {
          mode: "unchanged_declared_facts_not_reported_changed",
          fact_count: base.facts.filter((fact) =>
            revisionManifest.expected_revision_change.no_change_control_fact_keys.includes(fact.key),
          ).length,
        },
        document_version: revision.version,
        documents_listed: revision.documentsListed,
        processing_outcome: revisionProcessing.evaluation.outcome,
        pj01_classification: recorder.classification(),
        blocking_findings: recorder.blockingFindings(),
        backend_origin: backendOrigin,
        timeline_capture: "playwright/.p0c-prod/timeline.json",
        change_detail_capture: "playwright/.p0c-prod/change-detail.json",
      });
    } finally {
      page.off("response", captureResponse);
      recorder.write();
    }
  });
});
