"use client";

import { use, useState, useRef, useMemo, useCallback } from 'react';
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
import { EntityValidationList, ExtractedEntity } from '@/components/evidence';
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

// Mock extracted entities for Gate 6 Human-in-the-loop demonstration
const mockExtractedEntities: ExtractedEntity[] = [
  {
    id: 'entity-001',
    type: 'Penalty Clause',
    text: 'In case of delay exceeding 30 calendar days, the contractor shall pay a penalty of 0.5% of the total contract value per day of delay, up to a maximum of 10%.',
    originalText: 'En caso de retraso superior a 30 días naturales...',
    confidence: 87,
    page: 12,
    validationStatus: 'pending',
    linkedAlerts: ['alert-001'],
    linkedWbs: ['WBS-4.2.1'],
  },
  {
    id: 'entity-002',
    type: 'Payment Terms',
    text: 'Payment shall be made within 30 days of invoice receipt. Late payments shall accrue interest at 1.5% per month.',
    confidence: 94,
    page: 8,
    validationStatus: 'pending',
    linkedWbs: ['WBS-3.1.2'],
  },
  {
    id: 'entity-003',
    type: 'Warranty Period',
    text: 'The contractor warrants all work for a period of 24 months from the date of final acceptance.',
    confidence: 92,
    page: 15,
    validationStatus: 'approved',
  },
  {
    id: 'entity-004',
    type: 'Liability Limit',
    text: 'Total liability under this contract shall not exceed 150% of the total contract value.',
    confidence: 78,
    page: 22,
    validationStatus: 'pending',
    linkedAlerts: ['alert-002', 'alert-003'],
  },
  {
    id: 'entity-005',
    type: 'Termination Clause',
    text: 'Either party may terminate this agreement with 60 days written notice.',
    confidence: 45,
    page: 28,
    validationStatus: 'rejected',
    rejectionReason: 'Extraction incomplete - missing termination conditions and penalties.',
  },
  {
    id: 'entity-006',
    type: 'Force Majeure',
    text: 'Neither party shall be liable for delays caused by events beyond their reasonable control, including natural disasters, war, or government actions.',
    confidence: 89,
    page: 30,
    validationStatus: 'pending',
  },
];

interface EvidencePageProps {
  params: Promise<{
    id: string;
  }>;
}

export default function EvidencePage({ params }: EvidencePageProps) {
  const { id } = use(params);
  const [selectedDocument, setSelectedDocument] = useState(mockDocuments[0]);
  const [highlights, setHighlights] = useState([]);
  const [activeHighlightId, setActiveHighlightId] = useState<string | null>(null);
  const [splitView, setSplitView] = useState(false);
  const [entities, setEntities] = useState<ExtractedEntity[]>(mockExtractedEntities);
  const [activeEntityId, setActiveEntityId] = useState<string | null>(null);

  // Gate 6 Human-in-the-loop: Entity approval handler
  const handleApproveEntity = useCallback((entityId: string) => {
    setEntities((prev) =>
      prev.map((entity) =>
        entity.id === entityId
          ? { ...entity, validationStatus: 'approved' as const, validated: true }
          : entity
      )
    );
    // TODO: API call to persist approval
    console.log(`[Gate 6] Entity ${entityId} approved by user`);
  }, []);

  // Gate 6 Human-in-the-loop: Entity rejection handler
  const handleRejectEntity = useCallback((entityId: string, reason: string) => {
    setEntities((prev) =>
      prev.map((entity) =>
        entity.id === entityId
          ? {
              ...entity,
              validationStatus: 'rejected' as const,
              validated: false,
              rejectionReason: reason,
            }
          : entity
      )
    );
    // TODO: API call to persist rejection with reason
    console.log(`[Gate 6] Entity ${entityId} rejected by user. Reason: ${reason}`);
  }, []);

  // Handle entity click - navigate to page in PDF
  const handleEntityClick = useCallback((entity: ExtractedEntity) => {
    setActiveEntityId(entity.id);
    // TODO: Scroll PDF to entity.page when PDF viewer is active
    console.log(`Navigate to page ${entity.page} for entity ${entity.id}`);
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Evidence Viewer</h1>
          <p className="text-muted-foreground">
            Proyecto: {id}
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
                  {/* Gate 6 Human-in-the-loop: Entity Validation List */}
                  <EntityValidationList
                    entities={entities}
                    onApprove={handleApproveEntity}
                    onReject={handleRejectEntity}
                    onEntityClick={handleEntityClick}
                    activeEntityId={activeEntityId}
                  />
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
