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
import { env } from "@/config/env";
import { SentryInit } from "@/components/providers/SentryInit";

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  const [client] = useState(() => createQueryClient());
  const [mswReady, setMswReady] = useState(!env.IS_DEMO);
  useEffect(() => {
    if (!env.IS_DEMO) return;

    async function initMsw() {
      const { worker } = await import("@/mocks/browser");
      await worker.start({ onUnhandledRequest: "bypass", quiet: true });
      setMswReady(true);
    }

    initMsw();
  }, []);

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
