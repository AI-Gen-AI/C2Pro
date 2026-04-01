/**
 * Test Suite ID: S3-12
 * Backlog Task: TASK-022
 */
'use client';

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { AppHeader } from "@/components/layout/AppHeader";
import { DemoBanner } from "@/components/layout/DemoBanner";
import {
  useAppModeStore,
  selectIsDemoMode,
  isExplicitDemoRoute,
} from "@/stores/app-mode";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const demoEnvironmentEnabled = useAppModeStore(
    (state) => state.demoEnvironmentEnabled,
  );
  const isDemoMode = useAppModeStore(selectIsDemoMode);
  const showDemoBanner =
    demoEnvironmentEnabled &&
    (isDemoMode || isExplicitDemoRoute(pathname));

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <a
        href="#main-content"
        className="sr-only z-50 rounded-md bg-background px-3 py-2 text-sm font-medium text-foreground shadow-sm focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      >
        Skip to main content
      </a>
      {showDemoBanner && <DemoBanner />}
      <div className="flex flex-1 overflow-hidden">
        <AppSidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <AppHeader />
          <main
            id="main-content"
            className="flex-1 overflow-y-auto bg-background p-6"
          >
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
