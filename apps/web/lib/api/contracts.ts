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

export interface ProjectListItem extends ProjectResponse {}

export interface ProjectDocumentListItem extends DocumentListItem {
  project_id: string;
}

export type { DocumentPollingStatus };

export interface ProjectDocumentsGroup {
  projectId: string;
  projectName: string;
  documents: ProjectDocumentListItem[];
}
