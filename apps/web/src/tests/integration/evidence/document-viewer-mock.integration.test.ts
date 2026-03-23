import { describe, expect, it } from "vitest";

describe("document viewer mock handlers", () => {
  it("serves a synthetic PDF blob in node-based test coverage", async () => {
    const response = await fetch("/api/v1/documents/doc_demo_001/download");

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("application/pdf");
    expect(await response.text()).toContain("%PDF-1.4");
  });

  it("serves synthetic extracted entities in node-based test coverage", async () => {
    const response = await fetch("/api/v1/documents/doc_demo_001/entities");

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          type: "clause",
          page: 1,
        }),
      ]),
    );
  });
});
