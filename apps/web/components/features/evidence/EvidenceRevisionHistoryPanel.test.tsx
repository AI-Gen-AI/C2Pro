import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { EvidenceRevisionHistoryPanel } from "./EvidenceRevisionHistoryPanel";

const listRevisions = vi.fn();
const readRevisionClauses = vi.fn();

vi.mock("@/lib/api/generated/documents/documents", () => ({
  useListDocumentRevisionStatusesEndpointApiV1DocumentsDocumentIdRevisionsGet:
    (...args: unknown[]) => listRevisions(...args),
  useGetDocumentEntitiesEndpointApiV1DocumentsDocumentIdEntitiesGet:
    (...args: unknown[]) => readRevisionClauses(...args),
}));

describe("EvidenceRevisionHistoryPanel — read-only revision truth", () => {
  beforeEach(() => {
    listRevisions.mockReset();
    readRevisionClauses.mockReset();
    listRevisions.mockReturnValue({
      data: [
        {
          revision_id: "revision-A",
          rev_no: 1,
          status: "available",
          trust_state: "trusted",
          is_current: false,
          current_basis: "unresolved",
        },
        {
          revision_id: "revision-B",
          rev_no: 2,
          status: "available",
          trust_state: "proposed",
          is_current: false,
          current_basis: "unresolved",
        },
      ],
      isLoading: false,
      isError: false,
    });
    readRevisionClauses.mockImplementation(
      (_documentId: string, params: { revision_id: string | null }) => {
        const isRevisionA = params.revision_id === "revision-A";
        const prefix = isRevisionA ? "A" : "B";
        return {
          data: Array.from({ length: isRevisionA ? 9 : 7 }, (_, index) => ({
            id: `${prefix}-clause-${index + 1}`,
            type: "clause",
            text: `${prefix} Clause ${index + 1}: obligation`,
          })),
          isLoading: false,
          isError: false,
        };
      },
    );
  });

  it("shows proposed/historical separately and previews exactly selected revision without changing trust", () => {
    render(<EvidenceRevisionHistoryPanel documentId="doc-1" />);

    expect(screen.getByText(/No trusted-current revision is available/i)).toBeInTheDocument();
    expect(screen.getByText(/Proposed — not trusted/i)).toBeInTheDocument();
    expect(screen.queryByText(/No clauses extracted/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Revision 2/i }));

    expect(readRevisionClauses).toHaveBeenLastCalledWith(
      "doc-1",
      { revision_id: "revision-B" },
      { query: { enabled: true } },
    );
    expect(screen.getByText(/7 stored clauses in this selected revision/i)).toBeInTheDocument();
    expect(screen.getByText("B Clause 1: obligation")).toBeInTheDocument();
    expect(screen.getByText(/Read-only historical\/proposed preview/i)).toBeInTheDocument();
  });

  it("switches A=9 and B=7 without displaying clauses from a different revision", () => {
    render(<EvidenceRevisionHistoryPanel documentId="doc-1" />);

    fireEvent.click(screen.getByRole("button", { name: /Revision 1/i }));
    expect(screen.getByText(/9 stored clauses in this selected revision/i)).toBeInTheDocument();
    expect(screen.getByText("A Clause 9: obligation")).toBeInTheDocument();
    expect(screen.queryByText("B Clause 7: obligation")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Revision 2/i }));
    expect(screen.getByText(/7 stored clauses in this selected revision/i)).toBeInTheDocument();
    expect(screen.getByText("B Clause 7: obligation")).toBeInTheDocument();
    expect(screen.queryByText("A Clause 9: obligation")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Revision 1/i }));
    expect(screen.getByText(/9 stored clauses in this selected revision/i)).toBeInTheDocument();
    expect(screen.getByText("A Clause 9: obligation")).toBeInTheDocument();
    expect(screen.queryByText("B Clause 7: obligation")).not.toBeInTheDocument();
  });

  it("never labels a revision trusted-current when its current authority is unresolved", () => {
    listRevisions.mockReturnValue({
      data: [
        {
          revision_id: "revision-A",
          rev_no: 1,
          status: "available",
          trust_state: "trusted",
          is_current: true,
          current_basis: "unresolved",
        },
        {
          revision_id: "revision-B",
          rev_no: 2,
          status: "available",
          trust_state: "proposed",
          is_current: false,
          current_basis: "unresolved",
        },
      ],
      isLoading: false,
      isError: false,
    });

    render(<EvidenceRevisionHistoryPanel documentId="doc-1" />);
    expect(screen.getByText(/No trusted-current revision is available/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Trusted current/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /current authority unresolved/i })).toBeInTheDocument();
  });

  it("never reports zero extraction when no trusted-current projection is resolvable", () => {
    listRevisions.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });

    render(<EvidenceRevisionHistoryPanel documentId="doc-1" />);
    expect(screen.getByText(/No revision history is available for this document/i)).toBeInTheDocument();
    expect(screen.queryByText(/0 clauses extracted/i)).not.toBeInTheDocument();
  });

  it("shows a load failure instead of an empty-evidence claim", () => {
    listRevisions.mockReturnValue({ data: undefined, isLoading: false, isError: true });
    render(<EvidenceRevisionHistoryPanel documentId="doc-1" />);
    expect(screen.getByText(/Revision history could not be loaded/i)).toBeInTheDocument();
  });
});
