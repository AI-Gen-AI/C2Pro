import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, waitFor } from "@/src/tests/test-utils";

const sentryMocks = vi.hoisted(() => ({
  init: vi.fn(),
  browserTracingIntegration: vi.fn(() => "browser-tracing"),
  replayIntegration: vi.fn(() => "replay"),
}));

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

vi.mock("@/lib/api/generated", () => ({}));

vi.mock("@/config/env", () => ({
  env: {
    IS_DEV: true,
    SENTRY_DSN: "https://example.ingest.sentry.io/123",
  },
}));

vi.mock("@sentry/react", () => ({
  init: sentryMocks.init,
  browserTracingIntegration: sentryMocks.browserTracingIntegration,
  replayIntegration: sentryMocks.replayIntegration,
}));

import { SentryInit, isValidSentryDsn } from "./SentryInit";

describe("SentryInit", () => {
  it("initializes Sentry without Replay integration in Sprint 1", async () => {
    renderWithProviders(<SentryInit />);

    await waitFor(() => {
      expect(sentryMocks.init).toHaveBeenCalledWith(
        expect.objectContaining({
          dsn: "https://example.ingest.sentry.io/123",
          tunnel: "/tunnel",
          environment: "development",
          integrations: ["browser-tracing"],
        }),
      );
      expect(sentryMocks.replayIntegration).not.toHaveBeenCalled();
    });
  });

  it("rejects invalid DSN project ids", () => {
    expect(isValidSentryDsn("https://example.ingest.sentry.io/xxx")).toBe(
      false,
    );
    expect(
      isValidSentryDsn("https://public@o123.ingest.sentry.io/789"),
    ).toBe(true);
  });
});
