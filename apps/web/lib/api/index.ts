/**
 * API utilities and helpers
 * Centralized API functions for data fetching
 */

import type { Alert } from '@/types/project';
import type { Highlight } from '@/types/highlight';

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
  // Placeholder implementation
  // In production, this would call the backend API
  // GET /api/v1/documents/{documentId}/alerts
  return [];
}

/**
 * Create PDF highlights from alert data
 * TODO: Implement highlight creation logic
 */
export function createHighlightsFromAlerts(
  alerts: Alert[]
): Highlight[] {
  // Placeholder implementation
  // In production, this would transform alert evidence into highlight coordinates
  return [];
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
): Promise<any[]> {
  // Placeholder implementation
  // In production, this would call the backend API
  // GET /api/v1/projects/{projectId}/documents
  return [];
}

// Re-export API client and auth utilities
export * from './client';
export * from './auth';
export * from './config';
