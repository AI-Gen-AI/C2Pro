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
        excerpt: "The contractor shall pay delay penalties.",
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

  it("treats multi-page source evidence as document fallback rather than one fake page", () => {
    const clauses = sourceEvidenceClausesFromDocumentDetail([
      {
        id: "clause-multi",
        clause_code: "9.1",
        title: "Obligation spanning pages",
        text_start_offset: 10,
        text_end_offset: 180,
        extracted_entities: {
          evidence_location: {
            page_number: null,
            page_numbers: [1, 2],
            bbox: null,
          },
        },
      },
    ]);

    expect(
      resolveEvidenceAddress({
        evidenceId: "clause-multi",
        semanticTargets: [],
        sourceClauses: clauses,
      }),
    ).toMatchObject({ kind: "document-fallback" });
  });

  it("S4 — Health clause source wins over a same-ID semantic alias", () => {
    const result = resolveEvidenceAddress({
      evidenceId: "clause-a",
      preferSourceClause: true,
      semanticTargets: [
        { id: "clause-a", type: "ALERT", label: "Unrelated alert alias" },
      ],
      sourceClauses: [
        {
          id: "clause-a",
          clauseCode: "5.2",
          label: "Contract penalties",
          excerpt: "Delay penalties begin seven days after the milestone.",
          page: 3,
          startOffset: null,
          endOffset: null,
        },
      ],
    });
    expect(result).toMatchObject({
      kind: "raw-clause",
      target: {
        id: "clause-a",
        clauseCode: "5.2",
        excerpt: "Delay penalties begin seven days after the milestone.",
      },
    });
  });

  it("S4 — Health never resolves to an unrelated semantic target without the actual source clause", () => {
    expect(resolveEvidenceAddress({
      evidenceId: "clause-a",
      preferSourceClause: true,
      semanticTargets: [
        { id: "clause-a", type: "CLAUSE", label: "Current semantic alias" },
      ],
      sourceClauses: [],
    })).toEqual({ kind: "unresolved" });
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

describe("PQ-HITL-06 pinned source revision", () => {
  const sources = sourceEvidenceClausesFromDocumentDetail([
    {
      id: "clause-52", clause_code: "5.2", revision_id: "rev-b",
      text_start_offset: 10, text_end_offset: 40,
      extracted_entities: { evidence_location: { page_number: 3 } },
    },
  ]);
  const base = {
    evidenceId: "clause-52",
    semanticTargets: [{ id: "clause-52", type: "CLAUSE" as const, label: "Current semantic view" }],
    sourceClauses: sources,
  };

  it("rejects a stale A revision even when semantic/current clauses collide", () => {
    expect(resolveEvidenceAddress({
      ...base, revisionId: "rev-a", documentRevisionId: "rev-b",
    })).toEqual({ kind: "unresolved" });
    expect(resolveEvidenceAddress({
      ...base, revisionId: "rev-a", documentRevisionId: "rev-a",
    })).toEqual({ kind: "unresolved" });
  });

  it("requires an immutable PDF revision and matching source clause", () => {
    expect(resolveEvidenceAddress({
      ...base, revisionId: "rev-b", documentRevisionId: "rev-b",
    })).toMatchObject({
      kind: "raw-clause", targetType: "DOCUMENT_SPAN",
      target: { id: "clause-52", revisionId: "rev-b", page: 3 },
    });
    expect(resolveEvidenceAddress({
      ...base, revisionId: "rev-b", documentRevisionId: null,
    })).toEqual({ kind: "unresolved" });
  });

  it("does not silently infer revision for a clause missing metadata", () => {
    expect(resolveEvidenceAddress({
      evidenceId: "unversioned", semanticTargets: [],
      sourceClauses: [{
        id: "unversioned", clauseCode: "1.3", label: "Missing revision",
        page: 2, startOffset: 0, endOffset: 20,
      }],
      revisionId: "rev-b", documentRevisionId: "rev-b",
    })).toEqual({ kind: "unresolved" });
  });
});
