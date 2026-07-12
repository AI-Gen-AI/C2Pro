import { CheckCircle, Clock, FileText } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { DocumentInfo } from "@/types/document";

interface EvidenceDocumentsCardProps {
  documents: DocumentInfo[];
  documentsLoading: boolean;
  selectedDocumentId: string | null;
  onSelectDocument: (documentId: string) => void;
}

export function EvidenceDocumentsCard({
  documents,
  documentsLoading,
  selectedDocumentId,
  onSelectDocument,
}: EvidenceDocumentsCardProps) {
  return (
    <Card className="rounded-2xl border-border/80 bg-card/85 shadow-sm">
      <CardHeader className="border-b border-border/70">
        <CardTitle className="flex items-center gap-2">
          <Clock className="h-5 w-5" />
          Project Documents
        </CardTitle>
      </CardHeader>
      <CardContent>
        {documentsLoading ? (
          <p className="text-sm text-muted-foreground">Loading documents...</p>
        ) : documents.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No documents available for this project.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {documents.map((doc) => (
              <button
                key={doc.id}
                onClick={() => onSelectDocument(doc.id)}
                className={cn(
                  "flex items-center gap-3 rounded-2xl border bg-background/90 p-4 text-left shadow-sm transition-colors",
                  selectedDocumentId === doc.id
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/50",
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
  );
}
