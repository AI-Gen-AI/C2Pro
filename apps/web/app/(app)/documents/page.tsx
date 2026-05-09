import type { ProjectDocumentsGroup } from "@/lib/api/contracts";
import { DocumentsListClient } from "@/components/features/documents/DocumentsListClient";
import { Button } from "@/components/ui/button";
import { listProjectDocumentGroups } from "@/lib/api/services/documents";
import { Upload } from "lucide-react";

export default async function DocumentsPage() {
  let groups: ProjectDocumentsGroup[] = [];
  let loadError: string | null = null;

  try {
    groups = await listProjectDocumentGroups();
  } catch (error) {
    loadError =
      error instanceof Error
        ? error.message
        : "Could not load documents right now.";
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Documents
          </h1>
          <p className="text-sm text-muted-foreground">
            All project documents in one place
          </p>
        </div>
        <Button>
          <Upload className="mr-2 h-4 w-4" />
          Upload Document
        </Button>
      </div>

      {loadError ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {loadError}. Verify the backend service is available and try again.
        </div>
      ) : null}

      <DocumentsListClient groups={groups} />
    </div>
  );
}
