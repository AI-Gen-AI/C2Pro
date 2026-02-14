"use client";

import { useRef, useState, type DragEvent, type KeyboardEvent } from "react";

const ALLOWED_EXTENSIONS = new Set(["pdf", "xlsx", "bc3"]);

type DocumentUploadDropzoneProps = {
  projectId: string;
  maxFileSizeBytes?: number;
};

function getExtension(fileName: string): string {
  const parts = fileName.split(".");
  return parts.length > 1 ? parts[parts.length - 1]!.toLowerCase() : "";
}

export function DocumentUploadDropzone({
  projectId,
  maxFileSizeBytes,
}: DocumentUploadDropzoneProps) {
  const [dragState, setDragState] = useState<"idle" | "active">("idle");
  const [message, setMessage] = useState<string>("");
  const [statusMessage, setStatusMessage] = useState<string>("");
  const inputRef = useRef<HTMLInputElement | null>(null);

  const ariaLabel =
    dragState === "active" ? "Drop files to upload" : "Upload documents";

  const validateFiles = (files: File[]): void => {
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

    setMessage(`${files.length} files ready for upload`);
  };

  const onDrop = (event: DragEvent<HTMLButtonElement>): void => {
    event.preventDefault();
    event.stopPropagation();
    setDragState("idle");
    const files = Array.from(event.dataTransfer.files ?? []);
    validateFiles(files);
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
        className="w-full rounded-md border border-dashed p-6 text-primary-text"
      >
        Drag and drop files here
      </button>

      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          onClick={openPicker}
          onKeyDown={onBrowseKeyDown}
          className="rounded bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
        >
          Browse files
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="sr-only"
          onChange={(event) => validateFiles(Array.from(event.target.files ?? []))}
        />
      </div>

      <p role="status" aria-live="polite" className="mt-3 text-sm text-primary-text">
        {statusMessage}
      </p>
      {message ? <p className="mt-2 text-sm text-primary-text">{message}</p> : null}
    </section>
  );
}

