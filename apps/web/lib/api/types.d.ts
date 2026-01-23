// Auto-generated types would normally be exported here
// export * from "./generated/models";

// Temporarily define types directly until OpenAPI generation is set up
import type { Project } from '@/types/project';

export interface ProjectDetailResponse extends Project {
  // Additional fields that might be in the API response
}

export interface ProjectListResponse {
  items: Project[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}
