/**
 * PJ-01 step 3: upload a contract through the real upload surface.
 *
 * Proves acceptance before any processing wait: the upload POST must succeed, return the
 * document id and an enqueued task id, and the dialog must close (it closes only after
 * `uploadDocument` resolved). A null task id means the processing task was never enqueued,
 * which would otherwise surface minutes later as an unexplained stuck document.
 */
import path from "node:path";

import { expect, type Page, type Response } from "@playwright/test";

import type { Pj01RunRecorder } from "./run-recorder";

export interface UploadResult {
  documentId: string;
  taskId: string | null;
  httpStatus: number;
}

export async function uploadDocumentThroughUi(
  page: Page,
  recorder: Pj01RunRecorder,
  options: { projectId: string; filePath: string; documentType?: string },
): Promise<UploadResult> {
  const { projectId, filePath } = options;
  const documentType = options.documentType ?? "contract";
  const fileName = path.basename(filePath);

  await page.getByRole("button", { name: /upload document/i }).click();
  const surface = page.getByTestId("document-upload-surface");
  await expect(surface).toBeVisible({ timeout: 15_000 });
  await page.setInputFiles('input[type="file"]', filePath);

  // The staged file's type is a Select trigger (shadcn): confirm the type the user sees and
  // change it through the visible options only when the default is not the wanted type.
  const typeControl = page.getByLabel(`Document type for ${fileName}`);
  await expect(typeControl, "the staged file must expose its document type").toBeVisible({ timeout: 15_000 });
  const wanted = new RegExp(`^\\s*${documentType}\\s*$`, "i");
  if (!wanted.test(await typeControl.innerText())) {
    await typeControl.click();
    await page.getByRole("option", { name: wanted }).click();
  }
  await expect(typeControl).toHaveText(wanted);

  type UploadBody = { id?: string; document_id?: string; task_id?: string | null };
  const isUpload = (response: Response): boolean =>
    response.request().method() === "POST" &&
    new RegExp(`/projects/${projectId}/documents/?$`).test(new URL(response.url()).pathname);
  // The page navigates as soon as the upload is accepted, and the browser then drops the response
  // body (CDP "No resource with given identifier"). Ask for the body the moment the response
  // arrives, before any navigation can happen, instead of after waiting for it.
  const received = new Promise<{ status: number; ok: boolean; body: Promise<UploadBody | null> }>((resolve) => {
    const onResponse = (response: Response): void => {
      if (!isUpload(response)) return;
      page.off("response", onResponse);
      resolve({
        status: response.status(),
        ok: response.ok(),
        body: response.json().then(
          (parsed) => parsed as UploadBody,
          () => null,
        ),
      });
    };
    page.on("response", onResponse);
  });
  await page.getByRole("button", { name: /^upload 1 file$/i }).click();
  const accepted = await Promise.race([
    received,
    new Promise<never>((_resolve, reject) =>
      setTimeout(() => reject(new Error(`PJ01_UPLOAD_NO_RESPONSE: no answer to the upload of ${fileName}`)), 120_000),
    ),
  ]);
  if (!accepted.ok) {
    throw new Error(`PJ01_UPLOAD_REJECTED: HTTP ${accepted.status} for ${fileName}`);
  }
  const body = await accepted.body;
  if (!body) throw new Error("PJ01_UPLOAD_BODY_UNREADABLE: the accepted upload response could not be read");
  const documentId = body.id ?? body.document_id;
  if (!documentId) throw new Error("PJ01_UPLOAD_NO_DOCUMENT_ID: the upload response carried no document id");

  try {
    await expect(surface).toBeHidden({ timeout: 60_000 });
  } catch {
    const reason = await surface.innerText().catch(() => "(surface unavailable)");
    throw new Error(`PJ01_UPLOAD_NOT_ACCEPTED: the upload dialog stayed open:\n${reason}`);
  }

  const taskId = body.task_id ?? null;
  if (!taskId) {
    recorder.violation(
      "UPLOAD_NOT_ENQUEUED",
      "upload accepted but task_id is null: processing was never enqueued and the user is not told",
    );
  }
  recorder.record("documentId", documentId);
  recorder.record("uploadTaskEnqueued", Boolean(taskId));
  return { documentId, taskId, httpStatus: accepted.status };
}
