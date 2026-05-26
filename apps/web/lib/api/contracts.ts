import type {
  DocumentListItem,
  DocumentPollingStatus,
  ProjectResponse,
} from "@/lib/api/generated/models";

// ECOA v2 (ADR-009 §5) — canonical evidence-aware coherence contract.
export type CategoryStatus =
  | "pending_documents"
  | "insufficient_evidence"
  | "scored"
  | "conflicting_evidence"
  | "not_applicable"
  | "processing_error";

export interface ScoreExplanation {
  positive_factors: string[];
  negative_factors: string[];
  dominant_rules: string[];
  score_path: Array<Record<string, unknown>>;
}

export interface CategoryV2 {
  category: string;
  status: CategoryStatus;
  coherence_score: number | null;
  evidence_coverage: number;
  technical_reliability: number;
  evidence_freshness: number;
  applicability_reason: string | null;
  score_explanation: ScoreExplanation | null;
  evidence_count?: number;
  evidence_references?: string[];
  missing_evidence?: string[];
  detected_conflicts?: Array<Record<string, unknown>>;
  rationale?: string | null;
  recommendation?: string | null;
  calculation_metadata?: Record<string, unknown>;
}

export interface GlobalV2 {
  coherence_score: number | null;
  completeness_score: number;
  technical_reliability_index: number;
  status: "scored" | "partial" | "insufficient_active_weight" | "pending_documents";
  score_reason: string | null;
  active_weight: number;
}

export interface CoherenceV2Payload {
  project_id: string;
  version: "coherence-v2";
  generated_at: string;
  global: GlobalV2;
  categories: CategoryV2[];
}

export interface DashboardSummary {
  project_id: string;
  tenant_id: string;
  coherence_score: number | null;
  global_score: number | null;
  sub_scores: Record<string, number | null>;
  weights_used: Record<string, number>;
  alert_count: number;
  document_count: number;
  methodology_version: string;
  score_version?:
    | "v0_flag_based"
    | "v1_exponential_decay"
    | "v2_evidence_aware"
    | string
    | null;
  score_reason?: string | null;
  score_missing_dimensions?: string[];
  last_updated: string | null;
  // ECOA v2 additive field (ADR-009 §7.2). Null when `coherence_v2_enabled` is off.
  categories_v2?: CoherenceV2Payload | null;
}

export interface ProjectListItem extends ProjectResponse {
  alert_count?: number | null;
  critical_alert_count?: number | null;
  coherence_score_delta?: number | null;
  alert_count_delta?: number | null;
  updated_at?: string | null;
}

export interface ProjectQuickViewAlert {
  id: string;
  title: string;
  severity: string;
  status: string;
  created_at: string;
}

export interface ProjectQuickViewSummary {
  project_id: string;
  tenant_id: string;
  name: string;
  code: string | null;
  description: string | null;
  project_type: string;
  status: string;
  coherence_score: number;
  client_name: string | null;
  open_alert_count: number;
  critical_alert_count: number;
  top_alerts: ProjectQuickViewAlert[];
  updated_at: string | null;
}

export interface ProjectDocumentListItem extends DocumentListItem {
  project_id: string;
}

export type { DocumentPollingStatus };

export interface ProjectDocumentsGroup {
  projectId: string;
  projectName: string;
  documents: ProjectDocumentListItem[];
}

export interface AICostSeriesPoint {
  bucket: string | null;
  model: string;
  prompt_version: string;
  request_count: number;
  total_tokens: number;
  total_cost: number;
  avg_latency_ms: number;
}

export interface AICostAnalytics {
  timeframe: string;
  window_start: string;
  summary: {
    total_cost: number;
    total_tokens: number;
    total_requests: number;
  };
  series: AICostSeriesPoint[];
}

export interface AIVersionPerformanceItem {
  prompt_version: string;
  prompt_tag: string;
  total_runs: number;
  success_runs: number;
  success_rate: number;
  avg_latency_ms: number;
  total_cost: number;
  feedback_count: number;
  avg_feedback_score: number;
}

export interface AIVersionPerformance {
  timeframe: string;
  window_start: string;
  versions: AIVersionPerformanceItem[];
}

export interface AIQualityDriftPoint {
  bucket: string | null;
  operation: string;
  run_count: number;
  avg_latency_ms: number;
  avg_feedback_score: number;
  feedback_count: number;
}

export interface AIQualityDriftAlert {
  severity: "low" | "medium" | "high";
  type: "feedback_drop" | "latency_spike";
  operation: string;
  bucket: string | null;
  message: string;
}

export interface AIQualityDrift {
  timeframe: string;
  window_start: string;
  series: AIQualityDriftPoint[];
  alerts: AIQualityDriftAlert[];
}

export interface AIUsageMetric {
  id: string;
  timestamp: string;
  model: string;
  prompt_version: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost: number;
  latency_ms: number;
  trace_url: string | null;
}

export interface AIUsageMetricsResponse {
  metrics: AIUsageMetric[];
  total_count: number;
  page: number;
  page_size: number;
}
