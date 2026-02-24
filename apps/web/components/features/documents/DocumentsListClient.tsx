'use client';

import { type ChangeEvent, useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import {
  FileText,
  Upload,
  Search,
  Download,
  Eye,
  MoreVertical,
  FileSpreadsheet,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  FolderOpen,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type {
  DocumentListItem,
  DocumentPollingStatus,
  ProjectDocumentsGroup,
} from '@/lib/api/generated/models';

interface DocumentsListClientProps {
  groups: ProjectDocumentsGroup[];
}

const STATUS_LABELS: Record<DocumentPollingStatus, string> = {
  parsed: 'Analyzed',
  processing: 'Processing',
  queued: 'Queued',
  error: 'Error',
};

function getStatusIcon(status: DocumentPollingStatus) {
  switch (status) {
    case 'parsed':
      return CheckCircle2;
    case 'processing':
      return Clock;
    case 'queued':
      return Loader2;
    case 'error':
      return AlertTriangle;
    default:
      return FileText;
  }
}

function getStatusColor(status: DocumentPollingStatus) {
  switch (status) {
    case 'parsed':
      return 'bg-green-100 text-green-700 border-green-200';
    case 'processing':
      return 'bg-blue-100 text-blue-700 border-blue-200';
    case 'queued':
      return 'bg-gray-100 text-gray-700 border-gray-200';
    case 'error':
      return 'bg-red-100 text-red-700 border-red-200';
    default:
      return 'bg-gray-100 text-gray-700 border-gray-200';
  }
}

function getTypeColor(docType: string | null | undefined) {
  switch (docType) {
    case 'contract':
      return 'bg-blue-100 text-blue-700';
    case 'schedule':
      return 'bg-orange-100 text-orange-700';
    case 'budget':
      return 'bg-green-100 text-green-700';
    case 'specification':
      return 'bg-purple-100 text-purple-700';
    default:
      return 'bg-gray-100 text-gray-700';
  }
}

function getFileIcon(filename: string) {
  if (filename.endsWith('.xlsx') || filename.endsWith('.xls')) return FileSpreadsheet;
  return FileText;
}

function formatFileSize(bytes: number | null | undefined): string {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function DocumentsListClient({ groups }: DocumentsListClientProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const allDocuments = groups.flatMap((g) => g.documents);

  // Filter documents within each group
  const filteredGroups = groups
    .map((group) => ({
      ...group,
      documents: group.documents.filter((doc) => {
        const matchesSearch = doc.filename
          .toLowerCase()
          .includes(searchQuery.toLowerCase());
        const matchesStatus =
          statusFilter === 'all' || doc.status === statusFilter;
        return matchesSearch && matchesStatus;
      }),
    }))
    .filter((group) => group.documents.length > 0);

  const filteredCount = filteredGroups.reduce(
    (sum, g) => sum + g.documents.length,
    0
  );

  return (
    <>
      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search documents..."
            value={searchQuery}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="All Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="parsed">Analyzed</SelectItem>
            <SelectItem value="processing">Processing</SelectItem>
            <SelectItem value="queued">Queued</SelectItem>
            <SelectItem value="error">Error</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Total Documents</p>
          <p className="text-2xl font-bold">{allDocuments.length}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Analyzed</p>
          <p className="text-2xl font-bold text-green-600">
            {allDocuments.filter((d) => d.status === 'parsed').length}
          </p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Processing</p>
          <p className="text-2xl font-bold text-blue-600">
            {allDocuments.filter((d) => d.status === 'processing' || d.status === 'queued').length}
          </p>
        </div>
      </div>

      {/* Documents Grouped by Project */}
      <div className="space-y-4">
        {filteredGroups.length === 0 ? (
          <div className="rounded-md border bg-card px-4 py-8 text-center text-sm text-muted-foreground">
            No documents found.
          </div>
        ) : (
          <Accordion
            type="multiple"
            className="space-y-4"
            defaultValue={filteredGroups.map((g) => g.projectId)}
          >
            {filteredGroups.map((group) => (
              <AccordionItem
                key={group.projectId}
                value={group.projectId}
                className="rounded-lg border bg-card"
              >
                <AccordionTrigger className="px-4 py-3 hover:no-underline">
                  <div className="flex items-center gap-3">
                    <FolderOpen className="h-5 w-5 text-muted-foreground" />
                    <div className="text-left">
                      <div className="font-semibold">{group.projectName}</div>
                      <div className="text-sm text-muted-foreground">
                        {group.documents.length} document
                        {group.documents.length !== 1 ? 's' : ''}
                      </div>
                    </div>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="px-0 pb-0">
                  <div className="border-t">
                    <table className="w-full">
                      <thead className="border-b bg-muted/30">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">
                            Document
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">
                            Type
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">
                            Status
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">
                            Size
                          </th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">
                            Date
                          </th>
                          <th className="px-4 py-2"></th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {group.documents.map((doc) => {
                          const Icon = getFileIcon(doc.filename);
                          const StatusIcon = getStatusIcon(doc.status);
                          return (
                            <tr
                              key={doc.id}
                              className="hover:bg-muted/50 transition-colors"
                            >
                              <td className="px-4 py-3">
                                <Link
                                  href={`/projects/${doc.project_id}/evidence/${doc.id}`}
                                  className="flex items-center gap-3 hover:underline"
                                >
                                  <div className="rounded-lg bg-muted p-2">
                                    <Icon className="h-4 w-4" />
                                  </div>
                                  <div>
                                    <div className="font-medium text-sm">
                                      {doc.filename}
                                    </div>
                                    <div className="text-xs text-muted-foreground">
                                      {doc.id}
                                    </div>
                                  </div>
                                </Link>
                              </td>
                              <td className="px-4 py-3">
                                {doc.document_type ? (
                                  <Badge
                                    className={getTypeColor(doc.document_type)}
                                    variant="secondary"
                                  >
                                    {doc.document_type}
                                  </Badge>
                                ) : (
                                  <span className="text-sm text-muted-foreground">
                                    —
                                  </span>
                                )}
                              </td>
                              <td className="px-4 py-3">
                                <Badge
                                  variant="outline"
                                  className={getStatusColor(doc.status)}
                                >
                                  <StatusIcon className="mr-1 h-3 w-3" />
                                  {STATUS_LABELS[doc.status] ?? doc.status}
                                </Badge>
                              </td>
                              <td className="px-4 py-3 text-sm text-muted-foreground">
                                {formatFileSize(doc.file_size_bytes)}
                              </td>
                              <td className="px-4 py-3 text-sm text-muted-foreground">
                                {formatDate(doc.uploaded_at)}
                              </td>
                              <td className="px-4 py-3">
                                <div className="flex items-center gap-1">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-8 w-8"
                                  >
                                    <Eye className="h-4 w-4" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-8 w-8"
                                  >
                                    <Download className="h-4 w-4" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-8 w-8"
                                  >
                                    <MoreVertical className="h-4 w-4" />
                                  </Button>
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        )}
      </div>

      <div className="text-sm text-muted-foreground">
        Showing {filteredCount} documents across{' '}
        {filteredGroups.length} project
        {filteredGroups.length !== 1 ? 's' : ''}
      </div>
    </>
  );
}
