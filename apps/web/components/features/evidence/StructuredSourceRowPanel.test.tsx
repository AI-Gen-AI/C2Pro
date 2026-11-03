/** S4: the original row is shown only after the API verified it; every refusal shows no content. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StructuredSourceRowPanel } from "./StructuredSourceRowPanel";

const { query, auth } = vi.hoisted(() => ({
  query: vi.fn(),
  auth: { orgId: "o", userId: "u", isLoaded: true },
}));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth }));
vi.mock("@tanstack/react-query", () => ({ useQuery: (args: unknown) => query(args) }));
vi.mock("@/lib/api/client", () => ({ orvalApiClient: vi.fn() }));

const row = {
  family: "budget",
  document_id: "d",
  revision_id: "rev-1",
  rev_no: 2,
  source_locator: "Presupuesto!3",
  blob_sha256: "a".repeat(64),
  authority: "TRUSTED_CURRENT",
  row: { source_locator: "Presupuesto!3", kind: "declared_total", item: "Total presupuesto", total: 1500000, currency: null },
  source_assessment: "NOT_ASSESSED",
};

const state = (over: object) =>
  query.mockReturnValue({ isLoading: false, isError: false, isSuccess: false, data: undefined, error: null, ...over });

describe("StructuredSourceRowPanel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the verified row with revision, SHA-256 and authority, and asks the API for exactly that reference", () => {
    state({ isSuccess: true, data: row });
    render(<StructuredSourceRowPanel documentId="d" revisionId="rev-1" locator="Presupuesto!3" expectedBlobHash={"a".repeat(64)} />);
    expect(screen.getByTestId("structured-source-family")).toHaveTextContent("Budget row · revision 2");
    expect(screen.getByTestId("structured-source-sha")).toHaveTextContent("a".repeat(64));
    expect(screen.getByTestId("structured-source-authority")).toHaveTextContent("trusted by a human and current");
    const cells = screen.getByTestId("structured-source-cells");
    expect(cells).toHaveTextContent("Total presupuesto");
    expect(cells).toHaveTextContent("1500000");
    expect(cells).toHaveTextContent("—"); // a null cell is a dash, never "0" or a guess
    expect(query.mock.calls[0][0].enabled).toBe(true);
  });

  it("says plainly when the source is not explicitly trusted", () => {
    state({ isSuccess: true, data: { ...row, authority: "UNTRUSTED_SINGLE_REVISION" } });
    render(<StructuredSourceRowPanel documentId="d" revisionId="rev-1" locator="Presupuesto!3" />);
    expect(screen.getByTestId("structured-source-authority")).toHaveTextContent("NOT explicitly trusted");
  });

  it.each([
    [{ response: { status: 409, data: { detail: { code: "stale_reference" } } }, isAxiosError: true }, /stale/i],
    [{ response: { status: 409, data: { detail: { code: "source_unavailable" } } }, isAxiosError: true }, /cannot be verified/i],
    [{ response: { status: 404, data: {} }, isAxiosError: true }, /no such source/i],
    [new Error("boom"), /could not be verified/i],
  ])("refuses without content: %#", (error, message) => {
    state({ isError: true, error });
    render(<StructuredSourceRowPanel documentId="d" revisionId="rev-1" locator="Presupuesto!3" />);
    expect(screen.getByTestId("structured-source-refused")).toHaveTextContent(message);
    expect(screen.queryByTestId("structured-source-cells")).not.toBeInTheDocument();
  });

  it("does not query before the session is loaded", () => {
    auth.userId = "";
    state({ isLoading: true });
    render(<StructuredSourceRowPanel documentId="d" revisionId="rev-1" locator="Presupuesto!3" />);
    expect(query.mock.calls[0][0].enabled).toBe(false);
    auth.userId = "u";
  });
});
