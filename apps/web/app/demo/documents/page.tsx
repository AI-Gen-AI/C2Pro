"use client";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  FileText,
  FileSpreadsheet,
  FileCode,
  Upload,
  Download,
  Eye,
  MoreVertical,
} from "lucide-react";
import { SAMPLE_DATA } from "@/contexts/demo-mode";
import { formatDemoDate } from "../date-format";

function formatFileSize(bytes: number) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function getDocumentIcon(type: string) {
  switch (type) {
    case "contract":
      return <FileText className="w-8 h-8 text-blue-500" />;
    case "specification":
      return <FileCode className="w-8 h-8 text-purple-500" />;
    case "proposal":
      return <FileSpreadsheet className="w-8 h-8 text-green-500" />;
    default:
      return <FileText className="w-8 h-8 text-gray-500" />;
  }
}

function getTypeBadge(type: string) {
  switch (type) {
    case "contract":
      return <Badge className="bg-blue-100 text-blue-700">Contract</Badge>;
    case "specification":
      return <Badge className="bg-purple-100 text-purple-700">Specification</Badge>;
    case "proposal":
      return <Badge className="bg-green-100 text-green-700">Proposal</Badge>;
    default:
      return <Badge variant="outline">{type}</Badge>;
  }
}

export default function DemoDocumentsPage() {
  const documents = SAMPLE_DATA.documents;
  const clauses = SAMPLE_DATA.clauses;

  const totalClauses = documents.reduce((sum, doc) => sum + doc.clause_count, 0);
  const totalSize = documents.reduce((sum, doc) => sum + doc.size, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Documents</h1>
          <p className="text-sm text-muted-foreground">
            Contract documents and extracted clauses
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-sm text-muted-foreground">
            {documents.length} documents | {totalClauses} clauses | {formatFileSize(totalSize)}
          </div>
          <Button disabled className="opacity-50 cursor-not-allowed">
            <Upload className="w-4 h-4 mr-2" />
            Upload
          </Button>
        </div>
      </div>

      {/* Info Banner */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-blue-800">
          Demo documents showing sample contract analysis. Sign in to upload and analyze your own documents.
        </p>
      </div>

      {/* Documents List */}
      <div className="space-y-4">
        {documents.map((doc) => {
          const docClauses = clauses.filter((c) => c.document_id === doc.id);

          return (
            <Card key={doc.id} className="p-4 hover:shadow-md transition-shadow">
              <div className="flex items-start gap-4">
                {/* Icon */}
                <div className="p-2 bg-slate-100 rounded-lg">
                  {getDocumentIcon(doc.type)}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-foreground truncate">
                      {doc.name}
                    </h3>
                    {getTypeBadge(doc.type)}
                  </div>

                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <span>{formatFileSize(doc.size)}</span>
                    <span>{doc.clause_count} clauses extracted</span>
                    <span>
                      Uploaded {formatDemoDate(doc.created_at)}
                    </span>
                  </div>

                  {/* Extracted Clauses Preview */}
                  {docClauses.length > 0 && (
                    <div className="mt-3 space-y-2">
                      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Sample Extracted Clauses
                      </p>
                      {docClauses.slice(0, 2).map((clause) => (
                        <div
                          key={clause.id}
                          className="p-2 bg-slate-50 rounded border border-slate-200 text-sm"
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <Badge variant="outline" className="text-xs">
                              {clause.type.replace(/_/g, " ")}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {Math.round(clause.confidence * 100)}% confidence
                            </span>
                          </div>
                          <p className="text-muted-foreground line-clamp-2">
                            {clause.text}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="icon" disabled>
                    <Eye className="w-4 h-4" />
                  </Button>
                  <Button variant="ghost" size="icon" disabled>
                    <Download className="w-4 h-4" />
                  </Button>
                  <Button variant="ghost" size="icon" disabled>
                    <MoreVertical className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* All Clauses Summary */}
      <Card className="p-4">
        <h2 className="font-semibold text-foreground mb-3">
          All Extracted Clauses ({clauses.length})
        </h2>
        <div className="space-y-2">
          {clauses.map((clause) => (
            <div
              key={clause.id}
              className="p-3 bg-slate-50 rounded-lg border border-slate-200"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Badge variant="outline">
                    {clause.type.replace(/_/g, " ")}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {Math.round(clause.confidence * 100)}% confidence
                  </span>
                </div>
                <span className="text-xs text-muted-foreground">
                  {formatDemoDate(clause.extracted_at)}
                </span>
              </div>
              <p className="text-sm text-foreground">{clause.text}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
