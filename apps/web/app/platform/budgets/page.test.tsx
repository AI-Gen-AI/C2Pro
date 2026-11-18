import { fireEvent, render, screen, waitFor } from "@/src/tests/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import PlatformBudgetsPage from "./page";

const clerk = vi.hoisted(() => ({
  getToken: vi.fn(),
  isSignedIn: true,
}));

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    getToken: clerk.getToken,
    isLoaded: true,
    isSignedIn: clerk.isSignedIn,
  }),
}));

type SyntheticPage = {
  items: Array<{
    tenant_id: string;
    name: string;
    slug: string;
    is_active: boolean;
    monthly_cap_usd: string;
    spent_usd: string;
    reserved_usd: string;
    available_usd: string;
    utilisation_percent: string;
    budget_status: "RECONCILED";
    last_tenant_update: string | null;
  }>;
  total: number;
  limit: number;
  offset: number;
  period_key: string;
};

const row = {
  tenant_id: "synthetic-tenant-01",
  name: "Example EPC",
  slug: "example-epc",
  is_active: true,
  monthly_cap_usd: "5",
  spent_usd: "1",
  reserved_usd: "0.5",
  available_usd: "3.5",
  utilisation_percent: "30",
  budget_status: "RECONCILED" as const,
  last_tenant_update: null,
};

const page = (total = 1): SyntheticPage => ({
  items: [row],
  total,
  limit: 25,
  offset: 0,
  period_key: "2026-11",
});

const response = (status: number, data: SyntheticPage | object = page()) => ({
  ok: status >= 200 && status < 300,
  status,
  json: vi.fn().mockResolvedValue(data),
});

describe("private AI-GEN platform budgets", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    clerk.isSignedIn = true;
    clerk.getToken.mockReset().mockResolvedValue("synthetic-clerk-token");
    fetchMock = vi.fn().mockResolvedValue(response(200));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("renders read-only amounts without any editing or writing actions", async () => {
    render(<PlatformBudgetsPage />);
    expect(await screen.findByText("Example EPC")).toBeInTheDocument();
    expect(screen.getByText("synthetic-tenant-01", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Read-only", { exact: false })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit Example EPC" })).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/v1/platform/budgets?");
    expect(init.headers.Authorization).toBe("Bearer synthetic-clerk-token");
    expect(init.headers["X-Tenant-ID"]).toBeUndefined();
    expect(init.cache).toBe("no-store");
    expect(init.method).toBeUndefined(); // native GET only; no write request
  });

  it("opens the edit modal but refuses all writes under security hold", async () => {
    render(<PlatformBudgetsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Edit Example EPC" }));
    expect(screen.getByRole("dialog", { name: "Edit AI limit" })).toBeInTheDocument();
    expect(screen.getByLabelText("New monthly limit (USD)")).toHaveValue(5);
    fireEvent.change(screen.getByLabelText("Audit reason"), {
      target: { value: "Security hold should prevent real writes" },
    });
    expect(screen.getByRole("button", { name: "Save (locked)" })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("searches tenant name and changes server-side offset", async () => {
    fetchMock.mockResolvedValue(response(200, page(30)));
    render(<PlatformBudgetsPage />);
    expect(await screen.findByText("Example EPC")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("Search tenant by name"), {
      target: { value: "Example" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) =>
        String(url).includes("query=Example")
      )).toBe(true);
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) =>
        String(url).includes("offset=25")
      )).toBe(true);
    });
  });

  it.each([
    [403, "Access denied."],
    [503, "Platform budget read access is not enabled."],
  ])("fails closed on HTTP %s with no tenant data", async (status, message) => {
    fetchMock.mockResolvedValue(response(status));
    render(<PlatformBudgetsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.queryByText("Example EPC")).not.toBeInTheDocument();
  });

  it("never fetches when an operator token is unavailable", async () => {
    clerk.getToken.mockResolvedValue(null);
    render(<PlatformBudgetsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Operator session unavailable.");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
