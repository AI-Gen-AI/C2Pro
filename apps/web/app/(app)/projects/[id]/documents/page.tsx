'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, CheckCircle2, Clock, FileText, Loader2, RefreshCw, Search, Trash2, Upload } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { statusToToken } from '@/lib/ui/severity-tokens';
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
import { AnalysisProgressTracker } from '@/components/features/analysis/AnalysisProgressTracker';
import { TripletChecklist, type TripletSlotType } from '@/components/features/documents/TripletChecklist';
import { useProjectDocuments } from '@/hooks/useProjectDocuments';
import { useProjectCoherenceActions } from '@/hooks/useProjectCoherenceActions';
import { apiClient } from '@/lib/api/client';
import { useDeleteDocumentEndpointApiV1DocumentsDocumentIdDelete } from '@/lib/api/generated/documents/documents';
import { showToast } from '@/lib/ui/toast';
import { formatFileSize, type DocumentLifecycleStatus } from '@/types/document';
import { DocumentUploadDropzone } from '@/components/features/documents/DocumentUploadDropzone';
import { useProject } from '@/hooks/useProject';

const LIFECYCLE_LABELS: Record<DocumentLifecycleStatus, string> = {
  uploaded: 'Uploaded',
  processing: 'Processing',
  parsed: 'Parsed',
  analysis_pending: 'Analysis pending',
  analyzed: 'Analyzed',
  error: 'Error',
};

const LIFECYCLE_ORDER = Object.keys(LIFECYCLE_LABELS) as DocumentLifecycleStatus[];

function isLifecycleStatus(value: string | undefined): value is DocumentLifecycleStatus {
  return value !== undefined && Object.prototype.hasOwnProperty.call(LIFECYCLE_LABELS, value);
}

/**
 * The backend lifecycle state when present. Older payloads only carry the polling status,
 * whose "parsed" bucket includes documents never analyzed, so they never resolve to "analyzed".
 */
function resolveLifecycle(
  lifecycleStatus: DocumentLifecycleStatus | undefined,
  status: string,
): DocumentLifecycleStatus {
  if (isLifecycleStatus(lifecycleStatus)) {
    return lifecycleStatus;
  }
  switch (status) {
    case 'processing':
      return 'processing';
    case 'parsed':
      return 'parsed';
    case 'error':
      return 'error';
    default:
      return 'uploaded';  // queued or unknown → treat as queued, not errored
  }
}

function getStatusIcon(status: DocumentLifecycleStatus) {
  switch (status) {
    case 'analyzed':
      return CheckCircle2;
    case 'error':
      return AlertTriangle;
    default:
      return Clock;
  }
}

function getStatusColor(status: DocumentLifecycleStatus): string {
  // Parsed / pending documents are not finished: keep them neutral, not success-green.
  return statusToToken(status === 'parsed' || status === 'analysis_pending' ? 'uploaded' : status);
}

function labelType(type: string): string {
  if (!type) {
    return 'Document';
  }
  return type.charAt(0).toUpperCase() + type.slice(1);
}

function sortedUniqueTypes(rows: Array<{ type: string }>) {
  const types = new Set<string>();

  for (const row of rows) {
    types.add(row.type);
  }

  return Array.from(types).sort();
}

function isInFlightStatus(status: string | undefined): boolean {
  return ['uploaded', 'queued', 'processing'].includes(
    String(status ?? '').toLowerCase(),
  );
}

function mutationFailureMessage(error: unknown, fallback: string): string {
  const maybeResponse = error as {
    response?: { data?: { detail?: unknown } };
  };
  const detail = maybeResponse.response?.data?.detail;

  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  return error instanceof Error && error.message
    ? error.message
    : fallback;
}

