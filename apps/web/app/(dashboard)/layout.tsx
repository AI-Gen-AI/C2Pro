'use client';

import type { ReactNode } from "react";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { AppHeader } from "@/components/layout/AppHeader";
// TEMPORALMENTE DESACTIVADO: import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
// TEMPORALMENTE DESACTIVADO: import { useAuth } from "@/contexts/AuthContext";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  // TEMPORALMENTE DESACTIVADO: const { user, tenant, logout } = useAuth();

  return (
    // TEMPORALMENTE DESACTIVADO: <ProtectedRoute>
      <div className="flex h-screen overflow-hidden">
        <AppSidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <AppHeader />
          <main className="flex-1 overflow-y-auto bg-muted/30 p-6">
            {children}
          </main>
        </div>
      </div>
    // TEMPORALMENTE DESACTIVADO: </ProtectedRoute>
  );
}
