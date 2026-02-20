'use client';

interface DemoBannerProps {
  projectName?: string;
  onDismiss?: () => void;
}

export function DemoBanner({
  projectName = "Petrochemical Plant EPC",
  onDismiss,
}: DemoBannerProps) {
  return (
    <div
      className="flex w-full items-center justify-center gap-2 border-b border-warning/20 bg-warning-bg px-4 py-1.5"
      role="status"
      aria-label="Demo mode banner"
    >
      <span className="inline-block h-1.5 w-1.5 rounded-full bg-warning" />
      <span className="text-[11px] font-medium text-warning">
        Demo Mode — Sample data for {projectName} project
      </span>
      {onDismiss ? (
        <button
          type="button"
          className="text-[11px] font-medium text-warning underline-offset-2 transition hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-warning/60 focus-visible:ring-offset-2 focus-visible:ring-offset-warning-bg"
          onClick={onDismiss}
          aria-label="Dismiss demo banner"
        >
          Dismiss
        </button>
      ) : null}
    </div>
  );
}
