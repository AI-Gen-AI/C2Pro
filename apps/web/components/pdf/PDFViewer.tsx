'use client';

import { useEffect, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { HighlightLayer } from './HighlightLayer';
import type { Highlight } from '@/types/highlight';
import { cn } from '@/lib/utils';
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCw,
  Download,
  AlertCircle,
  FileText,
} from 'lucide-react';

// Configure PDF.js worker (local mjs build for Next.js)
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url
).toString();

export interface PDFViewerProps {
  /** URL or file path to the PDF document */
  file?: string | File | null;
  /** Initial page number (1-indexed) */
  initialPage?: number;
  /** Initial zoom scale (1.0 = 100%) */
  initialScale?: number;
  /** Whether to show page controls */
  showControls?: boolean;
  /** Whether to show zoom controls */
  showZoomControls?: boolean;
  /** Highlights to render on the PDF */
  highlights?: Highlight[];
  /** Currently active/focused highlight ID */
  activeHighlightId?: string | null;
  /** Callback when page changes */
  onPageChange?: (pageNumber: number) => void;
  /** Callback when scale changes */
  onScaleChange?: (scale: number) => void;
  /** Callback when document loads successfully */
  onDocumentLoadSuccess?: (numPages: number) => void;
  /** Callback when document fails to load */
  onDocumentLoadError?: (error: Error) => void;
  /** Callback when a highlight is clicked */
  onHighlightClick?: (highlightId: string, entityId: string) => void;
  /** CSS class for the container */
  className?: string;
  /** Minimum zoom scale */
  minScale?: number;
  /** Maximum zoom scale */
  maxScale?: number;
  /** Zoom step increment */
  zoomStep?: number;
}

