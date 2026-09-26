/**
 * F-DOC-1: the cross-project documents list labels lifecycle honestly —
 * "Analyzed" only for documents whose analysis completed.
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@/src/tests/test-utils";
import type { ProjectDocumentsGroup } from "@/lib/api/contracts";
import { DocumentsListClient } from "./DocumentsListClient";

function doc(id: string, status: string, lifecycle_status?: string) {
  return {
    id,
    project_id: "proj-1",
    filename: `${id}.pdf`,
    document_type: "contract",
    status,
    status_detail: "",
    lifecycle_status,
    uploaded_at: "2026-03-18T09:00:00Z",
    file_size_bytes: 10,
  };
}

const groups = [
  {
    projectId: "proj-1",
    projectName: "Harbour",
    documents: [
      doc("parsed-doc", "parsed", "parsed"),
      doc("pending-doc", "processing", "analysis_pending"),
      doc("analyzed-doc", "parsed", "analyzed"),
      doc("legacy-doc", "parsed"),
    ],
  },
] as unknown as ProjectDocumentsGroup[];

describe("DocumentsListClient", () => {
  it("never labels parsed or analysis-pending documents as analyzed", () => {
    render(<DocumentsListClient groups={groups} />);

    const row = (filename: string) => screen.getByText(filename).closest("tr");
    expect(row("parsed-doc.pdf")).toHaveTextContent("Parsed");
    expect(row("parsed-doc.pdf")).not.toHaveTextContent("Analyzed");
    expect(row("pending-doc.pdf")).toHaveTextContent("Analysis pending");
    expect(row("analyzed-doc.pdf")).toHaveTextContent("Analyzed");
    expect(row("legacy-doc.pdf")).toHaveTextContent("Parsed");
    expect(row("legacy-doc.pdf")).not.toHaveTextContent("Analyzed");
    expect(screen.getByLabelText("Analyzed documents")).toHaveTextContent("1");
  });
});
