import { HttpResponse, http } from "msw";

export const onboardingSampleProjectHandlers = [
  http.post("/api/v1/onboarding/sample-project/start", async () => {
    return HttpResponse.json({
      projectId: "proj_sample_001",
      route: "/dashboard/projects/proj_sample_001",
      reused: true,
      duplicateCreated: false,
    });
  }),

  http.get("/api/v1/onboarding/sample-project/ready", () => {
    return HttpResponse.json({
      widgets: {
        documents: "ready",
        alerts: "ready",
        stakeholders: "ready",
      },
    });
  }),

  http.post("/api/v1/onboarding/sample-project/retry", async ({ request }) => {
    const payload = (await request.json()) as { sessionId?: string };
    return HttpResponse.json({
      sessionId: payload.sessionId ?? "onb_001",
      state: "ready",
      recovered: true,
    });
  }),

  http.get("/api/v1/onboarding/sample-project/telemetry", () => {
    return HttpResponse.json({
      events: ["start", "ready"],
      elapsedMs: 180000,
    });
  }),
];

