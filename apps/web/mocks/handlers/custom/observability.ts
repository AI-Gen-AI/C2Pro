import { http, HttpResponse } from "msw";
import { db } from "../../data";

export const observabilityHandlers = [
  // ── System status ───────────────────────────────────────
  http.get("/api/v1/observability/status", () => {
    return HttpResponse.json({
      api_status: "OK",
      database_status: "OK",
      timestamp: new Date().toISOString(),
    });
  }),

  // ── Recent analyses ─────────────────────────────────────
  http.get("/api/v1/observability/analyses", () => {
    const projects = db.project.getAll();

    const analyses = projects
      .filter((p) => p.status === "active" || p.status === "completed")
      .map((project, idx) => {
        const isCompleted = idx < 3;
        const startedAt = new Date();
        startedAt.setHours(startedAt.getHours() - (idx + 1) * 4);

        const completedAt = isCompleted ? new Date(startedAt) : null;
        if (completedAt) {
          completedAt.setMinutes(completedAt.getMinutes() + 12);
        }

        const alerts = db.alert.findMany({
          where: { projectId: { equals: project.id } },
        });

        return {
          id: `analysis_demo_${String(idx + 1).padStart(3, "0")}`,
          project_id: project.id,
          status: isCompleted ? "COMPLETED" : "RUNNING",
          coherence_score: isCompleted
            ? Number((0.72 + idx * 0.06).toFixed(2))
            : null,
          alerts_count: alerts.length,
          started_at: startedAt.toISOString(),
          completed_at: completedAt ? completedAt.toISOString() : null,
        };
      });

    return HttpResponse.json({
      analyses,
      total_analyses: analyses.length,
    });
  }),
];
