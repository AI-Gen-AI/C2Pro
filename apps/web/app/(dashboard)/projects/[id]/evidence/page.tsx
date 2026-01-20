"use client";

import { useState, useRef, useMemo } from 'react';
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
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
// TEMPORARILY DISABLED: import '@/components/pdf/pdf-viewer.css';

// Temporary simplified PDF viewer placeholder
const PDFViewerPlaceholder = ({ file }: { file?: string }) => (
  <div className="flex h-full flex-col items-center justify-center gap-4 rounded-lg border-2 border-dashed border-border bg-muted/20 p-8">
    <FileText className="h-16 w-16 text-muted-foreground" />
    <div className="text-center">
      <h3 className="text-lg font-semibold">PDF Viewer</h3>
      <p className="text-sm text-muted-foreground mt-2">
        Visor de PDF con sistema de highlights
      </p>
      {file && (
        <p className="text-xs text-muted-foreground mt-2">
          Documento: {file}
        </p>
      )}
      <p className="text-xs text-muted-foreground mt-4">
        <strong>Próximamente:</strong> Visualización de PDF completa con anotaciones y búsqueda
      </p>
    </div>
  </div>
);

// Temporary: Disable PDF viewer until properly configured
// const PDFViewer = dynamic(
//   () => import('@/components/pdf/PDFViewer').then((mod) => mod.PDFViewer),
//   {
//     ssr: false,
//     loading: () => <Skeleton className="h-full w-full" />,
//   }
// );

const HighlightSearchBarPlaceholder = () => (
  <div className="rounded-lg border border-border p-4 text-center">
    <p className="text-sm text-muted-foreground">
      Búsqueda de highlights disponible cuando el PDF Viewer esté activo
    </p>
  </div>
);
import { cn } from '@/lib/utils';
import {
  ArrowLeft,
  ZoomIn,
  ZoomOut,
  RotateCw,
  Download,
  AlertTriangle,
  CheckCircle,
  XCircle,
  FileText,
  Loader2,
  RefreshCw,
  Database,
  FileJson,
  ChevronDown,
  Clock,
  Columns2,
} from 'lucide-react';
import Link from 'next/link';

// Temporary mock data - will be replaced with API calls
const mockDocuments = [
  {
    id: 'contract',
    name: 'Contract_Final.pdf',
    type: 'contract',
    extension: 'pdf',
    url: 'https://raw.githubusercontent.com/mozilla/pdf.js/ba2edeae/examples/learning/helloworld.pdf',
    totalPages: 1,
    fileSize: 2457600,
    uploadedAt: new Date('2024-01-15'),
  },
];

interface EvidencePageProps {
  params: {
    id: string;
  };
}

export default function EvidencePage({ params }: EvidencePageProps) {
  const [selectedDocument, setSelectedDocument] = useState(mockDocuments[0]);
  const [highlights, setHighlights] = useState([]);
  const [activeHighlightId, setActiveHighlightId] = useState<string | null>(null);
  const [splitView, setSplitView] = useState(false);

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
          <Button variant="outline" size="sm">
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
                  {selectedDocument.name}
                </CardTitle>
                <Badge variant="outline">{selectedDocument.type}</Badge>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <PDFViewerPlaceholder file={selectedDocument.url} />
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
              <Tabs defaultValue="entities" className="w-full">
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
                  <Alert>
                    <AlertDescription>
                      No hay alertas para este documento.
                    </AlertDescription>
                  </Alert>
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
            {mockDocuments.map((doc) => (
              <button
                key={doc.id}
                onClick={() => setSelectedDocument(doc)}
                className={cn(
                  "flex items-center gap-3 p-4 rounded-lg border transition-colors",
                  selectedDocument.id === doc.id
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/50"
                )}
              >
                <FileText className="h-8 w-8 text-muted-foreground" />
                <div className="flex-1 text-left">
                  <p className="font-medium text-sm">{doc.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {doc.totalPages} página{doc.totalPages !== 1 ? 's' : ''}
                  </p>
                </div>
                {selectedDocument.id === doc.id && (
                  <CheckCircle className="h-5 w-5 text-primary" />
                )}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
