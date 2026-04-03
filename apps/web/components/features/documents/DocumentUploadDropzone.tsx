"use client";

import { useRef, useState, type DragEvent, type KeyboardEvent } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { uploadDocument } from "@/lib/api";

const ALLOWED_EXTENSIONS = new Set(["pdf", "xlsx", "bc3"]);

type DocumentUploadDropzoneProps = {
  projectId: string;
  maxFileSizeBytes?: number;
  onUploadComplete?: () => void;
};

function getExtension(fileName: string): string {
  const parts = fileName.split(".");
  return parts.length > 1 ? parts[parts.length - 1]!.toLowerCase() : "";
}

export function DocumentUploadDropzone({
  projectId,
  maxFileSizeBytes,
  onUploadComplete,
}: DocumentUploadDropzoneProps) {
  const [dragState, setDragState] = useState<"idle" | "active">("idle");
  const [message, setMessage] = useState<string>("");
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const ariaLabel =
    dragState === "active" ? "Drop files to upload" : "Upload documents";

  const handleUpload = async (files: File[]): Promise<void> => {
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

    setUploading(true);
    setMessage(`Uploading ${files.length} file(s)...`);

    try {
      for (const file of files) {
        setStatusMessage(`Uploading: ${file.name}`);
        await uploadDocument(projectId, file, "CONTRACT");
      }
      setMessage(
        `Upload accepted for ${files.length} file(s). Backend processing is still required.`,
      );
      setStatusMessage("Upload request accepted");
      onUploadComplete?.();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Upload failed";
      setMessage(`Error: ${errorMessage}`);
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
    handleUpload(files);
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
      className="rounded-[28px] border border-border/70 bg-background p-6 shadow-sm"
      data-project-id={projectId}
      data-testid="document-upload-surface"
    >
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-border/70 bg-muted/30 px-4 py-4">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-foreground">Supported formats</p>
          <p className="text-sm text-muted-foreground">
            PDF, XLSX, BC3 up to 50MB per file.
          </p>
        </div>
        <div
          className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700"
          data-testid="document-upload-guidance"
        >
          Files stay private to this project workspace.
        </div>
      </div>

      <button
        type="button"
        aria-label={ariaLabel}
        data-drag-state={dragState}
        onDragEnter={onDragEnter}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={`min-h-[260px] w-full rounded-[24px] border-2 border-dashed bg-background px-6 py-10 text-center text-foreground shadow-sm transition-colors ${
          dragState === "active"
            ? "border-primary bg-primary/10 text-primary"
            : "border-border/90 hover:border-primary/50 hover:bg-muted/30"
        }`}
      >
        <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full border border-border/70 bg-muted text-foreground shadow-sm">
          <Upload className="h-7 w-7" />
        </div>
        <p className="text-lg font-semibold tracking-tight">Drag and drop files here</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Upload contracts, schedules, budgets, or BC3 files for this project.
        </p>
        <p className="mt-4 text-xs font-medium uppercase tracking-[0.22em] text-muted-foreground">
          PDF, XLSX, BC3
        </p>
      </button>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border/70 bg-background/80 px-4 py-3">
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">Prefer browsing?</p>
          <p className="text-xs text-muted-foreground">
            Choose one or multiple files and we will queue them for backend processing.
          </p>
        </div>
        <Button
          type="button"
          onClick={openPicker}
          onKeyDown={onBrowseKeyDown}
          disabled={uploading}
          variant="default"
        >
          <Upload className="mr-2 h-4 w-4" />
          Browse files
        </Button>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.xlsx,.bc3"
          className="sr-only"
          disabled={uploading}
          onChange={(event) => handleUpload(Array.from(event.target.files ?? []))}
        />
      </div>

      <p role="status" aria-live="polite" className="mt-4 text-sm text-muted-foreground">
        {statusMessage}
      </p>
      {message ? (
        <div className="mt-3 rounded-2xl border border-border/70 bg-muted/30 px-4 py-3 text-sm text-foreground">
          {message}
        </div>
      ) : null}
    </section>
  );
}

