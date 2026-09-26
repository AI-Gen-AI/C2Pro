/**
 * Test Suite ID: TS-P0D-REPORT-UI-003
 * Report page: Current state is the default mode; the Audit export stays available
 * and either mode can be opened directly through `?mode=`. The URL is the single
 * source of truth for the selected mode.
 * Audit composition coverage (TASK-FRT-188) lives in AuditReportMode.test.tsx.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import ProjectReportPage from "./page";

const PATHNAME = "/projects/proj-report-9/report";

// A tiny URL store standing in for the App Router: replace() updates the query and
// re-renders subscribers, like a real same-route navigation.
const url = vi.hoisted(() => {
  let query = "";
  const listeners = new Set<() => void>();
  return {
    get: () => query,
    set(next: string) {
      query = next;
      listeners.forEach((listener) => listener());
    },
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
});
const replaceMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", async () => {
  const { useSyncExternalStore } = await import("react");
  return {
    useParams: () => ({ id: "proj-report-9" }),
    usePathname: () => PATHNAME,
    useRouter: () => ({ replace: replaceMock }),
    useSearchParams: () => new URLSearchParams(useSyncExternalStore(url.subscribe, url.get, url.get)),
  };
});

vi.mock("@/components/features/report/current-state/CurrentStateReportMode", () => ({
  CurrentStateReportMode: ({ projectId }: { projectId: string }) => (
    <div data-testid="current-state-mode">current state for {projectId}</div>
  ),
}));

vi.mock("@/components/features/report/AuditReportMode", () => ({
  AuditReportMode: ({ projectId }: { projectId: string }) => (
    <div data-testid="audit-mode">audit for {projectId}</div>
  ),
}));

function openWithQuery(query: string) {
  url.set(query);
  renderWithProviders(<ProjectReportPage />);
}

describe("ProjectReportPage", () => {
  beforeEach(() => {
    url.set("");
    replaceMock.mockReset();
    replaceMock.mockImplementation((href: string) => {
      url.set(href.includes("?") ? href.slice(href.indexOf("?") + 1) : "");
    });
  });

  it("opens on the current state report for the project", () => {
    openWithQuery("");
    expect(screen.getByRole("tab", { name: "Current state" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("current-state-mode")).toHaveTextContent("current state for proj-report-9");
    expect(screen.queryByTestId("audit-mode")).toBeNull();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("keeps the audit export reachable as a second mode and reflects it in the URL", async () => {
    const user = userEvent.setup();
    openWithQuery("");
    await user.click(screen.getByRole("tab", { name: "Audit export" }));
    expect(replaceMock).toHaveBeenLastCalledWith(`${PATHNAME}?mode=audit`, { scroll: false });
    expect(screen.getByTestId("audit-mode")).toHaveTextContent("audit for proj-report-9");
    expect(screen.queryByTestId("current-state-mode")).toBeNull();
  });

  it("opens the audit export directly from ?mode=audit", () => {
    openWithQuery("mode=audit");
    expect(screen.getByRole("tab", { name: "Audit export" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("audit-mode")).toBeInTheDocument();
  });

  it("falls back to the current state report for an unknown mode", () => {
    openWithQuery("mode=pdf");
    expect(screen.getByRole("tab", { name: "Current state" })).toHaveAttribute("aria-selected", "true");
  });

  it("drops the mode parameter when returning to the current state and keeps other parameters", async () => {
    const user = userEvent.setup();
    openWithQuery("mode=audit&ref=email");
    await user.click(screen.getByRole("tab", { name: "Current state" }));
    expect(replaceMock).toHaveBeenLastCalledWith(`${PATHNAME}?ref=email`, { scroll: false });
    expect(screen.getByTestId("current-state-mode")).toBeInTheDocument();
  });

  it("follows the URL when it changes while the page stays mounted", () => {
    openWithQuery("mode=audit");
    expect(screen.getByTestId("audit-mode")).toBeInTheDocument();

    // e.g. the Report tab link (no mode) is clicked while the audit export is open
    act(() => url.set(""));
    expect(screen.getByRole("tab", { name: "Current state" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("current-state-mode")).toBeInTheDocument();

    // e.g. browser back to an audit-export entry
    act(() => url.set("mode=audit"));
    expect(screen.getByRole("tab", { name: "Audit export" })).toHaveAttribute("aria-selected", "true");
  });
});
