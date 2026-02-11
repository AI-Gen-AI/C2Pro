import { ReactNode } from "react";
import { AppSidebar } from "./AppSidebar";
import { AppHeader } from "./AppHeader";
import { DemoBanner } from "./DemoBanner";

interface AppLayoutProps {
  children: ReactNode;
  title?: string;
  breadcrumb?: string[];
  showDemoBanner?: boolean;
}

export function AppLayout({
  children,
  title,
  breadcrumb,
  showDemoBanner = true,
}: AppLayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden">
      <AppSidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        {showDemoBanner ? <DemoBanner /> : null}
        <AppHeader title={title} breadcrumb={breadcrumb} />
        <main className="flex-1 overflow-y-auto bg-muted/30 p-6">{children}</main>
      </div>
    </div>
  );
}
