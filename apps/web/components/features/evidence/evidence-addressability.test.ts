import { describe, expect, it } from "vitest";
import {
  resolveEvidenceAddress,
  sourceEvidenceClausesFromDocumentDetail,
} from "./evidence-addressability";

describe("evidence addressability", () => {
  it("prefers an existing semantic target over a same-id source clause", () => {
    const resolution = resolveEvidenceAddress({
      evidenceId: "target-1",
      semanticTargets: [
        { id: "target-1", label: "Responsible party", type: "STAKEHOLDER" },
      ],
      sourceClauses: [
        {
          id: "target-1",
          clauseCode: "2.4",
          label: "Source clause",
          page: 2,
          startOffset: 10,
          endOffset: 24,
        },
      ],
    });

    expect(resolution).toEqual({
      kind: "semantic",
      target: { id: "target-1", label: "Responsible party", type: "STAKEHOLDER" },
    });
  });

  it("resolves an authoritative source clause with a page and offsets as a document span", () => {
    const clauses = sourceEvidenceClausesFromDocumentDetail([
      {
        id: "clause-7-1",
        clause_code: "7.1",
        title: "Delay penalties",
        full_text: "The contractor shall pay delay penalties.",
        text_start_offset: 120,
        text_end_offset: 164,
        extracted_entities: { evidence_location: { page_number: 4 } },
      },
    ]);

    expect(
      resolveEvidenceAddress({
        evidenceId: "clause-7-1",
        semanticTargets: [],
        sourceClauses: clauses,
      }),
    ).toEqual({
      kind: "raw-clause",
      targetType: "DOCUMENT_SPAN",
      target: {
        id: "clause-7-1",
        clauseCode: "7.1",
        label: "Delay penalties",
        page: 4,
        startOffset: 120,
        endOffset: 164,
      },
    });
  });

  it("falls back to the source document when the known clause has no page span", () => {
    const resolution = resolveEvidenceAddress({
      evidenceId: "clause-8-2",
      semanticTargets: [],
      sourceClauses: [
        {
          id: "clause-8-2",
          clauseCode: "8.2",
          label: "Source context is available",
          page: null,
          startOffset: null,
          endOffset: null,
        },
      ],
    });

    expect(resolution.kind).toBe("document-fallback");
  });

  it("returns an explicit unresolved state for an unknown evidence id", () => {
    expect(
      resolveEvidenceAddress({
        evidenceId: "missing",
        semanticTargets: [],
        sourceClauses: [],
      }),
    ).toEqual({ kind: "unresolved" });
  });
});
