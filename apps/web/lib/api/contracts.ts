import type {
  DocumentListItem,
  DocumentPollingStatus,
  ProjectResponse,
} from "@/lib/api/generated/models";

export interface DashboardSummary {
  project_id: string;
  tenant_id: string;
  coherence_score: number;
  global_score: number;
  sub_scores: Record<string, number>;
  weights_used: Record<string, number>;
  alert_count: number;
  document_count: number;
  methodology_version: string;
  last_updated: string | null;
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
