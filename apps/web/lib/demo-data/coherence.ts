export type CoherenceCategoryKey =
  | "SCOPE"
  | "BUDGET"
  | "QUALITY"
  | "TECHNICAL"
  | "LEGAL"
  | "TIME";

export const coherenceData = {
  score: 78,
  docs: 8,
  points: 2847,
  cats: {
    SCOPE: { score: 80, alerts: 2, w: 0.2, trend: [72, 75, 78, 80] },
    BUDGET: { score: 62, alerts: 5, w: 0.2, trend: [58, 60, 61, 62] },
    QUALITY: { score: 85, alerts: 1, w: 0.15, trend: [80, 82, 84, 85] },
    TECHNICAL: { score: 72, alerts: 3, w: 0.15, trend: [65, 68, 70, 72] },
    LEGAL: { score: 90, alerts: 0, w: 0.15, trend: [85, 87, 89, 90] },
    TIME: { score: 75, alerts: 4, w: 0.15, trend: [70, 72, 73, 75] },
  },
  alertSum: { critical: 2, high: 5, medium: 8, low: 3 },
};

export const categoryLabels: Record<string, string> = {
  SCOPE: "Scope",
  BUDGET: "Budget",
  QUALITY: "Quality",
  TECHNICAL: "Technical",
  LEGAL: "Legal",
  TIME: "Time",
};
