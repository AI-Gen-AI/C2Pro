"use client";

import * as Sentry from "@sentry/react";
import { QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useState } from "react";
import { AuthProvider } from "@/contexts/AuthContext";
import { DevRoleSwitcher } from "@/components/dev-role-switcher";
import { createQueryClient } from "@/lib/api/queryClient";
import "@/lib/api/config";

Sentry.init({
  dsn: "https://dc374a124792ae061c949999122d205a@o4510540096077824.ingest.de.sentry.io/4510804751089744",
  tunnel: process.env.NODE_ENV === 'development' ? '/tunnel' : undefined,
  environment: process.env.NODE_ENV === 'development' ? 'development' : 'production',
  debug: true,
  integrations: [
    Sentry.browserTracingIntegration(), // Performance Monitoring
    Sentry.replayIntegration(), // Session Replay
  ],
  // Performance Monitoring
  tracesSampleRate: 1.0, // Capture 100% of the transactions
  // Session Replay
  replaysSessionSampleRate: 0.1, // This sets the sample rate at 10%. You may want to change it to 100% while in development and then to a lower rate in production.
  replaysOnErrorSampleRate: 1.0, // If you're not already sampling the entire session, change the sample rate to 100% when sampling sessions where errors occur.
});

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  const [client] = useState(() => createQueryClient());

  return (
    <QueryClientProvider client={client}>
      <AuthProvider>
        {children}
        <DevRoleSwitcher />
      </AuthProvider>
    </QueryClientProvider>
  );
}
