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

    expect(readRevisionClauses).toHaveBeenCalledWith(
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

  it("S6 — compares authoritative A against proposed B as separate read-only clause sources", () => {
    listRevisions.mockReturnValue({
      data: [
        {
          revision_id: "revision-A",
          rev_no: 1,
          status: "available",
          trust_state: "trusted",
          is_current: true,
          current_basis: "trusted",
        },
        {
          revision_id: "revision-B",
          rev_no: 2,
          status: "available",
          trust_state: "proposed",
          is_current: false,
          current_basis: "trusted",
        },
      ],
      isLoading: false,
      isError: false,
    });
    render(<EvidenceRevisionHistoryPanel documentId="doc-1" projectId="proj-123" />);
    expect(screen.getByRole("button", { name: /Revision 1 — Trusted current/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Revision 2/i }));

    const warning = screen.getByTestId("revision-proposal-warning");
    expect(warning).toHaveTextContent(/proposed and is not authorized/i);
    expect(warning).toHaveTextContent(/approved revision 1 remains trusted current/i);
    const compare = screen.getByTestId("revision-a-b-comparison");
    expect(compare).toHaveTextContent(//read-only extracted clause labels; not a source-text verification or a computed change diff/i/i);

    const baseline = screen.getByTestId("revision-approved-baseline");
    expect(baseline).toHaveTextContent("9 stored extracted clauses");
    // A and B show only the first three verified source rows, not inferred matches.
    expect(baseline).toHaveTextContent("A Clause 1: obligation");
    const proposed = screen.getByTestId("revision-proposed-source");
    expect(proposed).toHaveTextContent("7 stored extracted clauses");
    expect(proposed).toHaveTextContent("B Clause 1: obligation");
    expect(baseline).not.toHaveTextContent("B Clause 1: obligation");
    expect(proposed).not.toHaveTextContent("A Clause 1: obligation");
    expect(readRevisionClauses).toHaveBeenCalledWith(
      "doc-1",
      { revision_id: "revision-A" },
      { query: { enabled: true } },
    );
    expect(readRevisionClauses).toHaveBeenCalledWith(
      "doc-1",
      { revision_id: "revision-B" },
      { query: { enabled: true } },
    );
    expect(screen.getByRole("link", { name: /View recorded comparisons in What Changed/i }))
      .toHaveAttribute("href", "/projects/proj-123/changes");

    fireEvent.click(screen.getByRole("button", { name: /Revision 1/i }));
    expect(screen.queryByTestId("revision-a-b-comparison")).not.toBeInTheDocument();
    expect(screen.queryByTestId("revision-proposal-warning")).not.toBeInTheDocument();
  });

  it("S6 — never assumes a trusted A from an unresolved or lone revision when B is proposed", () => {
    listRevisions.mockReturnValue({
      data: [
        {
          revision_id: "revision-A",
          rev_no: 1,
          status: "available",
          trust_state: "trusted",
          is_current: true,
          current_basis: "single_revision",
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
    render(<EvidenceRevisionHistoryPanel documentId="doc-1" projectId="proj-123" />);
    fireEvent.click(screen.getByRole("button", { name: /Revision 2/i }));
    expect(screen.getByTestId("revision-proposal-warning")).toHaveTextContent(
      /No trusted current revision can be verified/i,
    );
    expect(screen.queryByTestId("revision-a-b-comparison")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Trusted current/i })).not.toBeInTheDocument();
  });

  it("S6 — after a verified approval B becomes trusted current and A becomes history", () => {
    listRevisions.mockReturnValue({
      data: [
        {
          revision_id: "revision-A",
          rev_no: 1,
          status: "available",
          trust_state: "trusted",
          is_current: false,
          current_basis: "trusted",
        },
        {
          revision_id: "revision-B",
          rev_no: 2,
          status: "available",
          trust_state: "trusted",
          is_current: true,
          current_basis: "trusted",
        },
      ],
      isLoading: false,
      isError: false,
    });
    render(<EvidenceRevisionHistoryPanel documentId="doc-1" projectId="proj-123" />);
    expect(screen.getByRole("button", { name: /Revision 2 — Trusted current/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Revision 1 — Trusted artifact — not current/i }))
      .toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Revision 2/i }));
    expect(screen.queryByTestId("revision-a-b-comparison")).not.toBeInTheDocument();
    expect(screen.queryByTestId("revision-proposal-warning")).not.toBeInTheDocument();
    expect(screen.getByText(/7 stored clauses in this selected revision/i)).toBeInTheDocument();
  });

  it("S6 — a rejected B remains historical and cannot displace approved A", () => {
    listRevisions.mockReturnValue({
      data: [
        {
          revision_id: "revision-A",
          rev_no: 1,
          status: "available",
          trust_state: "trusted",
          is_current: true,
          current_basis: "trusted",
        },
        {
          revision_id: "revision-B",
          rev_no: 2,
          status: "available",
          trust_state: "rejected",
          is_current: false,
          current_basis: "trusted",
        },
      ],
      isLoading: false,
      isError: false,
    });
    render(<EvidenceRevisionHistoryPanel documentId="doc-1" projectId="proj-123" />);
    expect(screen.getByRole("button", { name: /Revision 1 — Trusted current/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Revision 2 — Rejected — historical/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Revision 2/i }));
    expect(screen.getByText(/7 stored clauses in this selected revision/i)).toBeInTheDocument();
    expect(screen.queryByTestId("revision-a-b-comparison")).not.toBeInTheDocument();
    expect(screen.queryByTestId("revision-proposal-warning")).not.toBeInTheDocument();
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
