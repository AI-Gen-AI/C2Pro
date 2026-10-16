import { describe, expect, it } from "vitest";
import { reviewSourceLinks } from "./review-source-links";

describe("PQ-HITL-06 structured source links", () => {
  it("produces independent A/B revision targets without duplicating entries", () => {
    const links = reviewSourceLinks("p", { source_references: [
      { document_id: "doc-a", revision_id: "rev-a", clause_id: "c-61", clause_code: "6.1" },
      { document_id: "doc-a", revision_id: "rev-a", clause_id: "c-63", clause_code: "6.3" },
      { document_id: "doc-b", revision_id: "rev-b", clause_id: "c-64", clause_code: "6.4" },
      { document_id: "doc-a", revision_id: "rev-a", clause_id: "c-61", clause_code: "6.1" },
    ] });
    expect(links).toHaveLength(3);
    expect(links[0].href).toBe("/projects/p/evidence?documentId=doc-a&revisionId=rev-a&highlightId=c-61");
    expect(links[2].href).toContain("documentId=doc-b&revisionId=rev-b&highlightId=c-64");
  });

  it("does not hallucinate clause links from text or incomplete IDs", () => {
    expect(reviewSourceLinks("p", {
      critique_notes: "§5.2 is contradictory",
      source_references: [
        { document_id: "d", clause_id: "c" },
        { document_id: "d", revision_id: "r" },
        "§5.2",
        null,
      ],
    })).toEqual([]);
  });

  it("encodes untrusted identifiers and sanitizes display-only code", () => {
    const links = reviewSourceLinks("p/../x", { source_references: [
      { document_id: "doc?x=1", revision_id: "rev&y=2", clause_id: "c#1", clause_code: "§5.2" },
    ] });
    expect(links[0].href).toBe(
      "/projects/p%2F..%2Fx/evidence?documentId=doc%3Fx%3D1&revisionId=rev%26y%3D2&highlightId=c%231",
    );
    expect(links[0].label).toBe("Inspect cited clause §5.2");
  });
});