export function PDFViewer({
  file,
  initialPage = 1,
  initialScale = 1.0,
  showControls = true,
  showZoomControls = true,
  highlights = [],
  activeHighlightId = null,
  onPageChange,
  onScaleChange,
  onDocumentLoadSuccess,
  onDocumentLoadError,
  onHighlightClick,
  className,
  minScale = 0.5,
  maxScale = 3.0,
  zoomStep = 0.1,
}: PDFViewerProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState<number>(initialPage);
  const [scale, setScale] = useState<number>(initialScale);
  const [rotation, setRotation] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const [pageDimensions, setPageDimensions] = useState<{
    width: number;
    height: number;
  } | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

  // Reset to initial page when file changes
  useEffect(() => {
    setPageNumber(initialPage);
    setScale(initialScale);
    setRotation(0);
    setLoading(true);
    setError(null);
    setPageDimensions(null);
  }, [file, initialPage, initialScale]);

  useEffect(() => {
    if (!activeHighlightId) return;
    const activeHighlight = highlights.find((h) => h.id === activeHighlightId);
    if (activeHighlight && activeHighlight.page !== pageNumber) {
      setPageNumber(activeHighlight.page);
      onPageChange?.(activeHighlight.page);
      return;
    }
    const container = scrollContainerRef.current;
    if (!container) return;

    const highlight = container.querySelector<HTMLElement>(
      `[data-highlight-id="${activeHighlightId}"]`
    );
    if (!highlight) return;

    const containerRect = container.getBoundingClientRect();
    const highlightRect = highlight.getBoundingClientRect();
    const offsetTop =
      highlightRect.top - containerRect.top + container.scrollTop - 24;

    container.scrollTo({ top: offsetTop, behavior: 'smooth' });
  }, [activeHighlightId, highlights, pageNumber, scale, onPageChange]);

  function onDocumentLoad({ numPages }: { numPages: number }) {
    setNumPages(numPages);
    setLoading(false);
    setError(null);
    onDocumentLoadSuccess?.(numPages);
  }

  function onDocumentError(error: Error) {
    console.error('Error loading PDF:', error);
    setError(error);
    setLoading(false);
    onDocumentLoadError?.(error);
  }

  function changePage(offset: number) {
    const newPage = Math.min(Math.max(1, pageNumber + offset), numPages);
    setPageNumber(newPage);
    onPageChange?.(newPage);
  }

  function previousPage() {
    changePage(-1);
  }

  function nextPage() {
    changePage(1);
  }

  function zoomIn() {
    const newScale = Math.min(scale + zoomStep, maxScale);
    setScale(newScale);
    onScaleChange?.(newScale);
  }

  function zoomOut() {
    const newScale = Math.max(scale - zoomStep, minScale);
    setScale(newScale);
    onScaleChange?.(newScale);
  }

  function resetZoom() {
    setScale(1.0);
    onScaleChange?.(1.0);
  }

  function rotate() {
    setRotation((prev) => (prev + 90) % 360);
  }

  function downloadPDF() {
    if (typeof file === 'string') {
      const link = document.createElement('a');
      link.href = file;
      link.download = file.split('/').pop() || 'document.pdf';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  }

  const scalePercentage = Math.round(scale * 100);
  const canZoomIn = scale < maxScale;
  const canZoomOut = scale > minScale;
  const canGoPrevious = pageNumber > 1;
  const canGoNext = pageNumber < numPages;

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Toolbar */}
      {showControls && (
        <div className="flex items-center justify-between border-b bg-background p-3 shrink-0">
          <div className="flex items-center gap-2">
            {/* Page Navigation */}
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                onClick={previousPage}
                disabled={!canGoPrevious || loading}
                className="h-8 w-8 p-0"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <div className="flex items-center gap-1 px-2 text-sm">
                <span className="font-medium">{pageNumber}</span>
                <span className="text-muted-foreground">/</span>
                <span className="text-muted-foreground">{numPages || '?'}</span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={nextPage}
                disabled={!canGoNext || loading}
                className="h-8 w-8 p-0"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>

            {showZoomControls && (
              <>
                <div className="h-6 w-px bg-border mx-2" />
                {/* Zoom Controls */}
                <div className="flex items-center gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={zoomOut}
                    disabled={!canZoomOut || loading}
                    className="h-8 w-8 p-0"
                  >
                    <ZoomOut className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={resetZoom}
                    disabled={loading}
                    className="h-8 px-2 text-xs font-medium"
                  >
                    {scalePercentage}%
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={zoomIn}
                    disabled={!canZoomIn || loading}
                    className="h-8 w-8 p-0"
                  >
                    <ZoomIn className="h-4 w-4" />
                  </Button>
                </div>

                <div className="h-6 w-px bg-border mx-2" />
                {/* Additional Controls */}
                <div className="flex items-center gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={rotate}
                    disabled={loading}
                    className="h-8 w-8 p-0"
                  >
                    <RotateCw className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={downloadPDF}
                    disabled={loading || typeof file !== 'string'}
                    className="h-8 w-8 p-0"
                  >
                    <Download className="h-4 w-4" />
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* PDF Document Container */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-auto bg-muted/30 p-4"
      >
        <div className="flex justify-center">
          {error ? (
            <Alert variant="destructive" className="max-w-md">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Failed to load PDF</AlertTitle>
              <AlertDescription>
                {error.message || 'An error occurred while loading the document.'}
                <div className="mt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setError(null);
                      setLoading(true);
                    }}
                  >
                    Retry
                  </Button>
                </div>
              </AlertDescription>
            </Alert>
          ) : !file ? (
            <div className="flex flex-col items-center gap-4 p-8">
              <FileText className="h-16 w-16 text-muted-foreground animate-pulse" />
              <p className="text-sm text-muted-foreground">
                Documento no disponible.
              </p>
            </div>
          ) : (
            <Document
              file={file}
              onLoadSuccess={onDocumentLoad}
              onLoadError={onDocumentError}
              loading={
                <div className="flex flex-col items-center gap-4 p-8">
                  <FileText className="h-16 w-16 text-muted-foreground animate-pulse" />
                  <div className="space-y-2">
                    <Skeleton className="h-8 w-64" />
                    <Skeleton className="h-96 w-[600px]" />
                  </div>
                  <p className="text-sm text-muted-foreground">Loading PDF document...</p>
                </div>
              }
              error={
                <Alert variant="destructive" className="max-w-md">
                  <AlertCircle className="h-4 w-4" />
                  <AlertTitle>Failed to load PDF</AlertTitle>
                  <AlertDescription>
                    The document could not be loaded. Please check the file and try again.
                  </AlertDescription>
                </Alert>
              }
              className="pdf-document"
            >
              <div className="relative">
                <Page
                  pageNumber={pageNumber}
                  scale={scale}
                  rotate={rotation}
                  renderTextLayer={true}
                  renderAnnotationLayer={true}
                  onRenderSuccess={(page) => {
                    const viewport = page.getViewport({ scale: 1 });
                    setPageDimensions({
                      width: viewport.width,
                      height: viewport.height,
                    });
                  }}
                  loading={
                    <div className="flex items-center justify-center p-8">
                      <Skeleton className="h-[842px] w-[595px]" />
                    </div>
                  }
                  error={
                    <Alert variant="destructive" className="max-w-md">
                      <AlertCircle className="h-4 w-4" />
                      <AlertTitle>Page Error</AlertTitle>
                      <AlertDescription>
                        Failed to render page {pageNumber}.
                      </AlertDescription>
                    </Alert>
                  }
                  className="shadow-lg"
                />
                {/* Render highlights on top of the PDF */}
                {highlights.length > 0 && (
                  <HighlightLayer
                    highlights={highlights}
                    activeHighlightId={activeHighlightId}
                    currentPage={pageNumber}
                    scale={scale}
                    pageDimensions={pageDimensions}
                    onHighlightClick={onHighlightClick}
                  />
                )}
              </div>
            </Document>
          )}
        </div>
      </div>
    </div>
  );
}

export default PDFViewer;
