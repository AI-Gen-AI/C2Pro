"use client";

import * as Sentry from "@sentry/react";
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

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  const [client] = useState(() => createQueryClient());
  const [mswReady, setMswReady] = useState(!env.IS_DEMO);
  const [sentryReady, setSentryReady] = useState(false);

  useEffect(() => {
    if (sentryReady || typeof window === "undefined") return;

    Sentry.init({
      dsn: "https://dc374a124792ae061c949999122d205a@o4510540096077824.ingest.de.sentry.io/4510804751089744",
      tunnel: process.env.NODE_ENV === "development" ? "/tunnel" : undefined,
      environment:
        process.env.NODE_ENV === "development" ? "development" : "production",
      debug: true,
      integrations: [
        Sentry.browserTracingIntegration(),
        Sentry.replayIntegration(),
      ],
      tracesSampleRate: 1.0,
      replaysSessionSampleRate: 0.1,
      replaysOnErrorSampleRate: 1.0,
    });

    setSentryReady(true);
  }, [sentryReady]);

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
