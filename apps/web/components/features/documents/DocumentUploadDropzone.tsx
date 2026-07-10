"use client";

import { useRef, useState, type DragEvent, type KeyboardEvent } from "react";
import { FileText, Loader2, Upload, X } from "lucide-react";
import { useAuth } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { uploadDocument } from "@/lib/api";
import type { DocumentType } from "@/lib/api/generated/models";
import { formatFileSize } from "@/types/document";

const ALLOWED_EXTENSIONS = new Set(["pdf", "xlsx", "bc3"]);
const DOCUMENT_TYPES: { value: DocumentType; label: string }[] = [
  { value: "contract", label: "Contract" },
  { value: "budget", label: "Budget" },
  { value: "schedule", label: "Schedule" },
  { value: "drawing", label: "Drawing" },
  { value: "specification", label: "Specification" },
  { value: "other", label: "Other" },
];

type StagedUpload = {
  id: string;
  file: File;
  documentType: DocumentType;
};

type DocumentUploadDropzoneProps = {
  projectId: string;
  maxFileSizeBytes?: number;
  defaultType?: DocumentType;
  onUploadComplete?: () => void;
};

function getExtension(fileName: string): string {
  const parts = fileName.split(".");
  return parts.length > 1 ? parts[parts.length - 1]!.toLowerCase() : "";
}

function defaultDocumentTypeForFile(fileName: string): DocumentType {
  const extension = getExtension(fileName);
  if (extension === "pdf") {
    return "contract";
  }
  if (extension === "xlsx" || extension === "bc3") {
    return "budget";
  }
  return "other";
}

function formatUploadFailureMessage(error: unknown): string {
  const rawMessage = error instanceof Error ? error.message : "Upload failed";
  const statusMatch = rawMessage.match(/(\d{3})$/);

  if (statusMatch) {
    return [
      "Upload could not be completed right now.",
      `The server returned ${statusMatch[1]} before the file could be queued.`,
      "Try again in a moment. If it keeps happening, contact support.",
    ].join(" ");
  }

  return `Upload could not be completed right now. ${rawMessage}`;
}

