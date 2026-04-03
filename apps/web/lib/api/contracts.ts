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
