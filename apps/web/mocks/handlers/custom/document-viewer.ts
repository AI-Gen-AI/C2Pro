import { http, HttpResponse } from "@/mocks/msw";
import { db } from "../../data";

/**
 * Minimal blank-page PDF (valid PDF 1.4, single empty page).
 * Used so the Evidence Viewer can render something in demo mode.
 */
const BLANK_PDF = [
  "%PDF-1.4",
  "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj",
  "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj",
  "3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj",
  "xref",
  "0 4",
  "0000000000 65535 f ",
  "0000000009 00000 n ",
  "0000000058 00000 n ",
  "0000000115 00000 n ",
  "trailer<</Size 4/Root 1 0 R>>",
  "startxref",
  "206",
  "%%EOF",
].join("\n");

export const documentViewerHandlers = [
  // ── Document download (PDF blob) ────────────────────────
  http.get("/api/v1/documents/:documentId/download", ({ params }) => {
    const doc = db.document.findFirst({
      where: { id: { equals: String(params.documentId) } },
    });

    if (!doc) {
      return new HttpResponse(null, { status: 404 });
    }

    return new HttpResponse(BLANK_PDF, {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": `inline; filename="${doc.filename}"`,
      },
    });
  }),

  // ── Document entities ───────────────────────────────────
  http.get("/api/v1/documents/:documentId/entities", ({ params }) => {
    const documentId = String(params.documentId);
    const doc = db.document.findFirst({
      where: { id: { equals: documentId } },
    });

    if (!doc) {
      return new HttpResponse(null, { status: 404 });
    }

    // Return demo entities for documents that have "parsed" status
    if (doc.status !== "parsed") {
      return HttpResponse.json([]);
    }

    // Generate a few representative entities per document
    const clauses = db.clause.findMany({
      where: { documentId: { equals: documentId } },
    });

    const entities = clauses.map((clause, idx) => ({
      id: `entity_${documentId}_${idx}`,
      type: "clause" as const,
      text: clause.text,
      page: 1,
      confidence: 0.92 - idx * 0.05,
      metadata: { clauseType: clause.clauseType },
    }));

    return HttpResponse.json(entities);
  }),
];
