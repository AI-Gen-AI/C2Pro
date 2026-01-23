/**
 * RecentDocuments Component
 * Displays a list of recently accessed documents with quick navigation
 */

import { Clock, FileText, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import { getDocumentIcon, formatFileSize } from '@/types/document';

interface RecentDocument {
  id: string;
  name: string;
  type: string;
  extension: string;
  accessedAt: string;
  totalPages?: number;
  fileSize?: number;
}

interface RecentDocumentsProps {
  documents: RecentDocument[];
  currentDocumentId?: string;
  onDocumentSelect: (documentId: string) => void;
  onRemove?: (documentId: string) => void;
  onClearAll?: () => void;
  className?: string;
}

function formatTimeAgo(isoString: string): string {
  const now = new Date();
  const then = new Date(isoString);
  const diffMs = now.getTime() - then.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  return then.toLocaleDateString();
}

export function RecentDocuments({
  documents,
  currentDocumentId,
  onDocumentSelect,
  onRemove,
  onClearAll,
  className,
}: RecentDocumentsProps) {
  if (documents.length === 0) {
    return (
      <div className={cn('p-4 text-center', className)}>
        <Clock className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
        <p className="text-sm text-muted-foreground">No recent documents</p>
        <p className="text-xs text-muted-foreground mt-1">
          Documents you access will appear here
        </p>
      </div>
    );
  }

  return (
    <div className={cn('', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Recent Documents</span>
          <Badge variant="secondary" className="text-xs">
            {documents.length}
          </Badge>
        </div>
        {onClearAll && documents.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onClearAll}
            className="h-7 text-xs text-muted-foreground hover:text-foreground"
          >
            Clear all
          </Button>
        )}
      </div>

      {/* Document List */}
      <div className="max-h-[300px] overflow-y-auto">
        {documents.map((doc, index) => {
          const isActive = doc.id === currentDocumentId;

          return (
            <div key={doc.id}>
              <div
                className={cn(
                  'group flex items-center gap-3 px-4 py-3 hover:bg-muted/50 cursor-pointer transition-colors',
                  isActive && 'bg-muted border-l-2 border-l-primary'
                )}
                onClick={() => onDocumentSelect(doc.id)}
              >
                {/* Document Icon */}
                <div className="text-xl flex-shrink-0">
                  {getDocumentIcon(doc.extension)}
                </div>

                {/* Document Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p
                      className={cn(
                        'text-sm font-medium truncate',
                        isActive && 'text-primary'
                      )}
                    >
                      {doc.name}
                    </p>
                    {isActive && (
                      <Badge variant="default" className="text-xs h-5">
                        Current
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-muted-foreground">
                      {formatTimeAgo(doc.accessedAt)}
                    </span>
                    {doc.totalPages && (
                      <>
                        <span className="text-xs text-muted-foreground">•</span>
                        <span className="text-xs text-muted-foreground">
                          {doc.totalPages} pages
                        </span>
                      </>
                    )}
                    {doc.fileSize && (
                      <>
                        <span className="text-xs text-muted-foreground">•</span>
                        <span className="text-xs text-muted-foreground">
                          {formatFileSize(doc.fileSize)}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Remove Button */}
                {onRemove && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={(e) => {
                      e.stopPropagation();
                      onRemove(doc.id);
                    }}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                )}
              </div>

              {/* Separator between items (not after last) */}
              {index < documents.length - 1 && <Separator />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
