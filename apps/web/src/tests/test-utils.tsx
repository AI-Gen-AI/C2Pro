import React, { type ReactNode } from "react";
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";

function TestClerkProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
}

type TestWrapperOptions = {
  queryClient?: QueryClient;
};

export function createTestWrapper(options: TestWrapperOptions = {}) {
  const queryClient = options.queryClient ?? createTestQueryClient();

  return function TestWrapper({ children }: { children: ReactNode }) {
    return (
      <TestClerkProvider>
        <QueryClientProvider client={queryClient}>
          <ThemeProvider attribute="class" defaultTheme="light" enableSystem>
            {children}
          </ThemeProvider>
        </QueryClientProvider>
      </TestClerkProvider>
    );
  };
}

type SearchParamValue =
  | string
  | number
  | boolean
  | null
  | undefined;

export function createMockSearchParams(
  values: Record<string, SearchParamValue> = {},
) {
  const params = new URLSearchParams();

  Object.entries(values).forEach(([key, value]) => {
    if (value !== null && value !== undefined) {
      params.set(key, String(value));
    }
  });

  return params;
}

function AllProviders({ children }: { children: ReactNode }) {
  const queryClient = createTestQueryClient();

  return (
    <TestClerkProvider>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem>
          {children}
        </ThemeProvider>
      </QueryClientProvider>
    </TestClerkProvider>
  );
}

export function renderWithProviders(
  ui: React.ReactElement,
  options?: RenderOptions,
) {
  return render(ui, { wrapper: AllProviders, ...options });
}

export * from "@testing-library/react";
export { renderWithProviders as render };
