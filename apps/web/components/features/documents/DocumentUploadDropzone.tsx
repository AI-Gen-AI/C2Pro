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
    <section className="rounded-lg border p-4" data-project-id={projectId}>
      <button
        type="button"
        aria-label={ariaLabel}
        data-drag-state={dragState}
        onDragEnter={onDragEnter}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        className={`w-full rounded-md border-2 border-dashed p-8 text-center transition-colors ${
          dragState === "active"
            ? "border-primary bg-primary/10 text-primary"
            : "border-muted-foreground/25 text-muted-foreground hover:border-primary/50"
        }`}
      >
        <Upload className="mx-auto mb-2 h-8 w-8" />
        <p>Drag and drop files here</p>
        <p className="mt-1 text-xs">PDF, XLSX, BC3 (max 50MB)</p>
      </button>

      <div className="mt-4 flex items-center justify-center gap-3">
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

      <p role="status" aria-live="polite" className="mt-3 text-sm text-muted-foreground">
        {statusMessage}
      </p>
      {message ? <p className="mt-2 text-sm text-foreground">{message}</p> : null}
    </section>
  );
}

