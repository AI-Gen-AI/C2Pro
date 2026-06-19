export type HealthDimension =
  | "contract"
  | "risk"
  | "documentation"
  | "governance"
  | "schedule"
  | "cost"
  | "deliverables";

export type HealthBand = "healthy" | "watch" | "at_risk" | "critical" | "unknown";

export type HealthTrend = "up" | "down" | "flat" | "unknown";

export type HealthNullReason =
  | "insufficient_evidence"
  | "not_applicable"
  | "budget_exhausted";

export type EvidenceTier = "verified" | "weak" | "inferred" | "unverified";

export interface EvidenceRef {
  ref_id: string;
  source: string;
  tier: EvidenceTier;
  locator?: string | null;
}

export interface HealthSignal {
  dimension: HealthDimension;
  score: number | null;
  band: HealthBand;
  confidence: number;
  evidence: EvidenceRef[];
  trend: HealthTrend;
  missing_data: string[];
  null_reason: HealthNullReason | null;
}

export interface HealthVector {
  project_id: string;
  tenant_id: string;
  dimensions: HealthSignal[];
  composite_score: number | null;
  composite_band: HealthBand;
  composite_trend: HealthTrend;
  computed_at: string;
}
