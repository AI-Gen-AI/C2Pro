import { useState, useEffect, useRef } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Search, ChevronUp, ChevronDown, X } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface HighlightSearchBarProps {
  /** Current search query */
  searchQuery: string;
  /** Callback when search query changes */
  onSearchChange: (query: string) => void;
  /** Current match index (zero-based) */
  currentIndex: number;
  /** Total number of matches */
  totalMatches: number;
  /** Navigate to next match */
  onNext: () => void;
  /** Navigate to previous match */
  onPrevious: () => void;
  /** Close the search bar */
  onClose: () => void;
  /** Whether the search bar is visible */
  isVisible: boolean;
}

/**
 * HighlightSearchBar Component
 *
 * A sticky search bar for finding and navigating through highlights in the PDF.
 * Features:
 * - Debounced search input (300ms)
 * - Next/Previous navigation
 * - Match counter display
 * - Keyboard shortcuts (Enter, Shift+Enter, Esc)
 * - Auto-focus on mount
 *
 * @example
 * ```tsx
 * <HighlightSearchBar
 *   searchQuery={searchQuery}
 *   onSearchChange={setSearchQuery}
 *   currentIndex={0}
 *   totalMatches={5}
 *   onNext={goToNext}
 *   onPrevious={goToPrevious}
 *   onClose={() => setVisible(false)}
 *   isVisible={true}
 * />
 * ```
 */
export function HighlightSearchBar({
  searchQuery,
  onSearchChange,
  currentIndex,
  totalMatches,
  onNext,
  onPrevious,
  onClose,
  isVisible,
}: HighlightSearchBarProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [localQuery, setLocalQuery] = useState(searchQuery);

  /**
   * Debounce the search query to avoid excessive re-renders
   * Waits 300ms after user stops typing before triggering search
   */
  useEffect(() => {
    const timer = setTimeout(() => {
      onSearchChange(localQuery);
    }, 300);

    return () => clearTimeout(timer);
  }, [localQuery, onSearchChange]);

  /**
   * Auto-focus the input when the search bar becomes visible
   */
  useEffect(() => {
    if (isVisible && inputRef.current) {
      inputRef.current.focus();
      // Select all text for easy replacement
      inputRef.current.select();
    }
  }, [isVisible]);

  /**
   * Sync local query with external query changes
   * (e.g., when search is cleared externally)
   */
  useEffect(() => {
    setLocalQuery(searchQuery);
  }, [searchQuery]);

  // Don't render if not visible
  if (!isVisible) {
    return null;
  }

  const hasMatches = totalMatches > 0;
  const hasQuery = localQuery.trim().length > 0;

  // Determine what to show in the counter badge
  const matchCounter = hasMatches
    ? `${currentIndex + 1}/${totalMatches}`
    : hasQuery
      ? 'No matches'
      : '';

  return (
    <Card
      className={cn(
        'sticky top-0 z-20 border-b shadow-sm rounded-none',
        'animate-in slide-in-from-top duration-200'
      )}
    >
      <div className="flex items-center gap-2 p-3">
        {/* Search Icon */}
        <Search className="h-4 w-4 text-muted-foreground flex-shrink-0" />

        {/* Search Input */}
        <Input
          ref={inputRef}
          id="highlight-search-input"
          type="text"
          placeholder="Search highlights in this document..."
          value={localQuery}
          onChange={(e) => setLocalQuery(e.target.value)}
          onKeyDown={(e) => {
            // Navigate on Enter
            if (e.key === 'Enter') {
              e.preventDefault();
              if (hasMatches) {
                if (e.shiftKey) {
                  onPrevious();
                } else {
                  onNext();
                }
              }
            }
            // Close on Escape
            else if (e.key === 'Escape') {
              onClose();
            }
          }}
          className="flex-1 h-9"
          aria-label="Search highlights"
          aria-describedby="search-results-count"
        />

        {/* Match Counter */}
        <Badge
          variant={
            hasMatches ? 'secondary' : hasQuery ? 'outline' : 'secondary'
          }
          className={cn(
            'min-w-[70px] text-center font-mono text-xs',
            hasQuery && !hasMatches && 'text-muted-foreground'
          )}
          id="search-results-count"
        >
          {matchCounter || '0/0'}
        </Badge>

        {/* Navigation Buttons */}
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={onPrevious}
            disabled={!hasMatches}
            aria-label="Previous match (Shift+Enter)"
            title="Previous match (Shift+Enter)"
            className="h-9 w-9"
          >
            <ChevronUp className="h-4 w-4" />
          </Button>

          <Button
            variant="ghost"
            size="icon"
            onClick={onNext}
            disabled={!hasMatches}
            aria-label="Next match (Enter)"
            title="Next match (Enter)"
            className="h-9 w-9"
          >
            <ChevronDown className="h-4 w-4" />
          </Button>
        </div>

        {/* Close Button */}
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          aria-label="Close search (Esc)"
          title="Close search (Esc)"
          className="h-9 w-9"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Keyboard Shortcuts Hint */}
      {hasMatches && (
        <div className="px-3 pb-2 text-xs text-muted-foreground flex items-center gap-2">
          <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px] font-semibold border border-border">
            Enter
          </kbd>
          <span>next</span>
          <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px] font-semibold border border-border">
            Shift+Enter
          </kbd>
          <span>previous</span>
          <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px] font-semibold border border-border">
            Esc
          </kbd>
          <span>close</span>
        </div>
      )}

      {/* Screen reader announcements */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {hasMatches
          ? `${totalMatches} matches found. Currently on match ${currentIndex + 1} of ${totalMatches}`
          : hasQuery
            ? 'No matches found'
            : ''}
      </div>
    </Card>
  );
}
