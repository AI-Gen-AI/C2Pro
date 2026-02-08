'use client';

export function DemoBanner() {
  return (
    <div className="flex items-center justify-center gap-2 border-b border-warning/20 bg-warning-bg px-4 py-1.5">
      <span className="inline-block h-1.5 w-1.5 rounded-full bg-warning" />
      <span className="text-[11px] font-medium text-warning">
        Demo Mode — Sample data for &quot;Torre Skyline&quot; project
      </span>
    </div>
  );
}
