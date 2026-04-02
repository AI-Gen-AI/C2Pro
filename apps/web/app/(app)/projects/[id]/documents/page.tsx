'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, CheckCircle2, Clock, FileText, Loader2, Search, Trash2, Upload } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useProjectDocuments } from '@/hooks/useProjectDocuments';
import { useDeleteDocumentEndpointApiV1DocumentsDocumentIdDelete } from '@/lib/api/generated/documents/documents';
import { formatFileSize } from '@/types/document';
import { DocumentUploadDropzone } from '@/components/features/documents/DocumentUploadDropzone';
import { useProject } from '@/hooks/useProject';

type DocumentStatus = 'Analyzed' | 'Processing' | 'Uploaded' | 'Error';

function normalizeStatus(status: string): DocumentStatus {
  switch (status) {
    case 'parsed':
      return 'Analyzed';
    case 'processing':
      return 'Processing';
    case 'queued':
      return 'Uploaded';
    default:
      return 'Error';
  }
}

function getStatusIcon(status: DocumentStatus) {
  switch (status) {
    case 'Analyzed':
      return CheckCircle2;
    case 'Processing':
      return Clock;
    default:
      return AlertTriangle;
  }
}

function getStatusColor(status: DocumentStatus): string {
  switch (status) {
    case 'Analyzed':
      return 'bg-green-100 text-green-700 border-green-200';
    case 'Processing':
      return 'bg-blue-100 text-blue-700 border-blue-200';
    case 'Uploaded':
      return 'bg-gray-100 text-gray-700 border-gray-200';
    default:
      return 'bg-red-100 text-red-700 border-red-200';
  }
}

function labelType(type: string): string {
  if (!type) {
    return 'Document';
  }
  return type.charAt(0).toUpperCase() + type.slice(1);
}

export default function ProjectDocumentsPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const { data: project } = useProject(projectId);
  const { documents, loading, error, refetch } = useProjectDocuments(projectId);
  const deleteDocument = useDeleteDocumentEndpointApiV1DocumentsDocumentIdDelete();
  const projectName = project?.name?.trim() || projectId;

  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<{ id: string; name: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleUploadComplete = () => {
    setUploadDialogOpen(false);
    refetch();
  };

  const handleDeleteClick = (docId: string, docName: string) => {
    setDocumentToDelete({ id: docId, name: docName });
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!documentToDelete) return;
    setIsDeleting(true);
    try {
      await deleteDocument.mutateAsync({ documentId: documentToDelete.id });
      setDeleteDialogOpen(false);
      setDocumentToDelete(null);
      refetch();
    } catch (error) {
      console.error('Failed to delete document:', error);
    } finally {
      setIsDeleting(false);
    }
  };

  const rows = useMemo(
    () =>
      documents.map((doc) => ({
        id: doc.id,
        name: doc.name,
        type: labelType(doc.type || 'PDF'),
        status: normalizeStatus(doc.status ?? 'parsed'),
        uploadedAt: doc.uploadedAt,
        size: formatFileSize(doc.fileSize),
      })),
    [documents]
  );

  const typeOptions = useMemo(
    () => Array.from(new Set(rows.map((row) => row.type))).sort(),
    [rows]
  );

  const filteredRows = useMemo(
    () =>
      rows.filter((row) => {
        const matchesSearch = row.name.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesType = typeFilter === 'all' || row.type === typeFilter;
        const matchesStatus = statusFilter === 'all' || row.status === statusFilter;
        return matchesSearch && matchesType && matchesStatus;
      }),
    [rows, searchQuery, typeFilter, statusFilter]
  );

  const analyzedCount = rows.filter((row) => row.status === 'Analyzed').length;
  const processingCount = rows.filter((row) => row.status === 'Processing').length;
  const errorCount = rows.filter((row) => row.status === 'Error').length;
  const hasBackendDocuments = rows.length > 0;

  return (
    <div className="space-y-6" data-testid="documents-page">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push(`/projects/${projectId}`)}
            className="mb-2"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Project
          </Button>
          <h1 className="text-3xl font-bold tracking-tight">Documents</h1>
          <p className="text-muted-foreground">Project: {projectName}</p>
        </div>
        <Button onClick={() => setUploadDialogOpen(true)}>
          <Upload className="mr-2 h-4 w-4" />
          Upload Document
        </Button>
      </div>

      {/* Upload Dialog */}
      <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Upload Documents</DialogTitle>
          </DialogHeader>
          <DocumentUploadDropzone
            projectId={projectId}
            maxFileSizeBytes={50 * 1024 * 1024}
            onUploadComplete={handleUploadComplete}
          />
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={(open) => {
        if (!isDeleting) {
          setDeleteDialogOpen(open);
          if (!open) setDocumentToDelete(null);
        }
      }}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Delete Document</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{documentToDelete?.name}"? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setDeleteDialogOpen(false);
                setDocumentToDelete(null);
              }}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={isDeleting}
            >
              {isDeleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                'Delete'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          Failed to load documents: {error.message}
        </div>
      ) : null}

      <div className="flex items-center gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search documents..."
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="All Types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            {typeOptions.map((type) => (
              <SelectItem key={type} value={type}>
                {type}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="All Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="Analyzed">Analyzed</SelectItem>
            <SelectItem value="Processing">Processing</SelectItem>
            <SelectItem value="Uploaded">Uploaded</SelectItem>
            <SelectItem value="Error">Error</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Total Documents</p>
          <p className="text-2xl font-bold">{rows.length}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Analyzed</p>
          <p className="text-2xl font-bold text-green-600">{analyzedCount}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Processing</p>
          <p className="text-2xl font-bold text-blue-600">{processingCount}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Errors</p>
          <p className="text-2xl font-bold text-red-600">{errorCount}</p>
        </div>
      </div>

      <div className="rounded-lg border bg-card" data-testid="documents-list">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium">Document</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Type</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Status</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Size</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Upload Date</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    Loading documents...
                  </td>
                </tr>
              ) : filteredRows.length > 0 ? (
                filteredRows.map((doc) => {
                  const StatusIcon = getStatusIcon(doc.status);
                  return (
                    <tr key={doc.id} className="hover:bg-muted/50 transition-colors" data-testid={`document-row-${doc.id}`}>
                      <td className="px-4 py-3">
                        <Link
                          href={`/projects/${projectId}/evidence?documentId=${doc.id}`}
                          className="flex items-center gap-3 hover:underline"
                        >
                          <div className="rounded-lg bg-muted p-2">
                            <FileText className="h-5 w-5" />
                          </div>
                          <div>
                            <div className="font-medium" data-testid="document-name">{doc.name}</div>
                            <div className="text-sm text-muted-foreground">{doc.id}</div>
                          </div>
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" data-testid="document-type">{doc.type}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" className={getStatusColor(doc.status)}>
                          <StatusIcon className="mr-1 h-3 w-3" />
                          {doc.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">{doc.size}</td>
                      <td className="px-4 py-3 text-sm text-muted-foreground" data-testid="document-date">
                        {doc.uploadedAt ? new Date(doc.uploadedAt).toLocaleDateString() : '-'}
                      </td>
                      <td className="px-4 py-3">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-destructive hover:text-destructive hover:bg-destructive/10"
                          onClick={() => handleDeleteClick(doc.id, doc.name)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    {hasBackendDocuments
                      ? 'No documents match the current filters'
                      : 'No documents found for this project'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="text-sm text-muted-foreground">
        Showing {filteredRows.length} of {rows.length} documents
      </div>
    </div>
  );
}
