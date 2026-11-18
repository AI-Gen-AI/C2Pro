"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";
import { env } from "@/config/env";

type BudgetItem = {
  tenant_id: string;
  name: string;
  slug: string;
  is_active: boolean;
  monthly_cap_usd: string;
  spent_usd: string;
  reserved_usd: string;
  available_usd: string;
  utilisation_percent: string;
  budget_status: "RECONCILED" | "NO_TENANT_BUCKET" | "COUNTERS_DIVERGED";
  last_tenant_update: string | null;
};
type Page = { items: BudgetItem[]; total: number; limit: number; offset: number; period_key: string };

const PAGE_SIZE = 25;
const money = (value: string) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", minimumFractionDigits: 2,
  }).format(parsed) : "—";
};
const statusColor = (percent: string) => Number(percent) >= 100
  ? "text-red-600" : Number(percent) >= 90
  ? "text-orange-600" : Number(percent) >= 75
  ? "text-amber-600" : "text-foreground";

export default function PlatformBudgetsPage() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<Page | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      setPage(null); setLoading(false); setError("A valid operator session is required.");
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);
    setPage(null);
    const load = async () => {
      try {
        const token = await getToken();
        if (!token) throw new Error("Operator session unavailable.");
        const params = new URLSearchParams({ query: appliedSearch, limit: String(PAGE_SIZE), offset: String(offset) });
        const base = env.API_BASE_URL.replace(/\/$/, "");
        const response = await fetch(base + "/v1/platform/budgets?" + params.toString(), {
          signal: controller.signal,
          headers: { Authorization: "Bearer " + token },
          cache: "no-store",
        });
        if (response.status === 401 || response.status === 403) throw new Error("Access denied.");
        if (response.status === 503) throw new Error("Platform budget read access is not enabled.");
        if (!response.ok) throw new Error("Unable to load budgets.");
        const data: Page = await response.json();
        if (active) setPage(data);
      } catch (cause) {
        if (active && !controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Unable to load budgets.");
      } finally {
        if (active && !controller.signal.aborted) setLoading(false);
      }
    };
    void load();
    return () => { active = false; controller.abort(); };
  }, [getToken, isLoaded, isSignedIn, appliedSearch, offset]);

  return <section className="mx-auto max-w-6xl space-y-5" aria-label="AI-GEN platform budgets">
    <header>
      <h1 className="text-2xl font-semibold">AI-GEN · AI budgets</h1>
      <p className="text-sm text-muted-foreground">Private platform operator view · read-only · tenant monthly USD caps</p>
    </header>
    <form className="flex items-center gap-3" onSubmit={e => {
      e.preventDefault(); setAppliedSearch(search.trim()); setOffset(0);
    }}>
      <label htmlFor="tenant-budget-search" className="sr-only">Search tenant name</label>
      <input id="tenant-budget-search" className="w-full max-w-sm rounded-md border bg-background px-3 py-2"
        value={search} onChange={e => setSearch(e.target.value)} maxLength={100} placeholder="Search tenant by name" />
      <button type="submit" className="rounded-md border px-4 py-2 text-sm">Search</button>
    </form>
    {error && <div role="alert" className="rounded-md border p-4 text-sm">{error}</div>}
    {loading && <p role="status" className="text-sm">Loading tenant budgets…</p>}
    {page && <div className="space-y-3">
      <p className="text-sm text-muted-foreground">{page.total} tenants · {page.period_key} UTC · Values are not spending authorisations</p>
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-left text-sm">
          <thead className="border-b bg-muted/40"><tr>
            <th scope="col" className="p-3">Tenant</th><th scope="col" className="p-3">Status</th>
            <th scope="col" className="p-3 text-right">Monthly cap</th><th scope="col" className="p-3 text-right">Spent</th>
            <th scope="col" className="p-3 text-right">Reserved</th><th scope="col" className="p-3 text-right">Available</th>
            <th scope="col" className="p-3 text-right">Used</th><th scope="col" className="p-3">Reconciliation</th><th scope="col" className="p-3">Last tenant update</th>
          </tr></thead>
          <tbody>{page.items.map(row => <tr key={row.tenant_id} className="border-t">
            <td className="p-3"><div className="font-medium">{row.name}</div><div className="text-xs text-muted-foreground">{row.slug} · {row.tenant_id}</div></td>
            <td className="p-3">{row.is_active ? "Active" : "Inactive"}</td>
            <td className="p-3 text-right tabular-nums">{money(row.monthly_cap_usd)}</td>
            <td className="p-3 text-right tabular-nums">{money(row.spent_usd)}</td>
            <td className="p-3 text-right tabular-nums">{money(row.reserved_usd)}</td>
            <td className="p-3 text-right tabular-nums">{money(row.available_usd)}</td>
            <td className={"p-3 text-right tabular-nums " + statusColor(row.utilisation_percent)}>{row.utilisation_percent}%</td>
            <td className="p-3 text-xs">{row.budget_status === "RECONCILED" ? "Matched" : row.budget_status === "NO_TENANT_BUCKET" ? "Bucket missing" : "Counters differ"}</td>
            <td className="p-3 text-xs">{row.last_tenant_update ? new Date(row.last_tenant_update).toLocaleString() : "—"}</td>
          </tr>)}</tbody>
        </table>
        {page.items.length === 0 && <p className="p-5 text-sm">No matching tenants.</p>}
      </div>
      <div className="flex items-center gap-3">
        <button type="button" className="rounded-md border px-3 py-2 text-sm disabled:opacity-50"
          disabled={offset === 0} onClick={() => setOffset(v => Math.max(0, v - PAGE_SIZE))}>Previous</button>
        <span className="text-sm">{page.total ? offset + 1 : 0}–{Math.min(offset + PAGE_SIZE, page.total)} of {page.total}</span>
        <button type="button" className="rounded-md border px-3 py-2 text-sm disabled:opacity-50"
          disabled={offset + PAGE_SIZE >= page.total} onClick={() => setOffset(v => v + PAGE_SIZE)}>Next</button>
        <span className="ml-auto text-xs text-muted-foreground">Editing locked pending SECURITY approval</span>
      </div>
    </div>}
  </section>;
}
