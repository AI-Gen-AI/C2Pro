/**
 * API utilities and helpers
 * Centralized API functions for data fetching
 */

import type { Alert } from '@/types/project';
import type { AlertResponse, DocumentListResponse } from '@/types/backend';
import type { Highlight, Rectangle } from '@/types/highlight';
import { createHighlight } from '@/types/highlight';
import { apiClient } from './client';

/**
 * Processed entity type for document analysis
 */
export interface ProcessedEntity {
  id: string;
  type: 'stakeholder' | 'wbs' | 'bom' | 'clause';
  text: string;
  page: number;
  confidence: number;
  metadata?: Record<string, any>;
}

/**
 * Fetch alerts for a specific document
 * TODO: Implement actual API call
 */
export async function getDocumentAlerts(
  documentId: string
): Promise<Alert[]> {
  const response = await apiClient.get<AlertResponse[]>('/alerts', {
    params: { document_id: documentId },
  });
  return response.data;
}

/**
 * Create PDF highlights from alert data
 * TODO: Implement highlight creation logic
 */
export function createHighlightsFromAlerts(
  alerts: Alert[]
): Highlight[] {
  return alerts.flatMap((alert) => {
    const evidence = extractEvidenceLocation(alert);
    if (!evidence) return [];

    const rect: Rectangle = {
      top: evidence.bbox[1],
      left: evidence.bbox[0],
      width: evidence.bbox[2],
      height: evidence.bbox[3],
      normalized: evidence.normalized,
    };

    return [
      createHighlight(
        alert.id,
        evidence.page_number,
        [rect],
        severityToColor(alert.severity),
        alert.title
      ),
    ];
  });
}

/**
 * Fetch entities extracted from a document
 * TODO: Implement actual API call
 */
export async function getDocumentEntities(
  documentId: string,
  pageHeight?: number
): Promise<ProcessedEntity[]> {
  // Placeholder implementation
  // In production, this would call the backend API
  // GET /api/v1/documents/{documentId}/entities
  return [];
}

/**
 * Create PDF highlights from extracted entities
 * TODO: Implement highlight creation logic
 */
export function createHighlightsFromEntities(
  entities: ProcessedEntity[]
): Highlight[] {
  // Placeholder implementation
  // In production, this would transform entity data into highlight coordinates
  return [];
}

/**
 * Fetch documents for a specific project
 * TODO: Implement actual API call
 */
export async function getProjectDocuments(
  projectId: string
): Promise<DocumentListResponse[]> {
  const response = await apiClient.get<DocumentListResponse[]>(
    `/projects/${projectId}/documents`
  );
  return response.data;
}

function extractEvidenceLocation(alert: Alert): {
  page_number: number;
  bbox: [number, number, number, number];
  normalized?: boolean;
} | null {
  const alertAny = alert as AlertResponse;
  const direct = alertAny.evidence_location;
  const nested = alertAny.evidence_json?.evidence_location;
  const candidate = direct || nested;
  if (!candidate || !Array.isArray(candidate.bbox)) {
    return null;
  }
  const normalized =
    candidate.normalized ??
    candidate.bbox.every((value: number) => value >= 0 && value <= 1);
  return {
    page_number: candidate.page_number,
    bbox: candidate.bbox,
    normalized,
  };
}

function severityToColor(severity: Alert['severity']): string {
  const normalized = String(severity).toLowerCase();
  switch (normalized) {
    case 'critical':
      return 'red';
    case 'high':
      return 'orange';
    case 'medium':
      return 'yellow';
    default:
      return 'blue';
  }
}

// Re-export API client and auth utilities
export * from './client';
export * from './auth';
export * from './config';
