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
