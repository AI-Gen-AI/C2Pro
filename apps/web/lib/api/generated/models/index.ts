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
