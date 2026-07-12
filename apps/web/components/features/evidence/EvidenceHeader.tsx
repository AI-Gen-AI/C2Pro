import {
  ChevronDown,
  Columns2,
  Database,
  Download,
  FileJson,
  FileText,
  RefreshCw,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

interface EvidenceHeaderProps {
  projectName: string;
  documentCount: number;
  entityCount: number;
  alertCount: number;
  splitView: boolean;
  onRefresh: () => void;
  onExportJson: () => void;
  onExportCsv: () => void;
  onExportPdf: () => void;
  onOpenTemplates: () => void;
  onToggleSplitView: () => void;
}

export function EvidenceHeader({
  projectName,
  documentCount,
  entityCount,
  alertCount,
  splitView,
  onRefresh,
  onExportJson,
  onExportCsv,
  onExportPdf,
  onOpenTemplates,
  onToggleSplitView,
}: EvidenceHeaderProps) {
  return (
    <section className="rounded-2xl border border-border/70 bg-card/85 p-5 shadow-sm">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="space-y-3">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Evidence Viewer</h1>
            <p className="text-muted-foreground">Project: {projectName}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="rounded-full bg-background/90 px-3 py-1 shadow-sm">
              {documentCount} document{documentCount === 1 ? "" : "s"}
            </Badge>
            <Badge variant="outline" className="rounded-full bg-background/90 px-3 py-1 shadow-sm">
              {entityCount} entities
            </Badge>
            <Badge variant="outline" className="rounded-full bg-background/90 px-3 py-1 shadow-sm">
              {alertCount} alerts
            </Badge>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            className="rounded-xl bg-background/95 shadow-sm"
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="rounded-xl bg-background/95 shadow-sm">
                <Download className="mr-2 h-4 w-4" />
                Export
                <ChevronDown className="ml-2 h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              className="w-56 rounded-2xl border-border/80 bg-background/95 p-2 shadow-2xl backdrop-blur-md"
            >
              <div className="mb-2 rounded-xl border border-border/70 bg-muted/35 px-3 py-2">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Export Evidence
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Download the active evidence view.
                </p>
              </div>
              <DropdownMenuItem onClick={onExportJson} className="rounded-xl">
                <FileJson className="mr-2 h-4 w-4" />
                Export JSON
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onExportCsv} className="rounded-xl">
                <Database className="mr-2 h-4 w-4" />
                Export CSV
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onExportPdf} className="rounded-xl">
                <FileText className="mr-2 h-4 w-4" />
                Export PDF
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            variant="outline"
            size="sm"
            onClick={onOpenTemplates}
            className="rounded-xl bg-background/95 shadow-sm"
          >
            Evidence Templates
          </Button>
          <Button
            variant={splitView ? "default" : "outline"}
            size="sm"
            onClick={onToggleSplitView}
            className={cn(
              "rounded-xl shadow-sm",
              splitView ? "" : "bg-background/95",
            )}
          >
            <Columns2 className="mr-2 h-4 w-4" />
            Split View
          </Button>
        </div>
      </div>
    </section>
  );
}
