/**
 * Document Management Types
 * For handling multiple PDFs and their state
 */

export type DocumentType = 'contract' | 'schedule' | 'bom' | 'specification' | 'drawing';

export interface DocumentInfo {
  /** Unique identifier for the document */
  id: string;
  /** Display name */
  name: string;
  /** Document type */
  type: DocumentType;
  /** File extension */
  extension: 'pdf' | 'xlsx' | 'docx' | 'dwg';
  /** URL or path to the document */
  url: string;
  /** Total number of pages (for PDFs) */
  totalPages?: number;
  /** File size in bytes */
  fileSize?: number;
  /** Upload/creation date */
  uploadedAt?: Date;
}

export interface DocumentViewState {
  /** Current page number (1-indexed) */
  currentPage: number;
  /** Current zoom scale */
  scale: number;
  /** Current rotation (0, 90, 180, 270) */
  rotation: number;
  /** Last viewed timestamp */
  lastViewed?: Date;
}

export interface DocumentStateMap {
  [documentId: string]: DocumentViewState;
}

/**
 * Default view state for a new document
 */
export const DEFAULT_VIEW_STATE: DocumentViewState = {
  currentPage: 1,
  scale: 1.0,
  rotation: 0,
};

/**
 * Get file icon based on extension
 */
export function getDocumentIcon(extension: string): string {
  switch (extension) {
    case 'pdf':
      return '📄';
    case 'xlsx':
      return '📊';
    case 'docx':
      return '📝';
    case 'dwg':
      return '📐';
    default:
      return '📎';
  }
}

/**
 * Format file size to human-readable string
 */
export function formatFileSize(bytes?: number): string {
  if (!bytes) return 'Unknown size';

  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;

  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
}
