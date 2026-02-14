import { describe, expect, it } from "vitest";

describe("S2-02 custom MSW handlers", () => {
  it("returns the seeded projects list", async () => {
    const response = await fetch("/api/v1/projects");
    const data = await response.json();

    expect(response.ok).toBe(true);
    expect(data).toHaveLength(2);
    expect(data[0].id).toBe("proj_demo_001");
  });

  it("returns project details by id", async () => {
    const response = await fetch("/api/v1/projects/proj_demo_001");
    const data = await response.json();

    expect(response.ok).toBe(true);
    expect(data.id).toBe("proj_demo_001");
    expect(data.name).toBe("Torre Skyline");
  });

  it("returns project documents, alerts, and stakeholders", async () => {
    const [documents, alerts, stakeholders] = await Promise.all([
      fetch("/api/v1/projects/proj_demo_001/documents").then((r) => r.json()),
      fetch("/api/v1/projects/proj_demo_001/alerts").then((r) => r.json()),
      fetch("/api/v1/projects/proj_demo_001/stakeholders").then((r) => r.json()),
    ]);

    expect(documents).toHaveLength(1);
    expect(alerts).toHaveLength(2);
    expect(stakeholders).toHaveLength(2);
  });

  it("returns clauses for a document", async () => {
    const response = await fetch("/api/v1/documents/doc_demo_001/clauses");
    const data = await response.json();

    expect(response.ok).toBe(true);
    expect(data).toHaveLength(2);
  });
});
