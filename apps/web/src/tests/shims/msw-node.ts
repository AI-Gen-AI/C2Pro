/**
 * Test Suite ID: TASK-1446
 * Purpose: Vitest-compatible node server shim for local mock handlers.
 */

import type { MockHandler } from "./msw";

const FALLBACK_ORIGIN = "http://localhost";

function buildRequest(input: RequestInfo | URL, init?: RequestInit): Request {
  if (input instanceof Request) {
    return input;
  }

  const url =
    typeof input === "string"
      ? new URL(input, FALLBACK_ORIGIN).toString()
      : input instanceof URL
        ? input.toString()
        : String(input);

  return new Request(url, init);
}

export function setupServer(...initialHandlers: MockHandler[]) {
  let runtimeHandlers = [...initialHandlers];
  let originalFetch: typeof globalThis.fetch | undefined;
  let isListening = false;
  let onUnhandledRequest: "bypass" | "error" | undefined;

  const handleFetch: typeof globalThis.fetch = async (input, init) => {
    const request = buildRequest(input, init);

    for (const handler of runtimeHandlers) {
      const params = handler.match(request);
      if (!params) {
        continue;
      }

      return handler.resolver({ params, request });
    }

    if (onUnhandledRequest === "error") {
      throw new Error(`Unhandled mock request: ${request.method} ${request.url}`);
    }

    if (!originalFetch) {
      throw new Error(`Unhandled mock request without fallback fetch: ${request.method} ${request.url}`);
    }

    return originalFetch(input as never, init);
  };

  return {
    listen(options?: { onUnhandledRequest?: "bypass" | "error" }) {
      onUnhandledRequest = options?.onUnhandledRequest;
      if (!isListening) {
        originalFetch = globalThis.fetch.bind(globalThis);
        globalThis.fetch = handleFetch;
        isListening = true;
      }
    },
    resetHandlers(...nextHandlers: MockHandler[]) {
      runtimeHandlers = nextHandlers.length > 0 ? [...nextHandlers] : [...initialHandlers];
    },
    use(...nextHandlers: MockHandler[]) {
      runtimeHandlers = [...nextHandlers, ...runtimeHandlers];
    },
    close() {
      if (originalFetch) {
        globalThis.fetch = originalFetch;
      }
      isListening = false;
      runtimeHandlers = [...initialHandlers];
    },
  };
}
