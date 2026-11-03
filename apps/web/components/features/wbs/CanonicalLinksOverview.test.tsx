/** S7: three source families, each CURRENT only on the approved baseline. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { CanonicalLinksOverview } from "./CanonicalLinksOverview";
import type { ProjectWBSAuthority } from "@/lib/api/generated/models";

const { query, auth } = vi.hoisted(() => ({ query: vi.fn(), auth: { orgId: "o", userId: "u", isLoaded: true } }));
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth }));
vi.mock("@tanstack/react-query", () => ({ useQuery: (args: { queryKey: string[] }) => query(args) }));
vi.mock("@/lib/api/client", () => ({ orvalApiClient: vi.fn() }));

const authority = { approved: true, baseline_id: "base-1" } as unknown as ProjectWBSAuthority;
const ok = (data: object[]) => ({ data, isSuccess: true, isError: false });
const structured = (family: string, over: object = {}) => ({ family, state: "CURRENT", wbs_baseline_id: "base-1", ...over });
const technical = (over: object = {}) => ({ state: "CURRENT", wbs_baseline_id: "base-1", ...over });

function mock(structuredResult: object, technicalResult: object) {
  query.mockImplementation(({ queryKey }: { queryKey: string[] }) =>
    queryKey[0] === "structured-wbs-canonical-links" ? structuredResult : technicalResult,
  );
}

describe("CanonicalLinksOverview", () => {
  beforeEach(() => vi.clearAllMocks());

  it("counts the three families CURRENT on the approved baseline", () => {
    mock(ok([structured("budget"), structured("schedule")]), ok([technical()]));
    render(<CanonicalLinksOverview projectId="p" authority={authority} />);
    expect(screen.getByTestId("s7-links-overview-count")).toHaveTextContent("3 of 3");
    for (const family of ["budget", "schedule", "technical"]) {
      expect(screen.getByTestId(`s7-overview-${family}`)).toHaveTextContent("CURRENT");
    }
  });

  it("does not count a stale link or a link on another baseline, and names the missing family", () => {
    mock(ok([structured("budget", { state: "STALE_SOURCE" }), structured("schedule", { wbs_baseline_id: "old" })]), ok([technical()]));
    render(<CanonicalLinksOverview projectId="p" authority={authority} />);
    expect(screen.getByTestId("s7-links-overview-count")).toHaveTextContent("1 of 3");
    expect(screen.getByTestId("s7-overview-budget")).toHaveTextContent("no current approved link");
    expect(screen.getByTestId("s7-overview-schedule")).toHaveTextContent("no current approved link");
  });

  it("counts nothing without an approved baseline", () => {
    mock(ok([structured("budget")]), ok([technical()]));
    render(<CanonicalLinksOverview projectId="p" authority={{ approved: false } as ProjectWBSAuthority} />);
    expect(screen.getByTestId("s7-links-overview-count")).toHaveTextContent("0 of 3");
  });

  it("claims nothing while verifying or when either source of links failed", () => {
    mock({ data: undefined, isSuccess: false, isError: false }, ok([]));
    const { unmount } = render(<CanonicalLinksOverview projectId="p" authority={authority} />);
    expect(screen.getByText(/Verifying canonical links/)).toBeInTheDocument();
    unmount();
    mock(ok([structured("budget")]), { data: undefined, isSuccess: false, isError: true });
    render(<CanonicalLinksOverview projectId="p" authority={authority} />);
    expect(screen.getByTestId("s7-links-overview-error")).toHaveTextContent("No current links are claimed");
    expect(screen.queryByTestId("s7-links-overview-count")).not.toBeInTheDocument();
  });
});
