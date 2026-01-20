/**
 * Export Utilities for Evidence Viewer
 * Handles exporting highlights and entities to JSON and CSV formats
 */

import type { Highlight } from '@/types/highlight';

// Entity type matching the structure in EvidenceViewer
export interface ExtractedEntity {
  id: string;
  documentId: string;
  type: string;
  originalText?: string;
  text: string;
  confidence: number;
  validated: boolean;
  page: number;
  linkedWbs: string[];
  linkedAlerts: string[];
  highlightRects: Array<{
    top: number;
    left: number;
    width: number;
    height: number;
  }>;
}

/**
 * Export highlights and entities to JSON format
 */
export function exportToJSON(
  highlights: Highlight[],
  entities: ExtractedEntity[],
  documentName: string
): void {
  const exportData = {
    metadata: {
      exportDate: new Date().toISOString(),
      documentName: documentName,
      totalHighlights: highlights.length,
      totalEntities: entities.length,
      version: '1.0',
    },
    highlights: highlights.map((h) => ({
      id: h.id,
      page: h.page,
      entityId: h.entityId,
      color: h.color,
      label: h.label,
      rectangles: h.rectangles,
    })),
    entities: entities.map((e) => ({
      id: e.id,
      documentId: e.documentId,
      type: e.type,
      text: e.text,
      originalText: e.originalText,
      confidence: e.confidence,
      validated: e.validated,
      page: e.page,
      linkedWbs: e.linkedWbs,
      linkedAlerts: e.linkedAlerts,
      highlightRects: e.highlightRects,
    })),
  };

  // Create blob and download
  const blob = new Blob([JSON.stringify(exportData, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${sanitizeFilename(documentName)}_highlights_${getDateString()}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Export highlights and entities to CSV format
 * Creates a flattened table with one row per entity
 */
export function exportToCSV(
  highlights: Highlight[],
  entities: ExtractedEntity[],
  documentName: string
): void {
  // CSV headers
  const headers = [
    'Entity ID',
    'Document ID',
    'Type',
    'Text',
    'Confidence (%)',
    'Validated',
    'Page',
    'Linked WBS',
    'Linked Alerts',
    'Highlight Rectangles Count',
  ];

  // Convert entities to CSV rows
  const rows = entities.map((entity) => [
    escapeCsvValue(entity.id),
    escapeCsvValue(entity.documentId),
    escapeCsvValue(entity.type),
    escapeCsvValue(entity.text),
    entity.confidence.toString(),
    entity.validated ? 'Yes' : 'No',
    entity.page.toString(),
    escapeCsvValue(entity.linkedWbs.join('; ')),
    escapeCsvValue(entity.linkedAlerts.join('; ')),
    entity.highlightRects.length.toString(),
  ]);

  // Combine headers and rows
  const csvContent = [
    headers.join(','),
    ...rows.map((row) => row.join(',')),
  ].join('\n');

  // Create blob and download
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${sanitizeFilename(documentName)}_highlights_${getDateString()}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Escape CSV values that contain commas, quotes, or newlines
 */
function escapeCsvValue(value: string): string {
  if (!value) return '';

  // If value contains comma, quote, or newline, wrap in quotes and escape existing quotes
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return `"${value.replace(/"/g, '""')}"`;
  }

  return value;
}

/**
 * Sanitize filename by removing invalid characters
 */
function sanitizeFilename(filename: string): string {
  return filename
    .replace(/[^a-z0-9_\-\.]/gi, '_')
    .replace(/_{2,}/g, '_')
    .substring(0, 200); // Limit length
}

/**
 * Get current date as string in YYYY-MM-DD format
 */
function getDateString(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}
