/**
 * PJ-01 step G: upload revision B of the SAME document through the browser.
 *
 * The Documents row's "Upload new version" action sends the file to the document's revision
 * endpoint (PATCH /documents/{id}/file). The run proves the response is the same logical
 * document and that the project still lists exactly one document afterwards — a second
 * upload through "Upload Document" would be a different, unrelated document.
 */
import path from "node:path";

import { expect, type Page, type Response } from "@playwright/test";

import { clickProjectTab } from "./health";
import type { Pj01RunRecorder } from "./run-recorder";

export interface RevisionUploadResult {
  documentId: string;
  version: number | null;
  documentsListed: number;
}

export async function uploadNewVersionThroughUi(
  page: Page,
  recorder: Pj01RunRecorder,
  options: { projectId: string; documentId: string; filePath: string },
): Promise<RevisionUploadResult> {
  const { projectId, documentId, filePath } = options;

  await clickProjectTab(page, recorder, projectId, "documents", "DOCUMENTS_TAB_NOT_NAVIGABLE");
  await page.waitForURL(new RegExp(`/projects/${projectId}/documents`), { timeout: 30_000 });
  const row = page.getByTestId(`document-row-${documentId}`);
  await expect(row).toBeVisible({ timeout: 30_000 });

  const newVersion = row.getByRole("button", { name: /^upload new version of /i });
  if ((await newVersion.count()) === 0) {
    recorder.gapOrStop("G1_REVISION_UPLOAD_NOT_NAVIGABLE", "the document row offers no new-version upload");
  }
  await newVersion.click();

  const dialog = page.getByTestId("document-new-version-dialog");
  await expect(dialog).toBeVisible({ timeout: 15_000 });
  await dialog.getByLabel(/new version file/i).setInputFiles(filePath);

  const accepted = page.waitForResponse(
    (response: Response) =>
      response.request().method() === "PATCH" &&
      new RegExp(`/documents/${documentId}/file/?$`).test(new URL(response.url()).pathname),
    { timeout: 120_000 },
  );
  await dialog.getByRole("button", { name: /^upload new version$/i }).click();
  const response = await accepted;
  if (!response.ok()) {
    throw new Error(`PJ01_REVISION_UPLOAD_REJECTED: HTTP ${response.status()} for ${path.basename(filePath)}`);
  }
  const body = (await response.json()) as { id?: string; version?: number };
  if (body.id !== documentId) {
    recorder.violation("REVISION_CREATED_A_NEW_DOCUMENT", `new version response id ${body.id} != ${documentId}`);
  }
  await expect(dialog).toBeHidden({ timeout: 60_000 });

  const listed = await page.waitForResponse(
    (candidate: Response) =>
      candidate.request().method() === "GET" &&
      candidate.ok() &&
      new RegExp(`/projects/${projectId}/documents/?$`).test(new URL(candidate.url()).pathname),
    { timeout: 60_000 },
  );
  const items = ((await listed.json()) as { items?: { id: string }[] }).items ?? [];
  if (items.length !== 1) {
    recorder.violation("DOCUMENT_DUPLICATED", `the project lists ${items.length} documents after a new version`);
  }

  recorder.record("revisionUpload", { documentId: body.id, version: body.version ?? null, documentsListed: items.length });
  return { documentId: body.id ?? documentId, version: body.version ?? null, documentsListed: items.length };
}
