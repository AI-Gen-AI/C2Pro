import type { DashboardSummary } from "@/lib/api/generated/models";
import { DashboardService } from "./DashboardService";

export class CoherenceService {
  /**
   * Get the coherence score for a project.
   *
   * Delegates to the coherence dashboard endpoint which returns
   * global score, sub-scores, weights, and alert/document counts.
   */
  public static getScore(projectId: string): Promise<DashboardSummary> {
    return DashboardService.getSummary(projectId);
  }
}
