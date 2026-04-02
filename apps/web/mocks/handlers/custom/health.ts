import { http, HttpResponse } from "@/mocks/msw";

export const healthHandler = http.get("/api/v1/health", () =>
  HttpResponse.json({ status: "ok" }),
);