export default function ProjectDocumentsPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const { data: project } = useProject(projectId);
  const { documents, loading, error, refetch } = useProjectDocuments(projectId);
  const { evaluateCoherence, isEvaluating } = useProjectCoherenceActions(projectId);
  const deleteDocument = useDeleteDocumentEndpointApiV1DocumentsDocumentIdDelete();
  const projectName = project?.name?.trim() || projectId;

  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<{ id: string; name: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [retryingDocumentId, setRetryingDocumentId] = useState<string | null>(null);
  const [defaultUploadType, setDefaultUploadType] = useState<TripletSlotType | null>(null);
  const [versionTarget, setVersionTarget] = useState<{ id: string; name: string } | null>(null);
  const [versionFile, setVersionFile] = useState<File | null>(null);
  const [isUploadingVersion, setIsUploadingVersion] = useState(false);

  // A new version keeps the same logical document: the backend appends an immutable revision
  // and re-processes it. Uploading through "Upload Document" instead would create a second
  // document and break the revision history.
  const handleUploadNewVersion = async () => {
    if (!versionTarget || !versionFile) return;
    setIsUploadingVersion(true);
    try {
      const formData = new FormData();
      formData.append('file', versionFile);
      await apiClient.patch(`/documents/${versionTarget.id}/file`, formData);
      setVersionTarget(null);
      setVersionFile(null);
      await refetch();
    } catch (error) {
      showToast(mutationFailureMessage(error, 'Failed to upload the new version.'));
    } finally {
      setIsUploadingVersion(false);
    }
  };

  const handleRetryProcessing = async (docId: string) => {
    setRetryingDocumentId(docId);
    try {
      await apiClient.post(`/projects/${projectId}/documents/${docId}/reprocess`);
      await refetch();
    } catch (error) {
      showToast(mutationFailureMessage(error, 'Failed to retry document processing.'));
    } finally {
      setRetryingDocumentId(null);
    }
  };

  const handleUploadComplete = () => {
    setUploadDialogOpen(false);
    setDefaultUploadType(null);
    refetch();
  };

  const handleOpenUploadDialog = (type?: TripletSlotType) => {
    setDefaultUploadType(type ?? null);
    setUploadDialogOpen(true);
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
      showToast(mutationFailureMessage(error, 'Failed to delete document.'));
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
        status: resolveLifecycle(doc.lifecycleStatus, doc.status ?? 'parsed'),
        // Retry follows the polling status exactly as before: a stored "queued" document is
        // already being processed, and reprocessing it would enqueue a duplicate task.
        retryable: !(['processing', 'parsed', 'analyzed', 'parsed_pending_analysis'] as string[]).includes(
          doc.status ?? 'parsed',
        ),
        uploadedAt: doc.uploadedAt,
        size: formatFileSize(doc.fileSize),
      })),
    [documents]
  );

  const typeOptions = useMemo(
    () => sortedUniqueTypes(rows),
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

  const analyzedCount = rows.filter((row) => row.status === 'analyzed').length;
  const awaitingAnalysisCount = rows.filter(
    (row) => row.status === 'parsed' || row.status === 'analysis_pending',
  ).length;
  const inProgressCount = rows.filter(
    (row) => row.status === 'uploaded' || row.status === 'processing',
  ).length;
  const errorCount = rows.filter((row) => row.status === 'error').length;
  const hasBackendDocuments = rows.length > 0;
  const hasInFlightDocuments = documents.some((doc) =>
    isInFlightStatus(doc.status),
  );

  return (
    <div className="space-y-6" data-testid="documents-page">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="space-y-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push(`/projects/${projectId}`)}
            className="mb-2 rounded-xl bg-background/95 shadow-sm"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Project
          </Button>
          <h1 className="text-3xl font-bold tracking-tight">Documents</h1>
          <p className="text-muted-foreground">Project: {projectName}</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="rounded-full border bg-background/95 px-3 py-1 text-xs font-medium text-foreground shadow-sm">
              {rows.length} total documents
            </span>
            <span className="rounded-full border bg-background/95 px-3 py-1 text-xs text-muted-foreground shadow-sm">
              {analyzedCount} analyzed
            </span>
          </div>
        </div>
        <Button className="rounded-xl shadow-sm" onClick={() => handleOpenUploadDialog()}>
          <Upload className="mr-2 h-4 w-4" />
          Upload Document
        </Button>
      </div>

      {hasInFlightDocuments ? (
        <AnalysisProgressTracker projectId={projectId} />
      ) : null}

      <TripletChecklist
        documents={documents}
        coherenceHref={`/projects/${projectId}/coherence`}
        onUploadType={handleOpenUploadDialog}
        onEvaluateCoherence={() => void evaluateCoherence()}
        evaluatePending={isEvaluating}
      />

      {/* Upload Dialog */}
      <Dialog
        open={uploadDialogOpen}
        onOpenChange={(open) => {
          setUploadDialogOpen(open);
          if (!open) {
            setDefaultUploadType(null);
          }
        }}
      >
        <DialogContent
          className="gap-5 bg-card p-6 text-card-foreground sm:max-w-[680px] sm:rounded-[28px]"
          data-testid="documents-upload-dialog-shell"
        >
          <DialogHeader className="rounded-[24px] border border-border/70 bg-muted/70 px-5 py-5">
            <DialogTitle>Upload Documents</DialogTitle>
            <DialogDescription>
              Files will be scoped to{" "}
              <span className="font-medium text-foreground">{projectName}</span> and will
              appear in the document register once queued. Choose each file role before
              upload: contract, budget, or schedule.
            </DialogDescription>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="rounded-full border bg-background px-3 py-1 text-xs font-medium text-foreground shadow-sm">
                PDF, XLSX, BC3
              </span>
              <span className="rounded-full border bg-background px-3 py-1 text-xs text-muted-foreground shadow-sm">
                Max 50 MB each
              </span>
            </div>
          </DialogHeader>
          <DocumentUploadDropzone
            projectId={projectId}
            maxFileSizeBytes={50 * 1024 * 1024}
            defaultType={defaultUploadType ?? undefined}
            onUploadComplete={handleUploadComplete}
          />
        </DialogContent>
      </Dialog>

      {/* Upload New Version Dialog */}
      <Dialog
        open={versionTarget !== null}
        onOpenChange={(open) => {
          if (!open && !isUploadingVersion) {
            setVersionTarget(null);
            setVersionFile(null);
          }
        }}
      >
        <DialogContent className="bg-card p-6 text-card-foreground sm:max-w-[480px] sm:rounded-2xl" data-testid="document-new-version-dialog">
          <DialogHeader className="rounded-2xl border bg-muted/70 px-4 py-4">
            <DialogTitle>Upload a new version of {versionTarget?.name}</DialogTitle>
            <DialogDescription>
              The document keeps its identity. Previous versions are kept as immutable revisions, and the new
              version is processed again before its changes appear in What Changed?.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="document-new-version-file">
              New version file
            </label>
            <Input
              id="document-new-version-file"
              type="file"
              data-testid="document-new-version-input"
              onChange={(event) => setVersionFile(event.target.files?.[0] ?? null)}
            />
          </div>
          <DialogFooter className="gap-2 rounded-2xl border bg-background/80 px-4 py-4">
            <Button
              variant="outline"
              disabled={isUploadingVersion}
              onClick={() => {
                setVersionTarget(null);
                setVersionFile(null);
              }}
            >
              Cancel
            </Button>
            <Button
              disabled={!versionFile || isUploadingVersion}
              onClick={() => void handleUploadNewVersion()}
            >
              {isUploadingVersion ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Upload new version
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={(open) => {
        if (!isDeleting) {
          setDeleteDialogOpen(open);
          if (!open) setDocumentToDelete(null);
        }
      }}>
        <DialogContent className="bg-card p-6 text-card-foreground sm:max-w-[425px] sm:rounded-2xl">
          <DialogHeader className="rounded-2xl border bg-muted/70 px-4 py-4">
            <DialogTitle>Delete Document</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{documentToDelete?.name}"? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 rounded-2xl border bg-background/80 px-4 py-4">
            <Button
              className="rounded-xl"
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
              className="rounded-xl"
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

      <section className="rounded-2xl border bg-card/80 p-4 shadow-sm">
        <div
          className="flex flex-wrap items-center gap-3 rounded-2xl border bg-background/70 p-3 shadow-sm"
          data-testid="documents-filter-toolbar"
        >
          <div className="relative min-w-[260px] flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search documents..."
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              className="h-11 rounded-xl border-border/80 bg-background/95 pl-9"
            />
          </div>
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="h-11 w-full min-w-[180px] rounded-xl border-border/80 bg-background/95 shadow-sm sm:w-[200px]">
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
            <SelectTrigger className="h-11 w-full min-w-[180px] rounded-xl border-border/80 bg-background/95 shadow-sm sm:w-[200px]">
              <SelectValue placeholder="All Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              {LIFECYCLE_ORDER.map((lifecycle) => (
                <SelectItem key={lifecycle} value={lifecycle}>
                  {LIFECYCLE_LABELS[lifecycle]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div
          className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border/60 pt-4"
          data-testid="documents-results-summary"
        >
          <div className="flex flex-wrap items-center gap-2">
            {typeFilter !== 'all' ? (
              <span className="rounded-full border bg-background/95 px-3 py-1 text-xs text-foreground shadow-sm">
                Type: {typeFilter}
              </span>
            ) : null}
            {statusFilter !== 'all' ? (
              <span className="rounded-full border bg-background/95 px-3 py-1 text-xs text-foreground shadow-sm">
                Status: {isLifecycleStatus(statusFilter) ? LIFECYCLE_LABELS[statusFilter] : statusFilter}
              </span>
            ) : null}
          </div>
          <span className="text-xs text-muted-foreground">
            Showing {filteredRows.length} of {rows.length} documents
          </span>
        </div>
      </section>

      <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-5">
        <section className="rounded-2xl border bg-background/90 p-4 shadow-sm" aria-label="Total Documents">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Total Documents</p>
          <p className="mt-3 text-2xl font-semibold tracking-tight text-foreground">{rows.length}</p>
        </section>
        <section className="rounded-2xl border border-green-200 bg-green-50/40 p-4 shadow-sm" aria-label="Analyzed">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-green-800">Analyzed</p>
          <p className="mt-3 text-2xl font-semibold tracking-tight text-green-700">{analyzedCount}</p>
        </section>
        <section className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4 shadow-sm" aria-label="Awaiting Analysis">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-700">Awaiting Analysis</p>
          <p className="mt-3 text-2xl font-semibold tracking-tight text-slate-900">{awaitingAnalysisCount}</p>
        </section>
        <section className="rounded-2xl border border-blue-200 bg-blue-50/40 p-4 shadow-sm" aria-label="Uploaded Or Processing">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-800">Uploaded / Processing</p>
          <p className="mt-3 text-2xl font-semibold tracking-tight text-blue-700">{inProgressCount}</p>
        </section>
        <section className="rounded-2xl border border-red-200 bg-red-50/40 p-4 shadow-sm" aria-label="Errors">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-red-800">Errors</p>
          <p className="mt-3 text-2xl font-semibold tracking-tight text-red-700">{errorCount}</p>
        </section>
      </div>

      <div className="overflow-hidden rounded-2xl border bg-card shadow-sm" data-testid="documents-list">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b bg-muted/30">
              <tr>
                <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Document</th>
                <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Type</th>
                <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Status</th>
                <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Size</th>
                <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Upload Date</th>
                <th className="px-4 py-4 text-right text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Actions</th>
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
                    <tr key={doc.id} className="transition-colors hover:bg-muted/20" data-testid={`document-row-${doc.id}`}>
                      <td className="px-4 py-4">
                        <Link
                          href={`/projects/${projectId}/evidence?documentId=${doc.id}`}
                          className="flex items-center gap-3"
                        >
                          <div className="rounded-xl border bg-background/95 p-2 shadow-sm">
                            <FileText className="h-5 w-5" />
                          </div>
                          <div>
                            <div className="font-medium text-foreground hover:text-primary" data-testid="document-name">{doc.name}</div>
                            <div className="text-sm text-muted-foreground">{doc.id}</div>
                          </div>
                        </Link>
                      </td>
                      <td className="px-4 py-4">
                        <Badge variant="outline" className="rounded-full bg-background/95 shadow-sm" data-testid="document-type">{doc.type}</Badge>
                      </td>
                      <td className="px-4 py-4">
                        <Badge variant="outline" className={`rounded-full shadow-sm ${getStatusColor(doc.status)}`}>
                          <StatusIcon className="mr-1 h-3 w-3" />
                          {LIFECYCLE_LABELS[doc.status]}
                        </Badge>
                      </td>
                      <td className="px-4 py-4 text-sm text-muted-foreground">{doc.size}</td>
                      <td className="px-4 py-4 text-sm text-muted-foreground" data-testid="document-date">
                        {doc.uploadedAt ? new Date(doc.uploadedAt).toLocaleDateString() : '-'}
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center justify-end gap-2">
                          {doc.retryable && (
                            <Button
                              variant="outline"
                              size="sm"
                              aria-label={`Retry processing ${doc.name}`}
                              className="rounded-xl bg-background/95 shadow-sm"
                              disabled={retryingDocumentId === doc.id}
                              onClick={() => void handleRetryProcessing(doc.id)}
                            >
                              {retryingDocumentId === doc.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <RefreshCw className="h-4 w-4" />
                              )}
                            </Button>
                          )}
                          <Button
                            variant="outline"
                            size="sm"
                            aria-label={`Upload new version of ${doc.name}`}
                            className="rounded-xl bg-background/95 shadow-sm"
                            onClick={() => {
                              setVersionFile(null);
                              setVersionTarget({ id: doc.id, name: doc.name });
                            }}
                          >
                            <Upload className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            aria-label={`Delete ${doc.name}`}
                            className="rounded-xl bg-background/95 text-destructive shadow-sm hover:bg-destructive/10 hover:text-destructive"
                            onClick={() => handleDeleteClick(doc.id, doc.name)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
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
    </div>
  );
}
