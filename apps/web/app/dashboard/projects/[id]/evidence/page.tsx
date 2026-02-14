"use client";

import { use, useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { AlertTriangle, CheckCircle, ChevronDown, Clock, Columns2, Database, Download, FileJson, FileText, RefreshCw } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/components/ui/resizable';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { EntityValidationList, ExtractedEntity } from '@/components/evidence';
import { useDocumentAlerts } from '@/hooks/useDocumentAlerts';
import { useDocumentEntities } from '@/hooks/useDocumentEntities';
import { useProjectDocuments } from '@/hooks/useProjectDocuments';
import { cn } from '@/lib/utils';

const PDFViewerPlaceholder = ({ fileName }: { fileName?: string }) => (
  <div className="flex h-full flex-col items-center justify-center gap-4 rounded-lg border-2 border-dashed border-border bg-muted/20 p-8">
    <FileText className="h-16 w-16 text-muted-foreground" />
    <div className="text-center">
      <h3 className="text-lg font-semibold">PDF Viewer</h3>
      <p className="mt-2 text-sm text-muted-foreground">Document highlights and navigation panel.</p>
      {fileName ? (
        <p className="mt-2 text-xs text-muted-foreground">Selected: {fileName}</p>
      ) : null}
    </div>
  </div>
);

interface EvidencePageProps {
  params: Promise<{
    id: string;
  }>;
}

function normalizeConfidence(value: number): number {
  if (value <= 1) {
    return Math.round(value * 100);
  }
  return Math.round(value);
}

function normalizeEntityType(value: string): string {
  if (!value) {
    return 'Entity';
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export default function EvidencePage({ params }: EvidencePageProps) {
  const { id } = use(params);
  const searchParams = useSearchParams();
  const requestedDocumentId = searchParams.get('documentId');

  const [splitView, setSplitView] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [activeEntityId, setActiveEntityId] = useState<string | null>(null);

  const {
    documents,
    loading: documentsLoading,
    error: documentsError,
    refetch: refetchDocuments,
  } = useProjectDocuments(id);

  useEffect(() => {
    if (documents.length === 0) {
      setSelectedDocumentId(null);
      return;
    }

    if (requestedDocumentId && documents.some((doc) => doc.id === requestedDocumentId)) {
      setSelectedDocumentId(requestedDocumentId);
      return;
    }

    if (!selectedDocumentId || !documents.some((doc) => doc.id === selectedDocumentId)) {
      setSelectedDocumentId(documents[0]?.id ?? null);
    }
  }, [documents, requestedDocumentId, selectedDocumentId]);

  const selectedDocument = useMemo(
    () => documents.find((doc) => doc.id === selectedDocumentId) ?? null,
    [documents, selectedDocumentId]
  );

  const {
    entities: apiEntities,
    loading: entitiesLoading,
    error: entitiesError,
    refetch: refetchEntities,
  } = useDocumentEntities(selectedDocumentId);
  const {
    alerts,
    loading: alertsLoading,
    error: alertsError,
    refetch: refetchAlerts,
  } = useDocumentAlerts(selectedDocumentId);

  const mappedEntities = useMemo<ExtractedEntity[]>(
    () =>
      apiEntities.map((entity) => ({
        id: entity.id,
        type: normalizeEntityType(entity.type),
        text: entity.text,
        confidence: normalizeConfidence(entity.confidence),
        page: entity.page,
        validationStatus: 'pending',
      })),
    [apiEntities]
  );

  const [entities, setEntities] = useState<ExtractedEntity[]>([]);

  useEffect(() => {
    setEntities(mappedEntities);
  }, [mappedEntities]);

  const handleApproveEntity = useCallback((entityId: string) => {
    setEntities((prev) =>
      prev.map((entity) =>
        entity.id === entityId
          ? { ...entity, validationStatus: 'approved', validated: true }
          : entity
      )
    );
  }, []);

  const handleRejectEntity = useCallback((entityId: string, reason: string) => {
    setEntities((prev) =>
      prev.map((entity) =>
        entity.id === entityId
          ? {
              ...entity,
              validationStatus: 'rejected',
              validated: false,
              rejectionReason: reason,
            }
          : entity
      )
    );
  }, []);

  const handleEntityClick = useCallback((entity: ExtractedEntity) => {
    setActiveEntityId(entity.id);
  }, []);

  const handleRefresh = useCallback(async () => {
    await Promise.all([refetchDocuments(), refetchEntities(), refetchAlerts()]);
  }, [refetchDocuments, refetchEntities, refetchAlerts]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Evidence Viewer</h1>
          <p className="text-muted-foreground">Project: {id}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void handleRefresh()}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Download className="mr-2 h-4 w-4" />
                Export
                <ChevronDown className="ml-2 h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem>
                <FileJson className="mr-2 h-4 w-4" />
                Export JSON
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Database className="mr-2 h-4 w-4" />
                Export CSV
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            variant={splitView ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSplitView((value) => !value)}
          >
            <Columns2 className="mr-2 h-4 w-4" />
            Split View
          </Button>
        </div>
      </div>

      {documentsError ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          Failed to load documents: {documentsError.message}
        </div>
      ) : null}

      <ResizablePanelGroup direction="horizontal" className="min-h-[calc(100vh-12rem)]">
        <ResizablePanel defaultSize={splitView ? 50 : 70} minSize={30}>
          <Card className="h-full">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  {selectedDocument?.name ?? 'No document selected'}
                </CardTitle>
                {selectedDocument ? <Badge variant="outline">{selectedDocument.type}</Badge> : null}
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <PDFViewerPlaceholder fileName={selectedDocument?.name} />
            </CardContent>
          </Card>
        </ResizablePanel>

        <ResizableHandle withHandle />

        <ResizablePanel defaultSize={splitView ? 50 : 30} minSize={20}>
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Extracted Entities</CardTitle>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="entities" className="w-full">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="entities">Entities</TabsTrigger>
                  <TabsTrigger value="alerts">Alerts</TabsTrigger>
                  <TabsTrigger value="search">Search</TabsTrigger>
                </TabsList>

                <TabsContent value="entities" className="space-y-4">
                  {entitiesError ? (
                    <Alert>
                      <AlertTriangle className="h-4 w-4" />
                      <AlertDescription>
                        Failed to load entities: {entitiesError.message}
                      </AlertDescription>
                    </Alert>
                  ) : (
                    <EntityValidationList
                      entities={entities}
                      onApprove={handleApproveEntity}
                      onReject={handleRejectEntity}
                      onEntityClick={handleEntityClick}
                      activeEntityId={activeEntityId}
                      isLoading={entitiesLoading}
                    />
                  )}
                </TabsContent>

                <TabsContent value="alerts" className="space-y-4">
                  {alertsError ? (
                    <Alert>
                      <AlertDescription>Failed to load alerts: {alertsError.message}</AlertDescription>
                    </Alert>
                  ) : alertsLoading ? (
                    <Alert>
                      <AlertDescription>Loading alerts...</AlertDescription>
                    </Alert>
                  ) : alerts.length === 0 ? (
                    <Alert>
                      <AlertDescription>No alerts for this document.</AlertDescription>
                    </Alert>
                  ) : (
                    <div className="space-y-2">
                      {alerts.map((alert) => (
                        <div key={alert.id} className="rounded-md border p-3">
                          <p className="font-medium">{alert.title}</p>
                          <p className="text-sm text-muted-foreground">{alert.description}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="search" className="space-y-4">
                  <Alert>
                    <AlertDescription>Search highlights becomes available with PDF viewer integration.</AlertDescription>
                  </Alert>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </ResizablePanel>
      </ResizablePanelGroup>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Project Documents
          </CardTitle>
        </CardHeader>
        <CardContent>
          {documentsLoading ? (
            <p className="text-sm text-muted-foreground">Loading documents...</p>
          ) : documents.length === 0 ? (
            <p className="text-sm text-muted-foreground">No documents available for this project.</p>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {documents.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => setSelectedDocumentId(doc.id)}
                  className={cn(
                    'flex items-center gap-3 rounded-lg border p-4 text-left transition-colors',
                    selectedDocumentId === doc.id
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-primary/50'
                  )}
                >
                  <FileText className="h-8 w-8 text-muted-foreground" />
                  <div className="flex-1">
                    <p className="font-medium text-sm">{doc.name}</p>
                    <p className="text-xs text-muted-foreground">{doc.id}</p>
                  </div>
                  {selectedDocumentId === doc.id ? (
                    <CheckCircle className="h-5 w-5 text-primary" />
                  ) : null}
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
