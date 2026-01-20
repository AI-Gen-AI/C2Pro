/**
 * DocumentTabs Component
 * Displays documents as tabs for quick navigation
 * Replaces dropdown selector with visual tab interface
 */

import { useRef, useState, useEffect } from 'react';
import { X, ChevronLeft, ChevronRight, MoreHorizontal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { getDocumentIcon } from '@/types/document';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

export interface DocumentTab {
  id: string;
  name: string;
  extension: string;
  entityCount?: number;
}

interface DocumentTabsProps {
  documents: DocumentTab[];
  activeDocumentId: string;
  onDocumentChange: (documentId: string) => void;
  onDocumentClose?: (documentId: string) => void;
  maxVisibleTabs?: number;
  className?: string;
}

export function DocumentTabs({
  documents,
  activeDocumentId,
  onDocumentChange,
  onDocumentClose,
  maxVisibleTabs = 6,
  className,
}: DocumentTabsProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showLeftScroll, setShowLeftScroll] = useState(false);
  const [showRightScroll, setShowRightScroll] = useState(false);
  const [overflowDocuments, setOverflowDocuments] = useState<DocumentTab[]>([]);

  // Check scroll position
  const checkScroll = () => {
    const container = scrollContainerRef.current;
    if (!container) return;

    setShowLeftScroll(container.scrollLeft > 0);
    setShowRightScroll(
      container.scrollLeft < container.scrollWidth - container.clientWidth - 1
    );
  };

  // Handle overflow documents
  useEffect(() => {
    if (documents.length > maxVisibleTabs) {
      // Show first maxVisibleTabs - 1, then overflow menu
      const activeIndex = documents.findIndex((doc) => doc.id === activeDocumentId);

      if (activeIndex >= maxVisibleTabs - 1) {
        // Active tab is in overflow, keep it visible
        const visibleDocs = [
          ...documents.slice(0, maxVisibleTabs - 2),
          documents[activeIndex],
        ];
        const overflowDocs = documents.filter(
          (doc) => !visibleDocs.includes(doc)
        );
        setOverflowDocuments(overflowDocs);
      } else {
        // Active tab is visible normally
        setOverflowDocuments(documents.slice(maxVisibleTabs - 1));
      }
    } else {
      setOverflowDocuments([]);
    }
  }, [documents, activeDocumentId, maxVisibleTabs]);

  useEffect(() => {
    checkScroll();
    window.addEventListener('resize', checkScroll);
    return () => window.removeEventListener('resize', checkScroll);
  }, [documents]);

  const scroll = (direction: 'left' | 'right') => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const scrollAmount = 200;
    container.scrollBy({
      left: direction === 'left' ? -scrollAmount : scrollAmount,
      behavior: 'smooth',
    });

    setTimeout(checkScroll, 100);
  };

  const visibleDocuments =
    documents.length > maxVisibleTabs
      ? documents.slice(0, maxVisibleTabs - 1)
      : documents;

  const activeDoc = documents.find((doc) => doc.id === activeDocumentId);

  return (
    <div className={cn('flex items-center gap-1', className)}>
      {/* Left Scroll Button */}
      {showLeftScroll && (
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 flex-shrink-0"
          onClick={() => scroll('left')}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
      )}

      {/* Tabs Container */}
      <div
        ref={scrollContainerRef}
        className="flex items-center gap-1 overflow-x-auto scrollbar-hide flex-1"
        onScroll={checkScroll}
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        {visibleDocuments.map((doc) => {
          const isActive = doc.id === activeDocumentId;

          return (
            <div
              key={doc.id}
              className={cn(
                'group relative flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer transition-all flex-shrink-0',
                'border hover:bg-accent/50',
                isActive
                  ? 'bg-background border-primary text-foreground shadow-sm'
                  : 'bg-muted/30 border-transparent text-muted-foreground hover:text-foreground'
              )}
              onClick={() => !isActive && onDocumentChange(doc.id)}
            >
              {/* Document Icon */}
              <span className="text-base flex-shrink-0">
                {getDocumentIcon(doc.extension)}
              </span>

              {/* Document Name */}
              <span
                className={cn(
                  'text-sm font-medium truncate max-w-[180px]',
                  isActive && 'font-semibold'
                )}
                title={doc.name}
              >
                {doc.name.replace(/\.[^/.]+$/, '')} {/* Remove extension */}
              </span>

              {/* Entity Count Badge */}
              {doc.entityCount !== undefined && doc.entityCount > 0 && (
                <Badge
                  variant="secondary"
                  className={cn(
                    'h-5 px-1.5 text-xs flex-shrink-0',
                    isActive && 'bg-primary/10 text-primary'
                  )}
                >
                  {doc.entityCount}
                </Badge>
              )}

              {/* Close Button */}
              {onDocumentClose && documents.length > 1 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className={cn(
                    'h-5 w-5 p-0 ml-1 flex-shrink-0 rounded-sm',
                    'opacity-0 group-hover:opacity-100 transition-opacity',
                    'hover:bg-destructive/10 hover:text-destructive'
                  )}
                  onClick={(e) => {
                    e.stopPropagation();
                    onDocumentClose(doc.id);
                  }}
                >
                  <X className="h-3 w-3" />
                </Button>
              )}
            </div>
          );
        })}
      </div>

      {/* Right Scroll Button */}
      {showRightScroll && (
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 flex-shrink-0"
          onClick={() => scroll('right')}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      )}

      {/* Overflow Menu */}
      {overflowDocuments.length > 0 && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="h-8 px-2 flex-shrink-0 gap-1"
            >
              <MoreHorizontal className="h-4 w-4" />
              <Badge variant="secondary" className="h-5 px-1.5 text-xs">
                +{overflowDocuments.length}
              </Badge>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="max-w-[300px]">
            {overflowDocuments.map((doc) => (
              <DropdownMenuItem
                key={doc.id}
                onClick={() => onDocumentChange(doc.id)}
                className="flex items-center gap-2"
              >
                <span className="text-base">{getDocumentIcon(doc.extension)}</span>
                <span className="flex-1 truncate">{doc.name}</span>
                {doc.entityCount !== undefined && doc.entityCount > 0 && (
                  <Badge variant="secondary" className="h-5 px-1.5 text-xs">
                    {doc.entityCount}
                  </Badge>
                )}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}
