/**
 * Highlight System Types
 * For PDF <-> Entity Card synchronization
 */

export interface Rectangle {
  top: number;
  left: number;
  width: number;
  height: number;
  normalized?: boolean;
}

export interface Highlight {
  /** Unique identifier for the highlight */
  id: string;
  /** Page number where the highlight appears (1-indexed) */
  page: number;
  /** Bounding rectangles for the highlighted text */
  rects: Rectangle[];
  /** Highlight color (e.g., 'yellow', 'green', 'red') */
  color: string;
  /** ID of the associated entity */
  entityId: string;
  /** Optional label text to display on hover */
  label?: string;
}

export interface HighlightState {
  /** Currently active highlight ID (for animations/focus) */
  activeHighlightId: string | null;
  /** All highlights to render on the PDF */
  highlights: Highlight[];
  /** Callback when a highlight is clicked */
  onHighlightClick?: (highlightId: string, entityId: string) => void;
}

/**
 * Helper function to create a highlight from entity data
 */
export function createHighlight(
  entityId: string,
  page: number,
  rects: Rectangle[],
  color: string = 'yellow',
  label?: string
): Highlight {
  return {
    id: `highlight-${entityId}`,
    page,
    rects,
    color,
    entityId,
    label,
  };
}

/**
 * Get highlight color based on confidence level
 */
export function getHighlightColor(confidence: number): string {
  if (confidence >= 95) return 'green';
  if (confidence >= 80) return 'yellow';
  return 'red';
}
