"use client";

import { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import '@/components/pdf/pdf-viewer.css';

const HighlightSearchBarPlaceholder = () => (
  <div className="rounded-lg border border-border p-4 text-center">
    <p className="text-sm text-muted-foreground">
      Búsqueda de highlights disponible cuando el PDF Viewer esté activo
    </p>
  </div>
);
import { cn } from '@/lib/utils';
import { useDocumentAlerts } from '@/hooks/useDocumentAlerts';
import { useDocumentBlob } from '@/hooks/useDocumentBlob';
import { useProjectDocuments } from '@/hooks/useProjectDocuments';
import {
  Download,
  CheckCircle,
  FileText,
  RefreshCw,
  Database,
  FileJson,
  ChevronDown,
  Clock,
  Columns2,
} from 'lucide-react';

const PDFViewer = dynamic(
  () => import('@/components/pdf/PDFViewer').then((mod) => mod.PDFViewer),
  {
    ssr: false,
    loading: () => <Skeleton className="h-full w-full" />,
  }
);

interface EvidencePageProps {
  params: {
    id: string;
  };
}

export default function EvidencePage({ params }: EvidencePageProps) {
  const {
    documents,
    loading: documentsLoading,
    error: documentsError,
    refetch: refetchDocuments,
  } = useProjectDocuments(params.id);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
    null
  );
  const [activeHighlightId, setActiveHighlightId] = useState<string | null>(null);
  const [splitView, setSplitView] = useState(false);
  const [activeTab, setActiveTab] = useState('alerts');
  const alertRefs = useRef(new Map<string, HTMLDivElement | null>());
  const selectedDocument =
    documents.find((doc) => doc.id === selectedDocumentId) || null;

  useEffect(() => {
    if (!selectedDocumentId && documents.length > 0) {
      setSelectedDocumentId(documents[0].id);
    }
  }, [documents, selectedDocumentId]);

  const { blobUrl, loading: blobLoading, error: blobError } = useDocumentBlob(
    selectedDocumentId
  );
  const {
    alerts,
    highlights,
    loading: alertsLoading,
    error: alertsError,
    refetch: refetchAlerts,
  } = useDocumentAlerts(selectedDocumentId);

  const handleAlertClick = (alertId: string) => {
    setActiveHighlightId(`highlight-${alertId}`);
    setActiveTab('alerts');
  };

  const handleHighlightClick = (highlightId: string, entityId: string) => {
    setActiveHighlightId(highlightId);
    setActiveTab('alerts');
    const target = alertRefs.current.get(entityId);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  const handleDocumentChange = (docId: string) => {
    setSelectedDocumentId(docId);
    setActiveHighlightId(null);
  };

  const handleRefresh = async () => {
    await refetchDocuments();
    await refetchAlerts();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Evidence Viewer</h1>
          <p className="text-muted-foreground">
            Proyecto: {params.id}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleRefresh}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Actualizar
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Download className="mr-2 h-4 w-4" />
                Exportar
                <ChevronDown className="ml-2 h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem>
                <FileJson className="mr-2 h-4 w-4" />
                Exportar a JSON
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Database className="mr-2 h-4 w-4" />
                Exportar a CSV
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            variant={splitView ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSplitView(!splitView)}
          >
            <Columns2 className="mr-2 h-4 w-4" />
            Vista dividida
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <ResizablePanelGroup direction="horizontal" className="min-h-[calc(100vh-12rem)]">
        {/* Left Panel - Document Viewer */}
        <ResizablePanel defaultSize={splitView ? 50 : 70} minSize={30}>
          <Card className="h-full">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  {selectedDocument?.name || 'Documento'}
                </CardTitle>
                <Badge variant="outline">{selectedDocument?.type || 'contract'}</Badge>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {blobError ? (
                <div className="flex items-center justify-center p-8">
                  <Alert variant="destructive">
                    <AlertDescription>
                      Documento no disponible.
                    </AlertDescription>
                  </Alert>
                </div>
              ) : blobLoading && !blobUrl ? (
                <div className="p-6">
                  <Skeleton className="h-[720px] w-full" />
                </div>
              ) : (
                <PDFViewer
                  file={blobUrl}
                  highlights={highlights}
                  activeHighlightId={activeHighlightId}
                  onHighlightClick={handleHighlightClick}
                />
              )}
            </CardContent>
          </Card>
        </ResizablePanel>

        <ResizableHandle withHandle />

        {/* Right Panel - Entities & Alerts */}
        <ResizablePanel defaultSize={splitView ? 50 : 30} minSize={20}>
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Entidades Extraídas</CardTitle>
            </CardHeader>
            <CardContent>
              <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="entities">Entidades</TabsTrigger>
                  <TabsTrigger value="alerts">Alertas</TabsTrigger>
                  <TabsTrigger value="search">Búsqueda</TabsTrigger>
                </TabsList>

                <TabsContent value="entities" className="space-y-4">
                  <Alert>
                    <AlertDescription>
                      No hay entidades extraídas para este documento.
                      <br />
                      <span className="text-xs text-muted-foreground">
                        Las entidades serán extraídas automáticamente del backend.
                      </span>
                    </AlertDescription>
                  </Alert>
                </TabsContent>

                <TabsContent value="alerts" className="space-y-4">
                  {alertsLoading ? (
                    <Skeleton className="h-24 w-full" />
                  ) : alertsError ? (
                    <Alert variant="destructive">
                      <AlertDescription>
                        No se pudieron cargar las alertas.
                      </AlertDescription>
                    </Alert>
                  ) : alerts.length === 0 ? (
                    <Alert>
                      <AlertDescription>
                        No hay alertas para este documento.
                      </AlertDescription>
                    </Alert>
                  ) : (
                    <div className="space-y-3 max-h-[60vh] overflow-auto pr-2">
                      {alerts.map((alert) => (
                        <div
                          key={alert.id}
                          ref={(el) => {
                            alertRefs.current.set(alert.id, el);
                          }}
                          className={cn(
                            'rounded-lg border p-3 transition-colors cursor-pointer',
                            activeHighlightId === `highlight-${alert.id}` &&
                              'border-primary bg-primary/5'
                          )}
                          onClick={() => handleAlertClick(alert.id)}
                        >
                          <div className="flex items-center justify-between">
                            <p className="text-sm font-semibold">{alert.title}</p>
                            <Badge variant="outline">{alert.severity}</Badge>
                          </div>
                          <p className="text-xs text-muted-foreground mt-1">
                            {alert.description}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="search" className="space-y-4">
                  <HighlightSearchBarPlaceholder />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </ResizablePanel>
      </ResizablePanelGroup>

      {/* Document Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Documentos Recientes
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {documentsLoading ? (
              <Skeleton className="h-20 w-full" />
            ) : documentsError ? (
              <Alert variant="destructive">
                <AlertDescription>
                  No se pudieron cargar los documentos.
                </AlertDescription>
              </Alert>
            ) : documents.length === 0 ? (
              <Alert>
                <AlertDescription>
                  No hay documentos disponibles para este proyecto.
                </AlertDescription>
              </Alert>
            ) : (
              documents.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => handleDocumentChange(doc.id)}
                  className={cn(
                    "flex items-center gap-3 p-4 rounded-lg border transition-colors",
                    selectedDocument?.id === doc.id
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-primary/50"
                  )}
                >
                  <FileText className="h-8 w-8 text-muted-foreground" />
                  <div className="flex-1 text-left">
                    <p className="font-medium text-sm">{doc.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {(doc.fileSize || 0) / 1024 > 0
                        ? `${Math.max(1, Math.round((doc.fileSize || 0) / 1024))} KB`
                        : 'Sin tamaño'}
                    </p>
                  </div>
                  {selectedDocument?.id === doc.id && (
                    <CheckCircle className="h-5 w-5 text-primary" />
                  )}
                </button>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
