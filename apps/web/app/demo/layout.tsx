'use client';

import type { ReactNode } from "react";
import { DemoBanner } from "@/components/layout/DemoBanner";

export default function DemoLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <DemoBanner />
      <div
        className="border-b border-warning/20 bg-warning-bg/40 px-6 py-3"
        aria-label="Demo route context"
      >
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-warning">
          Demo Route
        </p>
        <p className="mt-1 text-sm text-warning">
          This area is backed by sample records under <code>/demo</code> and is
          separated from the real authenticated workspace.
        </p>
      </div>
      <main className="p-6">{children}</main>
    </div>
  );
}
