import { cn } from '@/lib/utils';
import type { Highlight } from '@/types/highlight';

interface HighlightLayerProps {
  /** Highlights to render on the current page */
  highlights: Highlight[];
  /** Currently active/focused highlight ID */
  activeHighlightId: string | null;
  /** Current page number (1-indexed) */
  currentPage: number;
  /** Current scale/zoom level */
  scale: number;
  /** Base PDF page dimensions (scale 1.0) */
  pageDimensions?: { width: number; height: number } | null;
  /** Callback when a highlight is clicked */
  onHighlightClick?: (highlightId: string, entityId: string) => void;
}

const COLOR_STYLE_MAP: Record<
  string,
  { backgroundColor: string; borderColor: string }
> = {
  yellow: {
    backgroundColor: 'rgba(250, 204, 21, 0.28)',
    borderColor: 'rgba(250, 204, 21, 0.85)',
  },
  green: {
    backgroundColor: 'rgba(16, 185, 129, 0.25)',
    borderColor: 'rgba(16, 185, 129, 0.8)',
  },
  red: {
    backgroundColor: 'rgba(255, 0, 0, 0.3)',
    borderColor: 'rgba(255, 0, 0, 0.85)',
  },
  orange: {
    backgroundColor: 'rgba(249, 115, 22, 0.3)',
    borderColor: 'rgba(249, 115, 22, 0.85)',
  },
  blue: {
    backgroundColor: 'rgba(59, 130, 246, 0.3)',
    borderColor: 'rgba(59, 130, 246, 0.85)',
  },
};

export function HighlightLayer({
  highlights,
  activeHighlightId,
  currentPage,
  scale,
  pageDimensions,
  onHighlightClick,
}: HighlightLayerProps) {
  // Filter highlights for current page only
  const pageHighlights = highlights.filter((h) => h.page === currentPage);

  if (pageHighlights.length === 0) {
    return null;
  }

  return (
    <div className="absolute inset-0 pointer-events-none z-10">
      {pageHighlights.map((highlight) => (
        <div key={highlight.id}>
          {highlight.rects.map((rect, idx) => {
            const isActive = highlight.id === activeHighlightId;
            const colorStyle =
              COLOR_STYLE_MAP[highlight.color] || COLOR_STYLE_MAP.yellow;
            const baseWidth = pageDimensions?.width ?? 1;
            const baseHeight = pageDimensions?.height ?? 1;
            const normalizedScaleX = rect.normalized ? baseWidth : 1;
            const normalizedScaleY = rect.normalized ? baseHeight : 1;

            return (
              <div
                key={`${highlight.id}-rect-${idx}`}
                className={cn(
                  'absolute border-2 rounded transition-all duration-200 cursor-pointer pointer-events-auto',
                  isActive && 'ring-4 ring-blue-500 ring-opacity-50 animate-pulse-gentle'
                )}
                style={{
                  top: `${rect.top * normalizedScaleY * scale}px`,
                  left: `${rect.left * normalizedScaleX * scale}px`,
                  width: `${rect.width * normalizedScaleX * scale}px`,
                  height: `${rect.height * normalizedScaleY * scale}px`,
                  backgroundColor: colorStyle.backgroundColor,
                  borderColor: colorStyle.borderColor,
                }}
                data-highlight-id={highlight.id}
                onClick={() => {
                  onHighlightClick?.(highlight.id, highlight.entityId);
                }}
                title={highlight.label || `Entity: ${highlight.entityId}`}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}

export default HighlightLayer;
