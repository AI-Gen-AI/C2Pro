'use client';

import type { ReactNode } from "react";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { AppHeader } from "@/components/layout/AppHeader";
import { DemoBanner } from "@/components/layout/DemoBanner";
import { useAppModeStore, selectIsDemoMode } from "@/stores/app-mode";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const isDemoMode = useAppModeStore(selectIsDemoMode);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {isDemoMode && <DemoBanner />}
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