export function DocumentUploadDropzone({
  projectId,
  maxFileSizeBytes,
  defaultType,
  onUploadComplete,
}: DocumentUploadDropzoneProps) {
  const { getToken } = useAuth();
  const [dragState, setDragState] = useState<"idle" | "active">("idle");
  const [message, setMessage] = useState<string>("");
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [uploading, setUploading] = useState(false);
  const [stagedUploads, setStagedUploads] = useState<StagedUpload[]>([]);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const ariaLabel =
    dragState === "active" ? "Drop files to upload" : "Upload documents";

  const stageFiles = (files: File[]): void => {
    if (files.length === 0) {
      setMessage("No files selected");
      return;
    }

    if (maxFileSizeBytes) {
      const oversize = files.find((file) => file.size > maxFileSizeBytes);
      if (oversize) {
        const sizeMb = Math.round(maxFileSizeBytes / (1024 * 1024));
        setMessage(`File exceeds ${sizeMb}MB limit: ${oversize.name}`);
        return;
      }
    }

    const invalid = files.find((file) => !ALLOWED_EXTENSIONS.has(getExtension(file.name)));
    if (invalid) {
      const ext = getExtension(invalid.name) || "unknown";
      setMessage(`Unsupported file type: .${ext}. Allowed: PDF, XLSX, BC3`);
      return;
    }

    setStagedUploads((current) => [
      ...current,
      ...files.map((file, index) => ({
        id: `${file.name}-${file.size}-${file.lastModified}-${index}`,
        file,
        documentType: defaultType ?? defaultDocumentTypeForFile(file.name),
      })),
    ]);
    setMessage(`${files.length} file(s) staged. Confirm each document type before uploading.`);
    setStatusMessage(`${files.length} file(s) staged for upload`);
  };

  const updateStagedDocumentType = (id: string, documentType: DocumentType): void => {
    setStagedUploads((current) =>
      current.map((item) => (item.id === id ? { ...item, documentType } : item)),
    );
  };

  const removeStagedUpload = (id: string): void => {
    setStagedUploads((current) => current.filter((item) => item.id !== id));
  };

  const uploadStagedFiles = async (): Promise<void> => {
    if (stagedUploads.length === 0) {
      setMessage("No files selected");
      return;
    }

    setUploading(true);
    setMessage(`Uploading ${stagedUploads.length} file(s)...`);

    try {
      for (const staged of stagedUploads) {
        const { file, documentType } = staged;
        setStatusMessage(`Uploading: ${file.name}`);
        const freshToken = await getToken();
        await uploadDocument(
          projectId,
          file,
          documentType,
          freshToken ? { token: freshToken } : undefined,
        );
      }
      setMessage(
        `Upload accepted for ${stagedUploads.length} file(s). Backend processing is still required.`,
      );
      setStatusMessage("Upload request accepted");
      setStagedUploads([]);
      onUploadComplete?.();
    } catch (error) {
      setMessage(formatUploadFailureMessage(error));
      setStatusMessage("");
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (event: DragEvent<HTMLButtonElement>): void => {
    event.preventDefault();
    event.stopPropagation();
    setDragState("idle");
    const files = Array.from(event.dataTransfer.files ?? []);
    stageFiles(files);
  };

  const onDragEnter = (event: DragEvent<HTMLButtonElement>): void => {
    event.preventDefault();
    setDragState("active");
  };

  const onDragOver = (event: DragEvent<HTMLButtonElement>): void => {
    event.preventDefault();
    setDragState("active");
  };

  const onDragLeave = (event: DragEvent<HTMLButtonElement>): void => {
    event.preventDefault();
    setDragState("idle");
  };

  const openPicker = (): void => {
    setStatusMessage("File picker opened");
    inputRef.current?.click();
  };

  const onBrowseKeyDown = (event: KeyboardEvent<HTMLButtonElement>): void => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openPicker();
    }
  };

  return (
    <section
      className="overflow-hidden rounded-[28px] border border-border/70 bg-background shadow-sm"
      data-project-id={projectId}
      data-testid="document-upload-surface"
    >
      {/* Drop zone */}
      <button
        type="button"
        aria-label={ariaLabel}
        data-drag-state={dragState}
        onDragEnter={onDragEnter}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={`min-h-[260px] w-full bg-background px-6 py-10 text-center text-foreground shadow-sm transition-colors ${
          dragState === "active"
            ? "border-b-2 border-dashed border-primary bg-primary/5 text-primary"
            : "border-b border-dashed border-border/60 hover:bg-muted/20"
        }`}
      >
        {uploading ? (
          <div className="flex flex-col items-center justify-center">
            <Loader2 className="mb-4 h-12 w-12 animate-spin text-primary" />
            <p className="text-base font-semibold tracking-tight">Uploading your files…</p>
            <p className="mt-1 text-sm text-muted-foreground">This may take a moment</p>
          </div>
        ) : (
          <>
            <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full border border-border/70 bg-muted text-foreground shadow-sm">
              <Upload className="h-7 w-7" />
            </div>
            <p className="text-lg font-semibold tracking-tight">Drag and drop files here</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Upload contracts, schedules, budgets, or BC3 files for this project.
            </p>
            <p className="mt-4 text-xs font-medium uppercase tracking-[0.22em] text-muted-foreground/70">
              PDF · XLSX · BC3
            </p>
          </>
        )}
      </button>

      {stagedUploads.length > 0 ? (
        <div className="space-y-3 border-b border-border/70 px-5 py-4">
          {stagedUploads.map((staged) => (
            <div
              key={staged.id}
              className="grid gap-3 rounded-2xl border border-border/70 bg-muted/20 p-3 sm:grid-cols-[1fr_180px_auto] sm:items-center"
            >
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border bg-background">
                  <FileText className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">
                    {staged.file.name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatFileSize(staged.file.size)}
                  </p>
                </div>
              </div>
              <Select
                value={staged.documentType}
                onValueChange={(value) =>
                  updateStagedDocumentType(staged.id, value as DocumentType)
                }
                disabled={uploading}
              >
                <SelectTrigger
                  aria-label={`Document type for ${staged.file.name}`}
                  className="h-10 rounded-xl bg-background"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DOCUMENT_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label={`Remove ${staged.file.name}`}
                className="rounded-xl"
                disabled={uploading}
                onClick={() => removeStagedUpload(staged.id)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      ) : null}

      {/* Footer: privacy badge + browse button */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div
          className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700"
          data-testid="document-upload-guidance"
        >
          Files stay private to this project workspace.
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            onClick={openPicker}
            onKeyDown={onBrowseKeyDown}
            disabled={uploading}
            variant="outline"
          >
            <Upload className="mr-2 h-4 w-4" />
            Browse files
          </Button>
          <Button
            type="button"
            onClick={() => void uploadStagedFiles()}
            disabled={uploading || stagedUploads.length === 0}
            variant="default"
          >
            {uploading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Upload {stagedUploads.length} file{stagedUploads.length === 1 ? "" : "s"}
          </Button>
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.xlsx,.bc3"
        className="sr-only"
        disabled={uploading}
        onChange={(event) => {
          stageFiles(Array.from(event.target.files ?? []));
          event.currentTarget.value = "";
        }}
      />

      <p role="status" aria-live="polite" className="sr-only">
        {statusMessage}
      </p>
      {message ? (
        <div className="mx-5 mb-4 rounded-2xl border border-border/70 bg-muted/30 px-4 py-3 text-sm text-foreground">
          {message}
        </div>
      ) : null}
    </section>
  );
}
