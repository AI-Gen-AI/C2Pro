/**
 * Placeholder types until `npm run generate-client` is executed.
 * This file will be overwritten by the OpenAPI codegen output.
 */

export interface ProjectListItemResponse {
  id: string;
  name: string;
  description?: string | null;
  code?: string | null;
}

export interface ProjectListResponse {
  items: ProjectListItemResponse[];
  total?: number;
  page?: number;
  page_size?: number;
  total_pages?: number;
  has_next?: boolean;
  has_prev?: boolean;
}

export type DocumentPollingStatus = "queued" | "processing" | "parsed" | "error";

export interface DocumentListItem {
  id: string;
  filename: string;
  document_type?: string | null;
  status: DocumentPollingStatus;
  error_message?: string | null;
  uploaded_at?: string | null;
  file_size_bytes?: number | null;
  project_id: string;
}

export interface DocumentListResponse {
  items: DocumentListItem[];
  total_count: number;
  skip: number;
  limit: number;
}

export interface ProjectDocumentsGroup {
  projectId: string;
  projectName: string;
  documents: DocumentListItem[];
}

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
  last_updated: string;
}
