"use client";

import { useState } from 'react';
import { EntityValidationCard, ExtractedEntity } from './EntityValidationCard';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  CheckCircle,
  XCircle,
  Clock,
  Search,
  Filter,
  AlertTriangle,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface EntityValidationListProps {
  entities: ExtractedEntity[];
  onApprove: (entityId: string) => void;
  onReject: (entityId: string, reason: string) => void;
  onEntityClick?: (entity: ExtractedEntity) => void;
  activeEntityId?: string | null;
  isLoading?: boolean;
}

type FilterStatus = 'all' | 'pending' | 'approved' | 'rejected';

export function EntityValidationList({
  entities,
  onApprove,
  onReject,
  onEntityClick,
  activeEntityId,
  isLoading = false,
}: EntityValidationListProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<FilterStatus>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');

  // Get unique entity types for filter
  const entityTypes = Array.from(new Set(entities.map((e) => e.type)));

  // Calculate stats
  const stats = {
    total: entities.length,
    pending: entities.filter((e) => !e.validationStatus || e.validationStatus === 'pending').length,
    approved: entities.filter((e) => e.validationStatus === 'approved').length,
    rejected: entities.filter((e) => e.validationStatus === 'rejected').length,
  };

  // Filter entities
  const filteredEntities = entities.filter((entity) => {
    // Search filter
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      const matchesSearch =
        entity.text.toLowerCase().includes(search) ||
        entity.type.toLowerCase().includes(search) ||
        (entity.originalText?.toLowerCase().includes(search) ?? false);
      if (!matchesSearch) return false;
    }

    // Status filter
    if (statusFilter !== 'all') {
      const entityStatus = entity.validationStatus || 'pending';
      if (entityStatus !== statusFilter) return false;
    }

    // Type filter
    if (typeFilter !== 'all' && entity.type !== typeFilter) return false;

    return true;
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading entities...</span>
      </div>
    );
  }

  if (entities.length === 0) {
    return (
      <Alert>
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>No entities found</AlertTitle>
        <AlertDescription>
          No extracted entities available for this document.
          <br />
          <span className="text-xs text-muted-foreground">
            Entities will be extracted automatically from the document content.
          </span>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      {/* Stats Bar */}
      <div className="flex items-center gap-2 flex-wrap">
        <Badge variant="outline" className="gap-1">
          <Clock className="h-3 w-3" />
          {stats.pending} Pending
        </Badge>
        <Badge variant="outline" className="gap-1 text-green-600 border-green-200">
          <CheckCircle className="h-3 w-3" />
          {stats.approved} Approved
        </Badge>
        <Badge variant="outline" className="gap-1 text-red-600 border-red-200">
          <XCircle className="h-3 w-3" />
          {stats.rejected} Rejected
        </Badge>
        <span className="text-xs text-muted-foreground ml-auto">
          {stats.total} total entities
        </span>
      </div>

      {/* Search and Filters */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search entities..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-8"
          />
        </div>
        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as FilterStatus)}>
          <SelectTrigger className="w-[130px]">
            <Filter className="mr-2 h-4 w-4" />
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="rejected">Rejected</SelectItem>
          </SelectContent>
        </Select>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            {entityTypes.map((type) => (
              <SelectItem key={type} value={type}>
                {type}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Filtered Results Count */}
      {filteredEntities.length !== entities.length && (
        <p className="text-xs text-muted-foreground">
          Showing {filteredEntities.length} of {entities.length} entities
        </p>
      )}

      {/* Entity List */}
      <ScrollArea className="h-[calc(100vh-24rem)]">
        <div className="space-y-3 pr-4">
          {filteredEntities.length === 0 ? (
            <Alert>
              <AlertDescription>
                No entities match your current filters. Try adjusting your search or filters.
              </AlertDescription>
            </Alert>
          ) : (
            filteredEntities.map((entity) => (
              <EntityValidationCard
                key={entity.id}
                entity={entity}
                onApprove={onApprove}
                onReject={onReject}
                onEntityClick={onEntityClick}
                isActive={activeEntityId === entity.id}
              />
            ))
          )}
        </div>
      </ScrollArea>

      {/* Quick Actions */}
      {stats.pending > 0 && (
        <div className="pt-3 border-t">
          <p className="text-xs text-muted-foreground mb-2">
            Quick Actions (Gate 6 compliant - requires individual confirmation)
          </p>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              className="text-green-600"
              onClick={() => {
                // Navigate to first pending entity
                const firstPending = entities.find(
                  (e) => !e.validationStatus || e.validationStatus === 'pending'
                );
                if (firstPending) onEntityClick?.(firstPending);
              }}
            >
              Review Next Pending
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
