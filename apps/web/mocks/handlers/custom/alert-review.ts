import { HttpResponse, http } from "msw";

type ReviewState = {
  status: "pending" | "approved" | "rejected";
  rejectionReason?: string;
};

const reviewState = new Map<string, ReviewState>();

function ensureState(alertId: string): ReviewState {
  const current = reviewState.get(alertId);
  if (current) return current;
  const initial: ReviewState = { status: "pending" };
  reviewState.set(alertId, initial);
  return initial;
}

export const alertReviewHandlers = [
  http.post("/api/v1/projects/:projectId/alerts/:alertId/approve", async ({ params, request }) => {
    const alertId = String(params.alertId);
    const current = ensureState(alertId);
    if (current.status === "rejected") {
      return HttpResponse.json(
        { code: "ALERT_CONFLICT", detail: "Rejected alerts cannot be approved" },
        { status: 409 },
      );
    }

    const payload = (await request.json()) as { approverId?: string };
    reviewState.set(alertId, { status: "approved" });
    return HttpResponse.json({
      id: alertId,
      status: "approved",
      reviewedBy: payload.approverId ?? "unknown-reviewer",
    });
  }),

  http.post("/api/v1/projects/:projectId/alerts/:alertId/reject", async ({ params, request }) => {
    const alertId = String(params.alertId);
    const payload = (await request.json()) as { reason?: string };
    const reason = payload.reason ?? "Rejected";
    reviewState.set(alertId, { status: "rejected", rejectionReason: reason });

    return HttpResponse.json({
      id: alertId,
      status: "rejected",
      rejectionReason: reason,
    });
  }),

  http.post("/api/v1/projects/:projectId/alerts", async ({ request }) => {
    const payload = (await request.json()) as {
      title: string;
      severity: string;
      clauseId: string;
    };

    return HttpResponse.json(
      {
        id: "a-created-001",
        title: payload.title,
        severity: payload.severity,
        clauseId: payload.clauseId,
        rank: 1,
      },
      { status: 201 },
    );
  }),

  http.patch("/api/v1/projects/:projectId/alerts/:alertId", ({ params }) => {
    const alertId = String(params.alertId);
    if (alertId === "a-missing") {
      return HttpResponse.json(
        { code: "ALERT_NOT_FOUND", detail: "Alert not found" },
        { status: 404 },
      );
    }

    return HttpResponse.json({ id: alertId, ok: true });
  }),

  http.delete("/api/v1/projects/:projectId/alerts/:alertId", ({ params }) => {
    const alertId = String(params.alertId);
    if (alertId === "a-concurrent") {
      return HttpResponse.json(
        { code: "ALERT_CONFLICT", detail: "Alert changed since last read" },
        { status: 409 },
      );
    }

    return new HttpResponse(null, { status: 204 });
  }),

  http.post("/api/v1/projects/:projectId/alerts/sync", async ({ request }) => {
    const payload = (await request.json()) as {
      localDraft?: {
        alertId: string;
        title: string;
      };
    };

    return HttpResponse.json({
      preservedDraft: payload.localDraft ?? null,
    });
  }),
];
