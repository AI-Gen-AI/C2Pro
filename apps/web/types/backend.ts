/**
 * Backend API response types
 * Types for API responses from the backend
 */

import type { Alert, Project } from './project';

/**
 * Generic API response wrapper
 */
export interface ApiResponse<T> {
  data?: T;
  error?: string;
  message?: string;
}

/**
 * Paginated response wrapper
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

/**
 * Alert API response
 */
export interface AlertResponse extends Alert {
  // Additional fields that might come from the backend
  evidence_location?: {
    page_number: number;
    bbox: [number, number, number, number];
    normalized?: boolean;
  };
  evidence_json?: {
    evidence_location?: {
      page_number: number;
      bbox: [number, number, number, number];
      normalized?: boolean;
    };
  };
}

/**
 * Project API response
 */
export type ProjectResponse = Project;

/**
 * Error response from the backend
 */
export interface ErrorResponse {
  detail: string;
  status_code?: number;
  error_code?: string;
}

/**
 * Document API response
 */
export interface DocumentResponse {
  id: string;
  project_id: string;
  name: string;
  filename?: string;
  document_type?: string;
  file_type: string;
  file_format?: string; // pdf, xlsx, docx, dwg, etc.
  file_size: number;
  storage_url?: string;
  processing_status?: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  id: string;
  filename: string;
  document_type?: string | null;
  status: 'queued' | 'processing' | 'parsed' | 'error';
  status_detail?: string;
  /** Honest lifecycle state; absent in older payloads. */
  lifecycle_status?:
    | 'uploaded'
    | 'processing'
    | 'parsed'
    | 'analysis_pending'
    | 'review_required'
    | 'analyzed'
    | 'needs_changes'
    | 'failed_retryable'
    | 'error';
  /** Whether the UI's Retry action is honest for this document (#712). */
  retryable?: boolean;
  /** Pending HITL review count when lifecycle_status is review_required (#712). */
  review_count?: number | null;
  /** Exact pending review item id, only when review_count is exactly 1 (#712). */
  review_item_id?: string | null;
  error_message?: string | null;
  uploaded_at: string;
  file_size_bytes: number;
}
