/**
 * Test Suite ID: S2-09
 * Roadmap Reference: S2-09 Document upload (drag-drop, PDF/XLSX/BC3, chunked)
 */
import { describe, expect, it } from "vitest";

describe("S2-09 RED - chunk upload integration", () => {
  it("[S2-09-RED-05] sends required upload metadata contract on each chunk", async () => {
    /** Roadmap: S2-09 */
    const response = await fetch("/api/v1/projects/proj_demo_001/uploads/chunks", {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({
        fileId: "file_demo_001",
        fileName: "contract.pdf",
        mimeType: "application/pdf",
        chunkIndex: 0,
        totalChunks: 3,
        payloadBase64: "AAECAw==",
      }),
    });

    expect(response.status).toBe(202);
    expect(await response.json()).toMatchObject({
      fileId: "file_demo_001",
      chunkIndex: 0,
      accepted: true,
    });
  });

  it("[S2-09-RED-06] retries only failed chunk and then completes upload", async () => {
    /** Roadmap: S2-09 */
    const startResponse = await fetch(
      "/api/v1/projects/proj_demo_001/uploads/start",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          fileName: "schedule.xlsx",
          fileSizeBytes: 6_000_000,
          mimeType:
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }),
      },
    );

    expect(startResponse.status).toBe(201);

    const finalizeResponse = await fetch(
      "/api/v1/projects/proj_demo_001/uploads/finalize",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          fileId: "file_demo_retry_001",
          uploadedChunks: [0, 1],
          retriedChunks: [1],
        }),
      },
    );

    expect(finalizeResponse.status).toBe(200);
    expect(await finalizeResponse.json()).toMatchObject({
      fileId: "file_demo_retry_001",
      uploadStatus: "completed",
      retriedChunks: [1],
    });
  });
});

