"use client";
import { QueryClientProvider } from "@tanstack/react-query";
import { ClerkProvider } from "@clerk/nextjs";
import { ThemeProvider } from "next-themes";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { AuthSync } from "@/components/providers/AuthSync";
import { AuthProvider } from "@/contexts/AuthContext";
import { createQueryClient } from "@/lib/api/queryClient";
import "@/lib/api/config";
import { SentryInit } from "@/components/providers/SentryInit";
import { useAppModeStore, selectIsDemoMode } from "@/stores/app-mode";

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  const isDemoMode = useAppModeStore(selectIsDemoMode);
  const [client] = useState(() => createQueryClient());
  const [mswReady, setMswReady] = useState(!isDemoMode);

  useEffect(() => {
    if (!isDemoMode) return;

    async function initMsw() {
      const { worker } = await import("@/mocks/browser");
      await worker.start({ onUnhandledRequest: "bypass", quiet: true });
      setMswReady(true);
    }

    initMsw();
  }, [isDemoMode]);

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
            <AuthProvider>{children}</AuthProvider>
          </ThemeProvider>
        </AuthSync>
      </QueryClientProvider>
    </ClerkProvider>
  );
}
