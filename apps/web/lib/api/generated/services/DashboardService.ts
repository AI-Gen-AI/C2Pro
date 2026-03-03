import type { DashboardSummary } from "@/lib/api/generated/models";
import { request } from "@/lib/api/generated/core/request";

const COHERENCE_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/api\/v1\/?$/, "") ??
  "http://localhost:8000";

export class DashboardService {
  /**
   * Get coherence dashboard summary for a project.
   *
   * Uses plain fetch (works in both server and client components).
   * The endpoint lives at /api/coherence/ (outside the /api/v1 prefix).
   */
  public static async getSummary(
    projectId: string
  ): Promise<DashboardSummary> {
    const url = `${COHERENCE_BASE}/api/coherence/dashboard/${projectId}`;
    const res = await fetch(url, { next: { revalidate: 60 } });

    if (!res.ok) {
      throw new Error(
        `Dashboard fetch failed (${res.status} ${res.statusText})`
      );
    }

    return res.json();
  }
}
