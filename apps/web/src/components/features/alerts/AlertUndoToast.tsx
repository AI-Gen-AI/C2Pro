/**
 * Test Suite ID: S3-06
 * Roadmap Reference: S3-06 Alert undo + double invalidation
 */
"use client";

interface AlertUndoToastProps {
  message: string;
  onUndo: () => void;
}

export function AlertUndoToast({ message, onUndo }: AlertUndoToastProps) {
  return (
    <div role="status" aria-live="polite">
      <span>{message}</span>
      <button
        type="button"
        onClick={onUndo}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onUndo();
          }
        }}
      >
        Undo
      </button>
    </div>
  );
}

