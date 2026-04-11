"use client";

import { useRef, useState, type DragEvent, type KeyboardEvent } from "react";
import { Loader2, Upload } from "lucide-react";
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

      {/* Footer: privacy badge + browse button */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div
          className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700"
          data-testid="document-upload-guidance"
        >
          Files stay private to this project workspace.
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
      </div>

      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.xlsx,.bc3"
        className="sr-only"
        disabled={uploading}
        onChange={(event) => handleUpload(Array.from(event.target.files ?? []))}
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
