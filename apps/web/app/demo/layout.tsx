'use client';

import type { ReactNode } from "react";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { AppHeader } from "@/components/layout/AppHeader";
import { DemoBanner } from "@/components/layout/DemoBanner";

export default function DemoLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <DemoBanner />
      <div className="flex flex-1 overflow-hidden">
        <AppSidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <AppHeader />
          <main className="flex-1 overflow-y-auto bg-background p-6">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
