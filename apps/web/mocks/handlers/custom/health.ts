import { http, HttpResponse } from "msw";

export const healthHandler = http.get("/api/v1/health", () =>
  HttpResponse.json({ status: "ok" }),
);
