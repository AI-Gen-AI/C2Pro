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
      {showDemoBanner && <DemoBanner />}
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
