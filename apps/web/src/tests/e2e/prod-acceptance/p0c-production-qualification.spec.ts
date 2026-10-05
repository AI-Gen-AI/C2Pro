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
import { clickProjectTab } from "../support/pj01/health";
import { ANALYSIS_BUDGET_MS, observeProcessingWithoutReload } from "../support/pj01/processing";
import { uploadNewVersionThroughUi } from "../support/pj01/revision";
import { Pj01RunRecorder } from "../support/pj01/run-recorder";
import { assertWhatChangedThroughNavigation } from "../support/pj01/what-changed";
import { signInSyntheticProductionUser, signOutThroughUi } from "./support/prod-auth.synthetic";

const OUTPUT_DIR = path.join(process.cwd(), "playwright", ".p0c-prod");
const RUN_OUTPUT = path.join(OUTPUT_DIR, "run.json");
const TIMELINE_OUTPUT = path.join(OUTPUT_DIR, "timeline.json");
const DETAIL_OUTPUT = path.join(OUTPUT_DIR, "change-detail.json");
const NO_CHANGE_DETAIL_OUTPUT = path.join(OUTPUT_DIR, "no-change-detail.json");
const FRESH_TIMELINE_OUTPUT = path.join(OUTPUT_DIR, "fresh-session-timeline.json");
const FRESH_DETAIL_OUTPUT = path.join(OUTPUT_DIR, "fresh-session-change-detail.json");

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

      // P0c's fifth acceptance assertion requires a real no-change outcome.
      // Re-upload the exact Contract B bytes as revision C of the SAME logical
      // document. This is a bounded negative control, not a second document or
      // a fabricated event.
      const negativeRevision = await recorder.step("P0C-N1", "Upload identical Contract B as no-change revision C", async () =>
        uploadNewVersionThroughUi(page, recorder, {
          projectId,
          documentId,
          filePath: contractB,
        }),
      );
      expect(negativeRevision.documentId).toBe(documentId);
      expect(negativeRevision.documentsListed).toBe(1);

      await recorder.step("P0C-N2", "Wait for no-change revision C analysis", async () => {
        const observed = await observeProcessingWithoutReload(page, recorder, { projectId, documentId });
        if (observed.evaluation.outcome !== "analyzed" || observed.evaluation.violations.length > 0) {
          const codes = observed.evaluation.violations.map((item) => item.code).join(",");
          throw new Error(`P0C_PROD_NO_CHANGE_PROCESSING_FAILED:outcome=${observed.evaluation.outcome};violations=${codes}`);
        }
      });

      type TimelineItem = {
        event_id: string;
        event_type: string;
        state: string;
        change_cause: string | null;
        document_id: string | null;
        provenance?: {
          source_revision_id?: string;
          target_revision_id?: string;
          source_blob_hash?: string;
          target_blob_hash?: string;
        };
      };
      const timelineItems = (): TimelineItem[] => {
        const body = timelineBodies.at(-1);
        if (!body || typeof body !== "object") return [];
        const items = (body as { items?: unknown }).items;
        return Array.isArray(items) ? (items as TimelineItem[]) : [];
      };
      const findNoChange = (): TimelineItem | undefined =>
        timelineItems().find(
          (item) =>
            item.event_type === "revision.changed" &&
            item.document_id === documentId &&
            item.state === "ready" &&
            item.change_cause === null &&
            item.provenance?.source_revision_id === whatChanged.targetRevisionId &&
            item.provenance?.target_revision_id !== whatChanged.targetRevisionId,
        );

      const noChange = await recorder.step("P0C-N3", "Prove revision C is a real no-change outcome", async () => {
        await clickProjectTab(page, recorder, projectId, "changes", "P0C_NO_CHANGE_TAB_NOT_NAVIGABLE");
        await page.waitForURL(new RegExp(`/projects/${projectId}/changes`), { timeout: 30_000 });

        await expect.poll(() => Boolean(findNoChange()), { timeout: 180_000 }).toBe(true);
        const candidate = findNoChange();
        if (!candidate?.provenance?.target_revision_id) {
          throw new Error("P0C_PROD_NO_CHANGE_OUTCOME_MISSING");
        }
        expect(candidate.provenance.source_blob_hash).toBe(targetBlobHash);
        expect(candidate.provenance.target_blob_hash).toBe(targetBlobHash);

        const card = page.getByTestId(`change-item-${candidate.event_id}`);
        await expect(card).toBeVisible({ timeout: 30_000 });
        await expect(card.getByText("No material change found")).toBeVisible();
        await expect(card.getByText("No change")).toBeVisible();

        const detailResponse = page.waitForResponse(
          (response) =>
            response.request().method() === "GET" &&
            new RegExp(
              `/projects/${projectId}/documents/${documentId}/changes/${candidate.provenance?.target_revision_id}/?$`,
            ).test(new URL(response.url()).pathname),
          { timeout: 60_000 },
        );
        await card.getByRole("link", { name: /view before, after & evidence/i }).click();
        const detail = (await (await detailResponse).json()) as {
          event_id?: string;
          state?: string;
          change_cause?: string | null;
          changes?: unknown[];
          provenance?: Record<string, unknown>;
        };
        expect(detail.event_id).toBe(candidate.event_id);
        expect(detail.state).toBe("ready");
        expect(detail.change_cause).toBeNull();
        expect(detail.changes).toEqual([]);
        expect(detail.provenance?.source_revision_id).toBe(whatChanged.targetRevisionId);
        expect(detail.provenance?.target_revision_id).toBe(candidate.provenance.target_revision_id);
        expect(detail.provenance?.source_blob_hash).toBe(targetBlobHash);
        expect(detail.provenance?.target_blob_hash).toBe(targetBlobHash);
        await expect(page.getByTestId("change-detail-page")).toBeVisible({ timeout: 30_000 });
        await expect(page.getByText("No material change", { exact: false }).first()).toBeVisible();
        await expect(page.getByText("The comparison completed with no material differences.")).toBeVisible();
        writeJson(NO_CHANGE_DETAIL_OUTPUT, detail);
        return candidate;
      });

      expect(recorder.blockingFindings(), "no blocking P0c findings").toEqual([]);

      // #686 requires durable API/UI evidence after a fresh authentication
      // boundary. A full sign-out/sign-in proves more than an in-session reload.
      await recorder.step("P0C-D1", "Re-login and prove durable What Changed projection", async () => {
        const timelineCountBeforeRelogin = timelineBodies.length;
        await signOutThroughUi(page);
        await signInSyntheticProductionUser(page);

        await page.goto(`${process.env.PROD_ACCEPTANCE_BASE_URL ?? "https://c2pro.io"}/projects/${projectId}/documents`);
        await page.waitForURL(new RegExp(`/projects/${projectId}/documents`), { timeout: 30_000 });
        await expect(page.getByTestId("documents-page")).toBeVisible({ timeout: 30_000 });
        await expect(page.getByTestId(`document-row-${documentId}`)).toBeVisible({ timeout: 30_000 });

        await clickProjectTab(page, recorder, projectId, "changes", "P0C_FRESH_SESSION_CHANGES_NOT_NAVIGABLE");
        await page.waitForURL(new RegExp(`/projects/${projectId}/changes`), { timeout: 30_000 });
        await expect.poll(() => timelineBodies.length, { timeout: 30_000 }).toBeGreaterThan(timelineCountBeforeRelogin);

        const freshTimeline = timelineItems();
        const changed = freshTimeline.find((item) => item.event_id === whatChanged.changeEventId);
        const unchanged = freshTimeline.find((item) => item.event_id === noChange.event_id);
        expect(changed?.state, "A→B event must survive re-login").toBe("ready");
        expect(changed?.provenance?.source_revision_id).toBe(whatChanged.sourceRevisionId);
        expect(changed?.provenance?.target_revision_id).toBe(whatChanged.targetRevisionId);
        expect(unchanged?.state, "B→C event must survive re-login").toBe("ready");
        expect(unchanged?.change_cause).toBeNull();

        const changedCard = page.getByTestId(`change-item-${whatChanged.changeEventId}`);
        await expect(changedCard).toBeVisible({ timeout: 30_000 });
        await expect(changedCard.getByText("Project evidence changed")).toBeVisible();

        const freshDetailResponse = page.waitForResponse(
          (response) =>
            response.request().method() === "GET" &&
            new RegExp(
              `/projects/${projectId}/documents/${documentId}/changes/${whatChanged.targetRevisionId}/?$`,
            ).test(new URL(response.url()).pathname),
          { timeout: 60_000 },
        );
        await changedCard.getByRole("link", { name: /view before, after & evidence/i }).click();
        const freshDetail = (await (await freshDetailResponse).json()) as {
          event_id?: string;
          state?: string;
          provenance?: Record<string, unknown>;
        };
        expect(freshDetail.event_id).toBe(whatChanged.changeEventId);
        expect(freshDetail.state).toBe("ready");
        expect(freshDetail.provenance?.source_revision_id).toBe(whatChanged.sourceRevisionId);
        expect(freshDetail.provenance?.target_revision_id).toBe(whatChanged.targetRevisionId);
        await expect(page.getByTestId("change-detail-page")).toBeVisible({ timeout: 30_000 });
        await expect(page.getByRole("heading", { name: "Before" }).first()).toBeVisible();
        await expect(page.getByRole("heading", { name: "After" }).first()).toBeVisible();

        writeJson(FRESH_TIMELINE_OUTPUT, timelineBodies.at(-1));
        writeJson(FRESH_DETAIL_OUTPUT, freshDetail);
      });

      // Let response handlers finish serialising the API bodies captured while
      // the canonical UI evaluator was exercising the timeline/detail surfaces.
      await page.waitForTimeout(100);
      expect(timelineBodies.length, "timeline API capture").toBeGreaterThan(0);
      expect(detailBodies.length, "change-detail API capture").toBeGreaterThan(0);

      const changedDetail = detailBodies.find((body) =>
        Boolean(body && typeof body === "object" && (body as { event_id?: string }).event_id === whatChanged.changeEventId),
      );
      expect(changedDetail, "A→B change-detail API capture").toBeTruthy();
      writeJson(TIMELINE_OUTPUT, timelineBodies.at(-1));
      writeJson(DETAIL_OUTPUT, changedDetail);
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
          mode: "identical_revision_no_material_change",
          source_revision_id: whatChanged.targetRevisionId,
          target_revision_id: noChange.provenance?.target_revision_id,
          event_id: noChange.event_id,
          blob_hash: targetBlobHash,
          detail_capture: "playwright/.p0c-prod/no-change-detail.json",
        },
        fresh_session: {
          relogin_verified: true,
          timeline_capture: "playwright/.p0c-prod/fresh-session-timeline.json",
          change_detail_capture: "playwright/.p0c-prod/fresh-session-change-detail.json",
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
