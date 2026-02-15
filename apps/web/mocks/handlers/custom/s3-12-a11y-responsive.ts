import { HttpResponse, http } from "msw";

export const s312A11yResponsiveHandlers = [
  http.get("/api/v1/a11y/axe-scan", () => {
    return HttpResponse.json({ criticalViolations: 0 });
  }),

  http.get("/api/v1/a11y/keyboard-flow", () => {
    return HttpResponse.json({ traps: 0, completed: true });
  }),

  http.get("/api/v1/a11y/modes", () => {
    return HttpResponse.json({ operable: true, readable: true });
  }),

  http.get("/api/v1/responsive/tablet-layout", () => {
    return HttpResponse.json({ clipped: 0, overlaps: 0 });
  }),

  http.get("/api/v1/responsive/tablet-orientation-state", () => {
    return HttpResponse.json({ preserved: true });
  }),
];
