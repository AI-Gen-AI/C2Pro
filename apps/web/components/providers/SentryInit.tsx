"use client";

import { useEffect, useRef } from "react";
import * as Sentry from "@sentry/react";
import { env } from "@/config/env";

export function isValidSentryDsn(dsn: string): boolean {
  try {
    const parsed = new URL(dsn);
    const projectId = parsed.pathname.split("/").filter(Boolean).at(-1);
    return Boolean(
      parsed.protocol.startsWith("http") &&
        parsed.host &&
        projectId &&
        /^\d+$/.test(projectId),
    );
  } catch {
    return false;
  }
}

export function SentryInit() {
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current || typeof window === "undefined") return;
    if (!env.SENTRY_DSN) return;
    if (!isValidSentryDsn(env.SENTRY_DSN)) return;

    Sentry.init({
      dsn: env.SENTRY_DSN,
      tunnel: env.IS_DEV ? "/tunnel" : undefined,
      environment: env.IS_DEV ? "development" : "production",
      debug: env.IS_DEV,
      integrations: [Sentry.browserTracingIntegration()],
      tracesSampleRate: 1.0,
    });

    initialized.current = true;
  }, []);

  return null;
}
