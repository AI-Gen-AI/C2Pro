"use client";
import { QueryClientProvider } from "@tanstack/react-query";
import { ClerkProvider } from "@clerk/nextjs";
import { usePathname } from "next/navigation";
import { ThemeProvider } from "next-themes";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { AuthSync } from "@/components/providers/AuthSync";
import { AuthProvider } from "@/contexts/AuthContext";
import { DemoModeProvider } from "@/contexts/demo-mode";
import { createQueryClient } from "@/lib/api/queryClient";
import "@/lib/api/config";
import { SentryInit } from "@/components/providers/SentryInit";
import {
  useAppModeStore,
  isExplicitDemoRoute,
} from "@/stores/app-mode";

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  const pathname = usePathname();
  const syncWithPathname = useAppModeStore((state) => state.syncWithPathname);
  const demoEnvironmentEnabled = useAppModeStore(
    (state) => state.demoEnvironmentEnabled,
  );
  const [client] = useState(() => createQueryClient());
  const shouldUseDemoMode =
    demoEnvironmentEnabled && isExplicitDemoRoute(pathname);
  const [mswReady, setMswReady] = useState(!shouldUseDemoMode);

  useEffect(() => {
    syncWithPathname(pathname);
  }, [pathname, syncWithPathname]);

  useEffect(() => {
    if (!shouldUseDemoMode) {
      setMswReady(true);
      return;
    }

    async function initMsw() {
      const { worker } = await import("@/mocks/browser");
      await worker.start({ onUnhandledRequest: "bypass", quiet: true });
      setMswReady(true);
    }

    initMsw();
  }, [shouldUseDemoMode]);

  if (!mswReady) {
    return (
      <div className="flex h-screen items-center justify-center">
        <span className="text-sm text-muted-foreground">
          Initializing demo environment...
        </span>
      </div>
    );
  }

  return (
    <ClerkProvider>
      <SentryInit />
      <QueryClientProvider client={client}>
        <AuthSync>
          <ThemeProvider attribute="class" defaultTheme="light" enableSystem>
            <AuthProvider>
              <DemoModeProvider>{children}</DemoModeProvider>
            </AuthProvider>
          </ThemeProvider>
        </AuthSync>
      </QueryClientProvider>
    </ClerkProvider>
  );
}
