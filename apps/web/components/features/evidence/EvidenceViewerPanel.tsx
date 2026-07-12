import { FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LazyPdfEvidenceViewer } from "@/components/features/evidence/LazyPdfEvidenceViewer";
import type { PdfHighlight } from "@/components/features/evidence/PdfEvidenceViewer";
import type { DocumentInfo } from "@/types/document";
import { buildDocumentDownloadUrl } from "./evidence-page-utils";

interface EvidenceViewerPanelProps {
  selectedDocument: DocumentInfo | null;
  selectedDocumentId: string | null;
  highlights: PdfHighlight[];
  activeHighlightId: string | null;
  onHighlightClick: (id: string) => void;
}

export function EvidenceViewerPanel({
  selectedDocument,
  selectedDocumentId,
  highlights,
  activeHighlightId,
  onHighlightClick,
}: EvidenceViewerPanelProps) {
  return (
    <Card className="h-full rounded-2xl border-border/80 bg-card/85 shadow-sm">
      <CardHeader className="border-b border-border/70">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            {selectedDocument?.name ?? "No document selected"}
          </CardTitle>
          {selectedDocument ? (
            <Badge variant="outline" className="rounded-full bg-background/90 px-3 py-1 shadow-sm">
              {selectedDocument.type}
            </Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {selectedDocumentId ? (
          <LazyPdfEvidenceViewer
            fileUrl={buildDocumentDownloadUrl(selectedDocumentId)}
            highlights={highlights}
            activeHighlightId={activeHighlightId}
            onHighlightClick={onHighlightClick}
          />
        ) : (
          <div className="m-6 flex h-full flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-border/80 bg-background/80 p-10 shadow-inner">
            <div className="rounded-2xl border border-border/70 bg-muted/35 p-4 shadow-sm">
              <FileText className="h-12 w-12 text-muted-foreground" />
            </div>
            <div className="text-center">
              <h3 className="text-lg font-semibold">
                No Document Selected
              </h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Select a document from the list below to view evidence.
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
