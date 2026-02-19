
# C2Pro v4.0 — Technical Design Document (TDD)

> **Document Type:** Engineering Kick-off — Technical Implementation Plan  
> **Version:** 4.0  
> **Date:** 2026-02-10  
> **Status:** APPROVED — Ready for Sprint Planning  
> **Supersedes:** TDD v3.0 (2026-02-08), FRONTEND_TESTING_PLAN.md (deprecated)  
> **Input:** Frontend Master Plan v1.0 (Phase 1–3 verified), Architecture Plan v2.1  
> **Audience:** Engineering Team, Tech Leads, DevOps, QA  
> **Author:** VP Engineering / Principal Software Architect  
> **Review:** 12 Expert Agents, 6 Cross-Reviewers, 10 Verifiers — 31 flags resolved

---

## Changelog v3.0 → v4.0

| Section | Change | Flags Resolved | Severity |
|---------|--------|----------------|----------|
| §2.2.1 API Client | Auth interceptor rewritten: Clerk-synced Zustand, no `require()` | FLAG-1,2,5 | 🔴 CRITICAL |
| §2.1.3 Providers | Added `AuthSync` component, org-switch cache clear | FLAG-4 | 🔴 CRITICAL |
| §2.4 Stores | `auth.ts` refactored to sync-only cache; added `processing.ts` | FLAG-1,22 | 🔴+🟡 |
| §2.3 Globals.css | Font `@import` removed; added `--primary-text` token | FLAG-8,10 | 🟠 HIGH |
| §2.6 CoherenceGauge | Rewritten as custom SVG (no Recharts dependency) | FLAG-9 | 🟠 HIGH |
| §2.7 SSE Hook | Added `withCredentials`, Zustand persistence, Safari fallback | FLAG-3,22 | 🔴+🟡 |
| §3 Directory | Added `providers/AuthSync.tsx`, `stores/processing.ts`, `fonts/` | FLAG-1,10,22 | Multiple |
| §4.2 Performance | Dashboard budget 50→80KB; `next/font/local` | FLAG-9,10 | 🟠 HIGH |
| §4.6 A11y | Keyboard shortcuts focus-scoped (WCAG 2.1.4) | FLAG-7 | 🟠 HIGH |
| §5 Sprint Plan | Resequenced with flag resolutions mapped per day | All 31 flags | All |
| §6 Risks | 8 new risks from Phase 2-3 analysis added | FLAG-3,4,14 | Multiple |
| §7.1 next.config | CSP strengthened: `worker-src`, Sentry ingest, Permissions-Policy | FLAG-15b | 🟡 |
| §7.3 State Rules | Auth moved from "owned by Zustand" to "synced from Clerk" | FLAG-1 | 🔴 CRITICAL |
| §8 (NEW) Testing | Complete TDD-first test architecture: 192 tests, 3-layer strategy | FLAG-11,12,13,26 | 🟠 HIGH |
| §9 (NEW) Security | CSP, GDPR consent, RBAC gates, watermark pseudonymization | FLAG-14,31 | 🟠+🟡 |
| §10 (NEW) A11y | WCAG 2.2 AA compliance checklist, contrast audit | FLAG-7,8 | 🟠 HIGH |

---

## Table of Contents

1. [Definitive Technology Stack (v4.0)](#1-definitive-technology-stack-v40)
2. [Architecture Patterns & Code Blueprints](#2-architecture-patterns--code-blueprints)
3. [Directory Structure (App Router v4.0)](#3-directory-structure-app-router-v40)
4. [Expert Engineering Decisions](#4-expert-engineering-decisions)
5. [Sprint Plan (4 × 2-Week Sprints)](#5-sprint-plan-4--2-week-sprints)
6. [Technical Risks & Mitigation](#6-technical-risks--mitigation)
7. [Appendices — Configuration](#7-appendices--configuration)
8. [Test-Driven Development Architecture (NEW)](#8-test-driven-development-architecture)
9. [Security Architecture (NEW)](#9-security-architecture)
10. [Accessibility Architecture (NEW)](#10-accessibility-architecture)

---

## 1. Definitive Technology Stack (v4.0)

### 1.1 Migration Delta: v3.0 → v4.0

| Category | v3.0 (Previous) | v4.0 (Current) | Change Reason |
|----------|-----------------|-----------------|---------------|
| Font Loading | `@fontsource-variable/inter` | **`next/font/local`** | FLAG-10: 140KB→40KB, auto `font-display:swap` |
| Auth Pattern | Dual (Clerk + Zustand independent) | **Clerk → AuthSync → Zustand cache** | FLAG-1,2: Dual source of truth eliminated |
| Hero Chart | Recharts `RadialBarChart` | **Custom SVG gauge** | FLAG-9: 65KB→2KB for hero metric |
| Dashboard Budget | 50KB gzipped | **80KB gzipped** | FLAG-9: Realistic with route-specific JS |
| Query Keys | Manual `queryKeys` object | **Orval-generated only** | FLAG-21: Cache duplication eliminated |
| SSE Auth | No auth (bare EventSource) | **`withCredentials: true`** | FLAG-3: Cookie-based auth for SSE |
| Primary Color | `#00ACC1` for all uses | **`#00838F` for text** (`--primary-text`) | FLAG-8: 2.74:1→4.52:1 contrast |
| Testing Plan | FRONTEND_TESTING_PLAN.md | **Integrated §8 (TDD-first)** | FLAG-11: Old plan was for Next.js 14 |

### 1.2 Partial `package.json` — Production Dependencies

```jsonc
{
  "name": "@c2pro/web",
  "version": "4.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev --turbopack",
    "dev:demo": "NEXT_PUBLIC_APP_MODE=demo next dev --turbopack",
    "build": "next build",
    "build:analyze": "ANALYZE=true next build",
    "start": "next start",
    "typecheck": "tsc --noEmit",
    "lint": "eslint . --max-warnings 0",
    "test": "vitest",
    "test:watch": "vitest --watch",
    "test:coverage": "vitest run --coverage",
    "test:e2e": "playwright test",
    "test:e2e:demo": "NEXT_PUBLIC_APP_MODE=demo playwright test",
    "generate:api": "orval",
    "generate:api:check": "orval --check",
    "storybook": "storybook dev -p 6006",
    "chromatic": "chromatic --exit-zero-on-changes",
    "check:budgets": "node scripts/check-budgets.js"
  },
  "dependencies": {
    "next": "^15.3.9",
    "react": "^19.1.0",
    "react-dom": "^19.1.0",
    "typescript": "^5.7.0",
    "@tanstack/react-query": "^5.87.0",
    "@tanstack/react-query-devtools": "^5.87.0",
    "@tanstack/react-table": "^8.21.0",
    "axios": "^1.7.9",
    "zod": "^3.24.0",
    "react-hook-form": "^7.54.0",
    "@hookform/resolvers": "^3.9.0",
    "zustand": "^5.0.3",
    "tailwindcss": "^4.1.0",
    "@tailwindcss/postcss": "^4.1.0",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.7.0",
    "lucide-react": "^0.469.0",
    "next-themes": "^0.4.4",
    "sonner": "^1.7.4",
    "cmdk": "^1.1.1",
    "motion": "^12.4.0",
    "@formkit/auto-animate": "^0.8.2",
    "next-view-transitions": "^0.3.0",
    "recharts": "^2.15.0",
    "tremor": "^3.18.0",
    "@react-pdf-viewer/core": "^4.1.0",
    "@react-pdf-viewer/highlight": "^4.1.0",
    "@react-pdf-viewer/default-layout": "^4.1.0",
    "pdfjs-dist": "^4.9.0",
    "date-fns": "^4.1.0",
    "@dnd-kit/core": "^6.3.0",
    "@dnd-kit/sortable": "^10.0.0",
    "react-resizable-panels": "^2.1.9",
    "@use-gesture/react": "^10.3.1",
    "react-grid-layout": "^2.2.2",
    "@sentry/nextjs": "^9.2.0",
    "@opentelemetry/api": "^1.9.0",
    "@clerk/nextjs": "^6.12.0"
  },
  "devDependencies": {
    "@types/react": "^19.1.0",
    "@types/node": "^22.12.0",
    "orval": "^7.5.0",
    "@hey-api/openapi-ts": "^0.66.0",
    "msw": "^2.7.0",
    "@mswjs/data": "^0.16.2",
    "@faker-js/faker": "^9.4.0",
    "vitest": "^3.2.0",
    "@vitest/coverage-v8": "^3.2.0",
    "@testing-library/react": "^16.2.0",
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/user-event": "^14.6.0",
    "@playwright/test": "^1.50.0",
    "@axe-core/playwright": "^4.10.0",
    "storybook": "^8.5.0",
    "@storybook/addon-a11y": "^8.5.0",
    "chromatic": "^11.22.0",
    "eslint": "^9.18.0",
    "eslint-config-next": "^15.3.0",
    "eslint-plugin-jsx-a11y": "^6.10.0",
    "prettier": "^3.4.0",
    "ajv": "^8.17.0",
    "@next/bundle-analyzer": "^15.3.0"
  }
}
```

**Changes from v3.0:**
- ❌ Removed: `@fontsource-variable/inter`, `@fontsource/jetbrains-mono` (replaced by `next/font/local`)
- ✅ Added: `@testing-library/user-event` (interaction testing), `@next/bundle-analyzer` (budget enforcement)

### 1.3 Critical Version Pins

| Package | Pinned | Reason |
|---------|--------|--------|
| `next` ≥15.3 | Stable PPR, Turbopack default, React Compiler GA | Required for dashboard streaming |
| `tailwindcss` ≥4.1 | CSS-first config stabilized | v4.0 had oxide engine issues |
| `react` ≥19.1 | Stable concurrent features, `use()` hook | Required by Next.js 15.3 |
| `orval` ≥7.5 | TanStack Query v5 + MSW v2 mock generation | Core of dual-mode pipeline |
| `zustand` ≥5.0 | New `createWithEqualityFn`, ES2018 target | Breaking selectors from v4 |
| `motion` ≥12.0 | `LazyMotion` tree-shaking, React 19 support | Renamed from framer-motion |
| `@clerk/nextjs` ≥6.12 | Org switching, session cookies | Core auth provider |

---

## 2. Architecture Patterns & Code Blueprints

### 2.1 Dual Mode Setup — Zero-Conditional-Logic Pattern

**Principle:** Components NEVER check `APP_MODE`. MSW intercepts at the Service Worker/Node level — components see identical responses in both modes.

#### 2.1.1 Environment Configuration

```typescript
// src/config/env.ts
export const env = {
  APP_MODE: (process.env.NEXT_PUBLIC_APP_MODE ?? 'production') as 'production' | 'demo',
  API_BASE_URL: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api',
  IS_DEMO: process.env.NEXT_PUBLIC_APP_MODE === 'demo',
  IS_DEV: process.env.NODE_ENV === 'development',
  SENTRY_DSN: process.env.NEXT_PUBLIC_SENTRY_DSN,
} as const;
```

#### 2.1.2 Server-Side MSW (Next.js 15 `instrumentation.ts` hook)

```typescript
// src/instrumentation.ts — UNCHANGED from v3.0
export async function register() {
  if (process.env.NEXT_PUBLIC_APP_MODE === 'demo') {
    const { server } = await import('@/mocks/node');
    server.listen({ onUnhandledRequest: 'bypass' });
    console.log('[C2Pro] MSW server-side mocking active (demo mode)');
  }
}
```

#### 2.1.3 Client-Side Providers *(CHANGED: Added AuthSync)*

```tsx
// src/app/providers.tsx
'use client';

import { useState, useEffect, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { ThemeProvider } from 'next-themes';
import { ClerkProvider } from '@clerk/nextjs';
import { AuthSync } from '@/components/providers/AuthSync';
import { env } from '@/config/env';

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        refetchOnReconnect: true,
        retry: env.IS_DEMO ? false : 2,
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10_000),
      },
      mutations: { retry: 0 },
    },
  });
}

let browserQueryClient: QueryClient | undefined;
function getQueryClient() {
  if (typeof window === 'undefined') return makeQueryClient();
  return (browserQueryClient ??= makeQueryClient());
}

export function Providers({ children }: { children: ReactNode }) {
  const [mswReady, setMswReady] = useState(!env.IS_DEMO);

  useEffect(() => {
    if (!env.IS_DEMO) return;
    async function initMSW() {
      const { worker } = await import('@/mocks/browser');
      await worker.start({ onUnhandledRequest: 'bypass', quiet: true });
      setMswReady(true);
    }
    initMSW();
  }, []);

  if (!mswReady) {
    return (
      <div className="flex h-screen items-center justify-center">
        <span className="text-muted-foreground text-sm">Initializing demo environment...</span>
      </div>
    );
  }

  return (
    <ClerkProvider>
      <QueryClientProvider client={getQueryClient()}>
        <AuthSync>
          <ThemeProvider attribute="class" defaultTheme="light" enableSystem disableTransitionOnChange>
            {children}
          </ThemeProvider>
        </AuthSync>
        {env.IS_DEV && <ReactQueryDevtools initialIsOpen={false} />}
      </QueryClientProvider>
    </ClerkProvider>
  );
}
```

**Provider hierarchy (order matters):**
```
ClerkProvider               ← Clerk context (session, org)
  └→ QueryClientProvider    ← TanStack Query cache
       └→ AuthSync          ← Syncs Clerk token → Zustand; clears cache on org switch
            └→ ThemeProvider ← Dark/light mode
                 └→ {children}
```

#### 2.1.4 AuthSync Component *(NEW — FLAG-1, FLAG-2, FLAG-4)*

```typescript
// src/components/providers/AuthSync.tsx
'use client';

import { useAuth, useOrganization } from '@clerk/nextjs';
import { useEffect, useRef } from 'react';
import { useAuthStore } from '@/stores/auth';
import { useQueryClient } from '@tanstack/react-query';

/**
 * Bridges Clerk auth → Zustand store for synchronous Axios interceptor access.
 * 
 * WHY: Axios interceptors are plain JS (not React), so they can't call useAuth().
 * Zustand's .getState() provides synchronous access outside React.
 * Clerk is the SOLE source of truth. Zustand is a read-only cache.
 * 
 * RULE: Only this component may call useAuthStore.getState().setAuth()
 */
export function AuthSync({ children }: { children: React.ReactNode }) {
  const { getToken, isSignedIn } = useAuth();
  const { organization } = useOrganization();
  const queryClient = useQueryClient();
  const setAuth = useAuthStore((s) => s.setAuth);
  const prevOrgRef = useRef<string | null>(null);

  // Sync Clerk token → Zustand on mount and every 50s (tokens expire at 60s)
  useEffect(() => {
    if (!isSignedIn) {
      useAuthStore.getState().clear();
      return;
    }
    const sync = async () => {
      const token = await getToken();
      const tenantId = organization?.id ?? null;
      setAuth({ token, tenantId });
    };
    sync();
    const interval = setInterval(sync, 50_000);
    return () => clearInterval(interval);
  }, [isSignedIn, organization?.id, getToken, setAuth]);

  // Clear ALL TanStack Query cache on organization switch (FLAG-4)
  useEffect(() => {
    const currentOrg = organization?.id ?? null;
    if (prevOrgRef.current && currentOrg && prevOrgRef.current !== currentOrg) {
      queryClient.clear(); // Prevents cross-tenant data leakage
    }
    prevOrgRef.current = currentOrg;
  }, [organization?.id, queryClient]);

  return <>{children}</>;
}
```

**Test specification:**
```typescript
// src/components/providers/AuthSync.test.tsx
describe('AuthSync', () => {
  it('syncs Clerk token to Zustand on mount', async () => { /* ... */ });
  it('re-syncs token every 50 seconds', async () => { /* ... */ });
  it('clears Zustand on sign-out', async () => { /* ... */ });
  it('clears QueryClient cache on org switch', async () => { /* ... */ });
  it('does NOT clear cache on initial org load', async () => { /* ... */ });
});
```

### 2.2 Orval Configuration — Single Codegen for Hooks + Mocks

```typescript
// orval.config.ts — UNCHANGED from v3.0
import { defineConfig } from 'orval';

export default defineConfig({
  c2pro: {
    input: {
      target: './openapi.json',
      validation: true,
    },
    output: {
      target: './src/lib/api/generated/endpoints.ts',
      client: 'react-query',
      mode: 'tags-split',
      httpClient: 'axios',
      override: {
        mutator: {
          path: './src/lib/api/client.ts',
          name: 'apiClient',
        },
        query: {
          useQuery: true,
          useMutation: true,
          useSuspenseQuery: true,
          signal: true,
          version: 5,
        },
        zod: {
          strict: { response: true, body: true },
          generate: { param: true, body: true, response: true },
        },
      },
    },
    hooks: { afterAllFilesWrite: 'prettier --write' },
  },
  c2proMocks: {
    input: { target: './openapi.json' },
    output: {
      target: './src/mocks/handlers/generated',
      mode: 'tags-split',
      client: 'mock-service-worker',
      httpClient: 'axios',
      override: {
        mock: {
          type: 'msw',
          useExamples: true,
          delay: 'real',
          baseUrl: '',
        },
      },
    },
  },
});
```

**Generated output structure:**
```
src/lib/api/generated/      # Production hooks (DO NOT EDIT)
├── coherence.ts            # useGetCoherenceDashboard, usePutCoherenceWeights
├── alerts.ts               # useGetAlertsByCategory, usePostAlertApprove
├── documents.ts            # usePostDocumentsUpload, useGetDocumentStatus
├── projects.ts             # useGetProjects, usePostProjects
├── schemas.ts              # Zod validation schemas
└── model/                  # TypeScript interfaces

src/mocks/handlers/generated/  # MSW handlers (DO NOT EDIT)
├── coherence.ts
├── alerts.ts
└── documents.ts
```

**⛔ Query Key Rule (FLAG-21):** Never create manual `queryKeys` objects. Use Orval-generated key factories:
```typescript
// ✅ CORRECT — import from generated code
import { getGetCoherenceDashboardQueryKey } from '@/lib/api/generated/coherence';

// ✅ CORRECT — broad invalidation by tag prefix
queryClient.invalidateQueries({ queryKey: ['coherence'] });

// ❌ FORBIDDEN — manual key objects
const queryKeys = { coherence: { dashboard: (id) => [...] } };
```

#### 2.2.1 API Client *(REWRITTEN — FLAG-1, FLAG-2, FLAG-5)*

```typescript
// src/lib/api/client.ts
import Axios, { type AxiosRequestConfig } from 'axios';
import { env } from '@/config/env';
import { useAuthStore } from '@/stores/auth';

const axiosInstance = Axios.create({
  baseURL: env.API_BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor: reads Clerk token from Zustand cache synchronously
axiosInstance.interceptors.request.use((config) => {
  const { token, tenantId } = useAuthStore.getState();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  if (tenantId) config.headers['X-Tenant-ID'] = tenantId;
  return config;
});

// Response interceptor: retry, auth redirect, rate limit handling
axiosInstance.interceptors.response.use(
  (r) => r,
  async (error) => {
    const config = error.config;

    // Network error retry (exponential backoff, max 3)
    if (!error.response && (config._retryCount ?? 0) < 3) {
      config._retryCount = (config._retryCount ?? 0) + 1;
      await new Promise(r => setTimeout(r, 1000 * Math.pow(2, config._retryCount)));
      return axiosInstance(config);
    }

    // 401: Clear auth and redirect to login
    if (error.response?.status === 401) {
      useAuthStore.getState().clear();
      if (typeof window !== 'undefined') window.location.href = '/login';
    }

    // 429: Rate limited — surface to UI, let TanStack handle retry
    if (error.response?.status === 429) {
      const { toast } = await import('sonner');
      toast.error('Too many requests. Please wait a moment.');
    }

    // 503: Service unavailable
    if (error.response?.status === 503) {
      const { toast } = await import('sonner');
      toast.error('Service temporarily unavailable. Retrying...');
    }

    return Promise.reject(error);
  }
);

export const apiClient = <T>(config: AxiosRequestConfig): Promise<T> => {
  const source = Axios.CancelToken.source();
  const promise = axiosInstance({ ...config, cancelToken: source.token }).then(({ data }) => data);
  // @ts-expect-error — Orval expects cancel on the promise
  promise.cancel = () => source.cancel('Query cancelled');
  return promise;
};
```

**Test specification:**
```typescript
// src/lib/api/client.test.ts
describe('apiClient', () => {
  it('attaches Bearer token from AuthStore', async () => { /* ... */ });
  it('attaches X-Tenant-ID header', async () => { /* ... */ });
  it('retries on network error up to 3 times with exponential backoff', async () => { /* ... */ });
  it('redirects to /login on 401', async () => { /* ... */ });
  it('shows toast on 429', async () => { /* ... */ });
  it('clears auth store on 401', async () => { /* ... */ });
  it('does NOT retry 401/403/422 errors', async () => { /* ... */ });
});
```

### 2.3 Design Tokens — Tailwind v4 CSS-First Configuration *(CORRECTED — FLAG-8, FLAG-10)*

```css
/* src/app/globals.css */
@import "tailwindcss";

/* ❌ REMOVED (FLAG-10): @import "@fontsource-variable/inter"; */
/* ❌ REMOVED (FLAG-10): @import "@fontsource/jetbrains-mono"; */
/* Fonts now loaded via next/font/local in layout.tsx */

@theme {
  --font-sans: "Inter Variable", "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;

  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;

  --shadow-sm: 0 1px 2px 0 oklch(0.55 0.05 195 / 0.05);
  --shadow-md: 0 1px 3px 0 oklch(0.55 0.05 195 / 0.1), 0 1px 2px -1px oklch(0.55 0.05 195 / 0.1);
  --shadow-lg: 0 4px 6px -1px oklch(0.55 0.05 195 / 0.1), 0 2px 4px -2px oklch(0.55 0.05 195 / 0.1);

  --color-chart-scope: #00ACC1;
  --color-chart-budget: #6929C4;
  --color-chart-quality: #1192E8;
  --color-chart-technical: #005D5D;
  --color-chart-legal: #9F1853;
  --color-chart-time: #FA4D56;

  --color-severity-critical: #B91C1C;
  --color-severity-high: #C2410C;
  --color-severity-medium: #92400E;
  --color-severity-low: #166534;

  --duration-fast: 150ms;
  --duration-normal: 200ms;
  --duration-slow: 300ms;
  --duration-score-reveal: 1500ms;
  --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
}

@layer base {
  :root {
    --background: oklch(0.99 0 0);
    --foreground: oklch(0.15 0 0);
    --card: oklch(1 0 0);
    --card-foreground: oklch(0.15 0 0);
    --primary: oklch(0.56 0.12 195);           /* #00ACC1 — backgrounds, decorative, large text ≥18px */
    --primary-foreground: oklch(1 0 0);
    --primary-text: oklch(0.42 0.10 195);      /* ✅ NEW (FLAG-8): #00838F — 4.52:1 on white */
    --secondary: oklch(0.96 0.01 195);
    --secondary-foreground: oklch(0.25 0 0);
    --muted: oklch(0.96 0.005 0);
    --muted-foreground: oklch(0.55 0 0);
    --accent: oklch(0.96 0.01 195);
    --accent-foreground: oklch(0.25 0 0);
    --destructive: oklch(0.55 0.22 27);
    --border: oklch(0.90 0.005 0);
    --ring: oklch(0.56 0.12 195);

    --success: oklch(0.47 0.14 155);
    --success-bg: oklch(0.95 0.04 155);
    --warning: oklch(0.82 0.15 85);
    --warning-bg: oklch(0.98 0.04 85);
    --error: oklch(0.55 0.22 27);
    --error-bg: oklch(0.97 0.03 27);

    --sidebar-background: oklch(0.20 0.05 195);
    --sidebar-foreground: oklch(0.92 0 0);
    --sidebar-primary: oklch(0.72 0.12 195);
    --sidebar-accent: oklch(0.30 0.05 195);

    --radius: 0.375rem;
  }

  .dark {
    --background: oklch(0.15 0 0);
    --foreground: oklch(0.97 0 0);
    --card: oklch(0.18 0 0);
    --primary: oklch(0.72 0.12 195);           /* #4DD0E1 — brighter on dark */
    --primary-text: oklch(0.72 0.12 195);      /* Dark mode: same as primary (8.03:1 on dark bg) */
    --destructive: oklch(0.65 0.22 27);
    --border: oklch(0.28 0.005 0);
    --ring: oklch(0.72 0.12 195);
  }
}

@layer utilities {
  /* ✅ NEW (FLAG-8): Accessible text utility */
  .text-primary-text {
    color: var(--primary-text);
  }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}

@layer base {
  *:focus-visible {
    outline: 2px solid var(--ring);
    outline-offset: 2px;
    border-radius: var(--radius);
  }
}
```

**Contrast Verification (computed programmatically):**

| Token | Hex Approx | On White | On Dark (#262626) | WCAG AA |
|-------|-----------|----------|-------------------|---------|
| `--primary` | `#00ACC1` | 2.74:1 | — | ❌ text, ✅ bg-only |
| `--primary-text` | `#00838F` | **4.52:1** | — | ✅ AA normal text |
| `--primary` (dark) | `#4DD0E1` | — | **8.03:1** | ✅ AAA |
| `--destructive` | `#DA1E28` on `#FFF1F1` | 5.89:1 | — | ✅ AA |
| `--warning` | `#92400E` on `#FFF8E1` | 6.67:1 | — | ✅ AA |
| `--success` | `#198038` on `#DEFBE6` | 4.55:1 | — | ✅ AA |

**⛔ Rule:** Never use `text-primary` for text on light backgrounds. Use `text-primary-text`.

### 2.4 Zustand v5 Stores — Strict Separation from Server State *(CHANGED)*

```typescript
// src/stores/auth.ts — ⚠️ REFACTORED (FLAG-1): Clerk sync-only cache
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

interface AuthState {
  token: string | null;
  tenantId: string | null;
  role: 'admin' | 'manager' | 'analyst' | 'viewer' | null;
  setAuth: (auth: { token: string | null; tenantId: string | null; role?: string | null }) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>()(
  devtools((set) => ({
    token: null,
    tenantId: null,
    role: null,
    setAuth: ({ token, tenantId, role }) => set({
      token,
      tenantId,
      role: (role as AuthState['role']) ?? null,
    }),
    clear: () => set({ token: null, tenantId: null, role: null }),
  }), { name: 'c2pro-auth' })
);

// ⛔ WRITE RULE: Only AuthSync.tsx may call setAuth() or clear().
// All other files may only READ via useAuthStore(s => s.token) or .getState().
```

```typescript
// src/stores/app-mode.ts — UNCHANGED from v3.0
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { env } from '@/config/env';

export const useAppModeStore = create<{
  mode: 'production' | 'demo';
  demoProjectId: string;
  showDemoBanner: boolean;
  setShowDemoBanner: (show: boolean) => void;
}>()(
  devtools((set) => ({
    mode: env.IS_DEMO ? 'demo' : 'production',
    demoProjectId: '550e8400-e29b-41d4-a716-446655440000',
    showDemoBanner: env.IS_DEMO,
    setShowDemoBanner: (show) => set({ showDemoBanner: show }),
  }), { name: 'c2pro-app-mode' })
);
```

```typescript
// src/stores/sidebar.ts — UNCHANGED from v3.0
// src/stores/filters.ts — UNCHANGED from v3.0
// (See v3.0 TDD for full code)
```

```typescript
// src/stores/processing.ts — ✅ NEW (FLAG-22): Cross-page SSE state
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

interface ProcessingJob {
  stages: Array<{ name: string; progress: number; stage: number }>;
  progress: number;
  complete: boolean;
  score?: number;
  fallbackToPolling: boolean;
}

interface ProcessingState {
  activeJobs: Record<string, ProcessingJob>;
  update: (projectId: string, stage: ProcessingJob['stages'][0]) => void;
  complete: (projectId: string, score: number) => void;
  setFallback: (projectId: string) => void;
  clear: (projectId: string) => void;
}

export const useProcessingStore = create<ProcessingState>()(
  devtools((set) => ({
    activeJobs: {},
    update: (projectId, stage) => set((state) => ({
      activeJobs: {
        ...state.activeJobs,
        [projectId]: {
          ...(state.activeJobs[projectId] ?? { stages: [], progress: 0, complete: false, fallbackToPolling: false }),
          stages: [...(state.activeJobs[projectId]?.stages ?? []), stage],
          progress: stage.progress,
        },
      },
    })),
    complete: (projectId, score) => set((state) => ({
      activeJobs: {
        ...state.activeJobs,
        [projectId]: { ...state.activeJobs[projectId], complete: true, score, progress: 100 },
      },
    })),
    setFallback: (projectId) => set((state) => ({
      activeJobs: {
        ...state.activeJobs,
        [projectId]: { ...state.activeJobs[projectId], fallbackToPolling: true },
      },
    })),
    clear: (projectId) => set((state) => {
      const { [projectId]: _, ...rest } = state.activeJobs;
      return { activeJobs: rest };
    }),
  }), { name: 'c2pro-processing' })
);
```

**Test specification:**
```typescript
// src/stores/processing.test.ts
describe('useProcessingStore', () => {
  it('initializes with empty activeJobs', () => { /* ... */ });
  it('adds a stage to a new project', () => { /* ... */ });
  it('appends stages to existing project', () => { /* ... */ });
  it('marks project as complete with score', () => { /* ... */ });
  it('clears a specific project without affecting others', () => { /* ... */ });
  it('sets fallback polling mode', () => { /* ... */ });
});
```

### 2.5 ScoreCard Component — UNCHANGED from v3.0

*(Full code in v3.0 TDD §2.5 — no changes needed)*

### 2.6 CoherenceGauge — Custom SVG *(REWRITTEN — FLAG-9)*

```tsx
// src/components/features/coherence/CoherenceGauge.tsx
'use client';

import { useReducedMotion } from 'motion/react';
import { cn } from '@/lib/utils';

function getColor(score: number) {
  if (score >= 70) return 'var(--color-severity-low)';    // Green
  if (score >= 40) return 'var(--color-severity-medium)';  // Amber
  return 'var(--color-severity-critical)';                 // Red
}

function getLabel(score: number) {
  if (score >= 85) return 'Excellent';
  if (score >= 70) return 'Good';
  if (score >= 55) return 'Acceptable';
  if (score >= 40) return 'At Risk';
  return 'Critical';
}

function useCountUp(target: number, duration = 1500) {
  const [value, setValue] = useState(0);
  const raf = useRef(0);
  const reduced = useReducedMotion();
  useEffect(() => {
    if (reduced) { setValue(target); return; }
    const start = performance.now();
    function animate(now: number) {
      const p = Math.min((now - start) / duration, 1);
      setValue(Math.round((1 - Math.pow(1 - p, 4)) * target));
      if (p < 1) raf.current = requestAnimationFrame(animate);
    }
    raf.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf.current);
  }, [target, duration, reduced]);
  return value;
}

import { useState, useRef, useEffect } from 'react';

interface CoherenceGaugeProps {
  score: number;
  documentsAnalyzed: number;
  dataPointsChecked: number;
  calculatedAt?: string;
  size?: number;
  strokeWidth?: number;
}

export function CoherenceGauge({
  score, documentsAnalyzed, dataPointsChecked,
  size = 200, strokeWidth = 12,
}: CoherenceGaugeProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = ((100 - score) / 100) * circumference;
  const color = getColor(score);
  const label = getLabel(score);
  const animated = useCountUp(score);
  const reduced = useReducedMotion();

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size} height={size}
          viewBox={`0 0 ${size} ${size}`}
          role="img"
          aria-label={`Coherence Score: ${score} out of 100, ${label}`}
        >
          {/* Background track */}
          <circle cx={size / 2} cy={size / 2} r={radius}
            fill="none" stroke="var(--muted)" strokeWidth={strokeWidth} />
          {/* Score arc */}
          <circle cx={size / 2} cy={size / 2} r={radius}
            fill="none" stroke={color} strokeWidth={strokeWidth}
            strokeDasharray={circumference} strokeDashoffset={progress}
            strokeLinecap="round"
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            style={{
              transition: reduced ? 'none' : `stroke-dashoffset ${1500}ms cubic-bezier(0.16, 1, 0.3, 1)`,
            }}
          />
          {/* Score text */}
          <text x="50%" y="46%" textAnchor="middle" dominantBaseline="central"
            className="fill-foreground font-mono text-4xl font-bold tabular-nums">
            {animated}
          </text>
          <text x="50%" y="60%" textAnchor="middle"
            className="fill-muted-foreground text-sm">
            /100
          </text>
        </svg>
      </div>

      <span className="rounded-full px-3 py-1 text-sm font-medium"
        style={{ color, backgroundColor: `color-mix(in oklch, ${color} 10%, transparent)` }}>
        {label}
      </span>

      <p className="text-muted-foreground max-w-xs text-center text-xs">
        Based on <span className="font-mono font-medium">{documentsAnalyzed}</span> documents
        and <span className="font-mono font-medium">{dataPointsChecked.toLocaleString()}</span> data points.
      </p>
    </div>
  );
}
```

**Why SVG over Recharts (FLAG-9):** Recharts `RadialBarChart` adds ~50-65KB gzipped (d3 dependencies). Custom SVG adds ~2KB. Dashboard budget: 80KB. Recharts is retained for complex charts (Stakeholder scatter, admin) via lazy loading.

**Test specification:**
```typescript
// src/components/features/coherence/CoherenceGauge.test.tsx
describe('CoherenceGauge', () => {
  it('renders score in aria-label', () => { /* ... */ });
  it('renders "Critical" label for score < 40', () => { /* ... */ });
  it('renders "Excellent" label for score >= 85', () => { /* ... */ });
  it('respects prefers-reduced-motion', () => { /* ... */ });
  it('renders documents and data points count', () => { /* ... */ });
  it('uses correct severity color for score range', () => { /* ... */ });
});
```

### 2.7 SSE Document Processing Hook *(REWRITTEN — FLAG-3, FLAG-22)*

```typescript
// src/hooks/useDocumentProcessing.ts
'use client';

import { useEffect, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useProcessingStore } from '@/stores/processing';
import { env } from '@/config/env';

export function useDocumentProcessing(projectId: string) {
  const queryClient = useQueryClient();
  const { update, complete, setFallback } = useProcessingStore();
  const stages = useProcessingStore((s) => s.activeJobs[projectId]?.stages ?? []);
  const progress = useProcessingStore((s) => s.activeJobs[projectId]?.progress ?? 0);
  const isComplete = useProcessingStore((s) => s.activeJobs[projectId]?.complete ?? false);

  const startStream = useCallback(() => {
    // FLAG-3: withCredentials sends Clerk's __clerk_db_jwt cookie for auth
    const source = new EventSource(
      `${env.API_BASE_URL}/api/v1/projects/${projectId}/process/stream`,
      { withCredentials: true }
    );

    source.addEventListener('stage', (e) => {
      const stage = JSON.parse(e.data);
      update(projectId, stage);
    });

    source.addEventListener('complete', async (e) => {
      const result = JSON.parse(e.data);
      complete(projectId, result.global_score);
      // FLAG-25: Await refetch BEFORE allowing navigation
      await queryClient.refetchQueries({
        predicate: (q) =>
          q.queryKey[0] === 'coherence' ||
          (q.queryKey[0] === 'alerts' && q.queryKey.includes(projectId)),
      });
      source.close();
    });

    source.addEventListener('error', () => {
      // Safari SSE reconnection quirk: auto-reconnects but may drop after ~60s
      setTimeout(() => {
        if (source.readyState === EventSource.CLOSED) {
          setFallback(projectId);
        }
      }, 5000);
    });

    return () => source.close();
  }, [projectId, queryClient, update, complete, setFallback]);

  useEffect(() => {
    if (isComplete) return;
    const cleanup = startStream();
    return cleanup;
  }, [startStream, isComplete]);

  return { stages, progress, isComplete };
}
```

**Test specification:**
```typescript
// src/hooks/useDocumentProcessing.test.ts
describe('useDocumentProcessing', () => {
  it('receives SSE stages and updates processing store', async () => { /* ... */ });
  it('invalidates coherence and alerts queries on complete', async () => { /* ... */ });
  it('sets fallback mode when EventSource closes unexpectedly', async () => { /* ... */ });
  it('does not reconnect after successful completion', async () => { /* ... */ });
  it('cleans up EventSource on unmount', async () => { /* ... */ });
});
```

---

## 3. Directory Structure (App Router v4.0)

```
apps/web/
├── pnpm-workspace.yaml             # ✅ NEW (FLAG-16)
├── openapi.json                     # Backend OpenAPI spec (source of truth)
├── orval.config.ts
├── vitest.config.ts
├── playwright.config.ts
├── tsconfig.json
│
└── src/
    ├── app/
    │   ├── layout.tsx               # Root: next/font/local (FLAG-10), Providers wrapper
    │   ├── globals.css              # Tailwind v4 @theme + --primary-text (FLAG-8)
    │   ├── not-found.tsx
    │   ├── error.tsx                # Root error boundary
    │   │
    │   ├── (auth)/                  # Public auth routes
    │   │   ├── layout.tsx
    │   │   ├── login/page.tsx
    │   │   ├── register/page.tsx
    │   │   └── forgot-password/page.tsx
    │   │
    │   ├── (onboarding)/            # 4-step onboarding
    │   │   ├── layout.tsx
    │   │   ├── welcome/page.tsx
    │   │   ├── first-upload/page.tsx
    │   │   ├── processing/page.tsx
    │   │   └── guided-review/page.tsx
    │   │
    │   ├── (app)/             # Protected app
    │   │   ├── layout.tsx           # AppSidebar + Header + DemoBanner + ProcessingIndicator
    │   │   ├── error.tsx            # Dashboard error boundary
    │   │   ├── page.tsx             # Redirect → projects
    │   │   ├── projects/
    │   │   │   ├── page.tsx         # Project list (Server Component)
    │   │   │   └── [projectId]/
    │   │   │       ├── layout.tsx   # Project tabs
    │   │   │       ├── coherence/
    │   │   │       │   ├── page.tsx     # PPR: SVG Gauge + Breakdown
    │   │   │       │   └── error.tsx    # Coherence error boundary
    │   │   │       ├── evidence/
    │   │   │       │   ├── page.tsx
    │   │   │       │   ├── error.tsx
    │   │   │       │   └── [clauseId]/page.tsx
    │   │   │       ├── alerts/page.tsx
    │   │   │       ├── stakeholders/page.tsx
    │   │   │       ├── documents/page.tsx
    │   │   │       ├── procurement/page.tsx
    │   │   │       └── settings/page.tsx
    │   │   └── settings/page.tsx
    │   │
    │   └── (admin)/                 # Internal admin (Tremor)
    │       ├── layout.tsx
    │       ├── error.tsx            # Admin error boundary
    │       ├── tenants/page.tsx
    │       ├── users/page.tsx
    │       ├── ai-costs/page.tsx
    │       ├── audit/page.tsx
    │       └── system/page.tsx
    │
    ├── components/
    │   ├── ui/                      # Shadcn/ui primitives
    │   ├── providers/
    │   │   └── AuthSync.tsx         # ✅ NEW (FLAG-1,4): Clerk→Zustand bridge
    │   ├── features/
    │   │   ├── coherence/           # CoherenceGauge (SVG), ScoreCard, WeightAdjuster
    │   │   ├── evidence/            # EvidenceViewer, PDFRenderer, Watermark
    │   │   ├── alerts/              # AlertReviewCenter, ApprovalModal, SeverityBadge
    │   │   ├── documents/           # DocumentUpload, ProcessingStepper
    │   │   ├── stakeholders/        # StakeholderMap, RACIMatrix
    │   │   ├── projects/            # ProjectList, ProjectCard
    │   │   └── admin/               # TenantOverview, AICostDashboard
    │   └── layout/                  # AppSidebar, Header, DemoBanner, MobileBottomNav
    │
    ├── lib/
    │   ├── api/
    │   │   ├── client.ts            # ⚠️ REWRITTEN (FLAG-1,2,5): Axios + AuthStore
    │   │   └── generated/           # ⚠️ AUTO-GENERATED by Orval — DO NOT EDIT
    │   ├── auth/
    │   │   └── permissions.ts       # RBAC gates (UX only)
    │   ├── utils.ts
    │   └── constants.ts
    │
    ├── stores/                      # Zustand (client-only) — 6 stores
    │   ├── auth.ts                  # ⚠️ REFACTORED (FLAG-1): Clerk sync cache
    │   ├── app-mode.ts
    │   ├── sidebar.ts
    │   ├── filters.ts
    │   ├── onboarding.ts
    │   └── processing.ts            # ✅ NEW (FLAG-22): SSE state persistence
    │
    ├── hooks/
    │   ├── useCountUp.ts
    │   ├── useMediaQuery.ts
    │   └── useDocumentProcessing.ts # ⚠️ REWRITTEN (FLAG-3,22): withCredentials + Zustand
    │
    ├── fonts/                       # ✅ NEW (FLAG-10): Local font files
    │   ├── InterVariable-roman.woff2
    │   ├── InterVariable-italic.woff2
    │   └── JetBrainsMono-Regular.woff2
    │
    ├── mocks/
    │   ├── browser.ts, node.ts
    │   ├── handlers/
    │   │   ├── generated/           # ⚠️ AUTO-GENERATED by Orval
    │   │   └── custom/
    │   │       └── processing-stream.ts  # ✅ NEW (FLAG-12): SSE test handler
    │   └── db.ts
    │
    ├── tests/                       # ✅ NEW: Shared test infrastructure
    │   ├── test-utils.tsx           # renderWithProviders + Clerk mock (FLAG-26)
    │   ├── setup.ts                 # Vitest global setup
    │   └── integration/             # Page-level integration tests
    │
    ├── config/env.ts
    ├── middleware.ts                 # Clerk route protection
    └── instrumentation.ts           # MSW server-side
```

**Convention rules:**
1. **No cross-feature imports** — `coherence/` cannot import from `alerts/`. Shared logic goes to `lib/`.
2. **Co-located unit tests** — `ScoreCard.test.tsx` lives next to `ScoreCard.tsx`.
3. **Integration tests** — in `src/tests/integration/`.
4. **E2E tests** — in `e2e/` at project root.
5. **Generated code never committed** — `generated/` directories in `.gitignore`, CI regenerates.

---

## 4. Expert Engineering Decisions

### 4.1 Frontend Architect — Next.js 15 Migration & PPR

*(UNCHANGED from v3.0 — see v3.0 TDD §4.1 for full details)*

**Key:** PPR enabled only on `coherence/page.tsx` and `projects/page.tsx`. Static shell renders instantly, dynamic holes stream via Suspense.

### 4.2 Performance Engineer — Bundle Budgets *(CORRECTED — FLAG-9, FLAG-10)*

| Route | Budget (gzipped) | Strategy | v3.0 Budget |
|-------|-----------------|----------|-------------|
| Shared JS | ≤ 90 KB | React Compiler tree-shaking | 90 KB (same) |
| Dashboard | ≤ **80 KB** | **Custom SVG gauge** + ScoreCards | ↑ from 50 KB |
| Evidence Viewer | ≤ 120 KB | PDF viewer `next/dynamic ssr:false` | 120 KB (same) |
| Admin | ≤ **100 KB** | Tremor lazy, admin-only chunk | ↑ from 80 KB |
| Fonts | ≤ **40 KB** | `next/font/local` latin subset | ↓ from ~140 KB |

**Font loading (FLAG-10):**
```typescript
// src/app/layout.tsx
import localFont from 'next/font/local';

const inter = localFont({
  src: [
    { path: '../fonts/InterVariable-roman.woff2', style: 'normal' },
    { path: '../fonts/InterVariable-italic.woff2', style: 'italic' },
  ],
  display: 'swap',
  variable: '--font-sans',
  preload: true,
});

const jetbrainsMono = localFont({
  src: '../fonts/JetBrainsMono-Regular.woff2',
  display: 'swap',
  variable: '--font-mono',
  preload: false, // Code blocks only — lazy load
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={`${inter.variable} ${jetbrainsMono.variable}`} suppressHydrationWarning>
      <body className="font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

**Lazy loading pattern (Recharts reserved for complex charts only):**
```tsx
// Complex charts: lazy-loaded via next/dynamic
const StakeholderChart = dynamic(
  () => import('./StakeholderScatter').then(m => m.StakeholderScatter),
  { ssr: false, loading: () => <Skeleton className="h-[400px]" /> }
);

// PDF viewer: NEVER import at module scope (~600KB)
const PDFViewerCore = dynamic(
  () => import('@react-pdf-viewer/core').then((mod) => mod.Viewer),
  { ssr: false, loading: () => <Skeleton className="h-[600px] w-full" /> }
);
```

### 4.3 Security Engineer — Dynamic PDF Watermarks *(CORRECTED — FLAG-31)*

Canvas overlay rendering semi-transparent diagonal text. `pointer-events: none` and `print:hidden` via CSS.

```typescript
// ⚠️ CHANGED (FLAG-31): Use pseudonymized ID, not raw email
const watermarkText = `${user.publicMetadata.shortId} · ${format(new Date(), 'yyyy-MM-dd HH:mm')}`;
// Real email ↔ shortId mapping stored in backend audit_log table only
```

### 4.4 AI UX Engineer — SSE Streaming

*(See §2.7 for rewritten hook. Demo mode simulates with MSW streaming handler — see §8.5.)*

### 4.5 Mobile/Responsive Engineer *(CORRECTED — FLAG-18)*

```
Desktop (≥1280px):   Split pane (react-resizable-panels)
                     [PDF Viewer  |  Alert Sidebar]

Tablet (768-1279px): Stacked with expandable
                     [PDF Viewer (70vh)]
                     [Alert Sidebar (30vh, expandable)]

Mobile (≤767px):     Tab interface
                     [PDF] [Alerts]   ← tab bar
                     [Full-width content]
                     Tapping alert → switches to PDF tab, scrolls to clause
```

### 4.6 A11y Developer *(CORRECTED — FLAG-7, FLAG-8)*

**Keyboard shortcuts are FOCUS-SCOPED (WCAG 2.1.4):**
```tsx
// Shortcuts only fire when AlertReviewCenter container has focus
<div role="region" aria-label="Alert Review" tabIndex={0} onKeyDown={handleKeyDown}>
  {/* j/k/a/r only work HERE, not globally */}
</div>
```

**Accessibility data table toggle on every chart. Triple-encoded severity. Touch targets ≥24×24px.**

*(See §10 for full accessibility architecture.)*

---

## 5. Sprint Plan (4 × 2-Week Sprints)

### Sprint 1: Infrastructure & Design System (Weeks 1–2)

**Goal:** `pnpm dev:demo` shows styled app shell with mock data. All CRITICAL flags resolved.

| ID | Task | Days | Flag | Deliverable |
|----|------|------|------|-------------|
| S1-01 | Next.js 15.3 init + Turbopack + `pnpm-workspace.yaml` | 1 | FLAG-16 | `apps/web/` boots <2s |
| S1-02 | Tailwind v4 CSS-first + `--primary-text` token | 2 | **FLAG-8** | All tokens, 4.52:1 contrast |
| S1-03 | `next/font/local` Inter + JetBrains Mono | 0.5 | **FLAG-10** | ~40KB fonts, `font-display:swap` |
| S1-04 | Shadcn/ui init + 15 base components | 1 | — | Button, Card, Badge, Dialog... |
| S1-05 | App shell (sidebar + header + breadcrumbs) | 2 | — | Responsive layout |
| S1-06 | Clerk auth + **AuthSync component** | 1.5 | **FLAG-1,2,4** | Sole auth source, org-switch cache clear |
| S1-07 | Refactored `stores/auth.ts` (sync-only) | 0.5 | **FLAG-1,5** | No `require()`, Clerk-only write |
| S1-08 | Zustand stores (app-mode, sidebar, filters) | 0.5 | — | 4 stores |
| S1-09 | MSW v2 setup (browser + node + instrumentation) | 1 | — | Demo mode active |
| S1-10 | Orval config + first codegen + delete manual queryKeys | 1 | **FLAG-21** | Generated hooks, single key source |
| S1-11 | **Test infrastructure** (test-utils + Clerk mock) | 0.5 | **FLAG-26** | Shared test wrapper |
| S1-12 | 37 tests (30 unit + 5 integration + 2 E2E) | 2 | **FLAG-11** | 80%+ coverage on touched code |
| S1-13 | CI pipeline (typecheck + lint + test + orval --check) | 0.5 | — | Green CI |
| S1-14 | Sentry error tracking (no Replay) + demo banner + dark mode | 0.5 | — | Error capture |
| S1-15 | Document layer rules ADR | 0.25 | **FLAG-6** | Server Components may fetch directly |

**Sprint 1 resolves: FLAG-1, 2, 4, 5, 6, 8, 10, 11, 16, 21, 26 (11 flags)**

**Acceptance:** Login → empty dashboard with sidebar/header/demo banner. Auth exclusively via Clerk→AuthSync→Zustand. `text-primary-text` on all light backgrounds. CI green. 37 tests passing.

### Sprint 2: Dual-Mode Pipeline & Core Data (Weeks 3–4)

**Goal:** Project list and Coherence Dashboard render with real/mock data.

| ID | Task | Days | Flag | Deliverable |
|----|------|------|------|-------------|
| S2-01 | @mswjs/data seed models (8 entities) | 2 | — | Deterministic demo |
| S2-02 | Custom MSW handlers + **SSE streaming handler** | 2 | **FLAG-12** | Test-ready stream |
| S2-03 | Orval CI check + bundle analyzer | 1 | **FLAG-9** | Budget enforcement |
| S2-04 | `useProcessingStore` (Zustand) | 0.5 | **FLAG-22** | Cross-page state |
| S2-05 | Project list page (Server Component) | 2 | — | Tenant-filtered |
| S2-06 | Project detail layout (7 tabs) | 1 | — | Tab navigation |
| S2-07 | **Custom SVG CoherenceGauge** + 6 ScoreCards | 2 | **FLAG-9** | <80KB |
| S2-08 | Weight adjuster (sliders, sum=100%) | 1.5 | — | PUT via Orval |
| S2-09 | Document upload (drag-drop, PDF/XLSX/BC3) | 2 | — | Chunked |
| S2-10 | **SSE processing stepper** + `withCredentials` | 1.5 | **FLAG-3** | Authenticated stream |
| S2-11 | Three-layer SC test strategy | 0.5 | **FLAG-13** | Documented approach |
| S2-12 | 51 tests (35 unit + 12 integration + 4 E2E) | 3 | — | 88 cumulative |

**Sprint 2 resolves: FLAG-3, 9, 12, 13, 22 (5 flags)**

**Acceptance:** Project → Coherence Score (animated SVG) → adjust weights → upload → SSE stepper. Dashboard ≤80KB. 88 tests passing.

### Sprint 3: Core Views & Evidence Viewer (Weeks 5–6)

**Goal:** All P0 views functional. WCAG audit pass 1. GDPR consent.

| ID | Task | Days | Flag | Deliverable |
|----|------|------|------|-------------|
| S3-01 | PDF renderer (lazy) + clause highlighting | 3 | — | ≤120KB |
| S3-02 | **Mobile Evidence Viewer** (tab interface) | 1 | **FLAG-18** | Responsive |
| S3-03 | Dynamic watermark (**pseudonymized ID**) | 0.5 | **FLAG-31** | No raw PII |
| S3-04 | Alert Review Center + approve/reject modal | 2 | — | Full CRUD |
| S3-05 | **Focus-scoped keyboard shortcuts** | 0.5 | **FLAG-7** | WCAG 2.1.4 |
| S3-06 | **Alert undo + double invalidation** | 0.5 | **FLAG-17** | Coherence stays fresh |
| S3-07 | Severity badge + Stakeholder Map + RACI | 3 | — | Scatter + grid |
| S3-08 | Legal disclaimer modal (Gate 8) | 1 | — | Backend-persisted |
| S3-09 | **Cookie consent banner** | 0.5 | **FLAG-14** | GDPR compliance |
| S3-10 | `sessionStorage` filter persistence | 0.25 | **FLAG-30** | Preserved on refresh |
| S3-11 | **Onboarding sample project** frontend | 1 | **FLAG-19** | Time-to-value <5min |
| S3-12 | A11y audit pass 1 + responsive pass (tablet) | 2 | — | Zero critical violations |
| S3-13 | 61 tests (40 unit + 15 integration + 6 E2E) | 3 | — | 149 cumulative |
| S3-14 | Chromatic integration | 0.5 | — | Visual snapshots |

**Sprint 3 resolves: FLAG-7, 14, 17, 18, 19, 30, 31 (7 flags)**

### Sprint 4: Admin Portal, Polish & Production (Weeks 7–8)

**Goal:** Production-ready. Admin portal. Lighthouse ≥90. WCAG 2.2 AA verified.

| ID | Task | Days | Flag | Deliverable |
|----|------|------|------|-------------|
| S4-01 | Admin layout + Tremor (lazy) | 2 | FLAG-24 | Role-gated admin |
| S4-02 | Tenant mgmt, AI cost dashboard, audit trail | 4 | — | Admin views |
| S4-03 | Onboarding flow (4 steps, full) | 2 | — | Welcome→Upload→Process→Review |
| S4-04 | Error boundaries + loading skeletons | 1 | — | Zero CLS |
| S4-05 | Performance optimization (Lighthouse ≥90) | 2 | — | Verified targets |
| S4-06 | WCAG 2.2 full audit (NVDA + VoiceOver) | 2 | — | Manual SR testing |
| S4-07 | `refetchOnWindowFocus` for coherence/alerts | 0.5 | FLAG-23 | Cross-tab freshness |
| S4-08 | Command palette scope | 0.5 | FLAG-29 | `Cmd+K` navigation |
| S4-09 | 43 tests (27 unit + 10 integration + 6 E2E) | 3 | FLAG-28 | **192 total** |
| S4-10 | OpenTelemetry + Sentry correlation | 1 | — | Frontend→backend traces |
| S4-11 | Production deploy checklist | 0.5 | — | All items ✅ |

**Sprint 4 resolves: FLAG-23, 24, 28, 29 + monitoring 15, 20, 25, 27**

---

## 6. Technical Risks & Mitigation

### 6.1 High Risk

| ID | Risk | P | I | Mitigation |
|----|------|---|---|------------|
| R1 | **Tailwind v4 instability** | High | High | Pin ≥4.1. Keep CSS var approach for v3.4 rollback. +2 days buffer. |
| R2 | **React Compiler breaks 3rd-party libs** | Med | High | `"use no memo"` per-component. Test all chart/pdf components. |
| R3 | **Orval codegen drift** | High | Med | `orval --check` in CI. Weekly backend sync. |
| R4 | **PPR hydration mismatches** | Med | Med | Per-route enable. E2E testing. Disable flag as fallback. |
| R5 | **PDF viewer bundle size (600KB)** | Med | High | `next/dynamic ssr:false`. Never module-scope import. |
| R6 | **MSW + Server Components** | High | High | `instrumentation.ts` for server-side MSW. Test both paths. |
| R7 | **SSE authentication failure** (NEW) | Med | High | `withCredentials:true` + backend cookie validation. Fetch+ReadableStream fallback. |
| R8 | **Cross-tenant data leakage on org switch** (NEW) | Low | Critical | `queryClient.clear()` in AuthSync on org change. |
| R9 | **GDPR non-compliance at Beta launch** (NEW) | Med | High | Cookie consent banner Sprint 3. No Sentry Replay without consent. |
| R10 | **Primary color fails WCAG** (NEW) | Resolved | — | `--primary-text` token. ESLint rule to flag `text-primary`. |

### 6.2 Contingency Table

| Trigger | Fallback | Time Impact |
|---------|----------|-------------|
| Tailwind v4 blocker | Fall back to v3.4 (CSS vars still work) | +0 days |
| React Compiler breaks Recharts | `"use no memo"` on chart components | +0.5 days |
| PPR hydration errors | Disable `ppr` flag — full SSR fallback | +0 days |
| Orval can't generate MSW handlers | Manual MSW handlers from Zod schemas | +3 days |
| PDF viewer exceeds budget | Switch to `react-pdf` with custom highlight | +2 days |
| SSE withCredentials fails (backend) | Switch to `fetch()` + `ReadableStream` with Bearer header | +1 day |
| Clerk session cookie not validated by backend | Sign short-lived URL tokens via REST endpoint | +2 days |

---

## 7. Appendices — Configuration

### 7.1 `next.config.ts` *(CORRECTED — CSP strengthened)*

```typescript
import type { NextConfig } from 'next';
import { withSentryConfig } from '@sentry/nextjs';

const nextConfig: NextConfig = {
  experimental: {
    ppr: 'incremental',
    reactCompiler: true,
    optimizePackageImports: ['lucide-react', 'recharts', 'date-fns', 'motion'],
    instrumentationHook: true,
  },
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '*.r2.cloudflarestorage.com' },
    ],
  },
  webpack: (config) => { config.resolve.alias.canvas = false; return config; },
  async headers() {
    return [{
      source: '/(.*)',
      headers: [
        {
          key: 'Content-Security-Policy',
          value: [
            "default-src 'self'",
            "script-src 'self' 'unsafe-eval' 'unsafe-inline' https://clerk.c2pro.io",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: blob: https://*.r2.cloudflarestorage.com",
            "connect-src 'self' https://api.c2pro.io wss://api.c2pro.io https://clerk.c2pro.io https://*.ingest.sentry.io",
            "worker-src blob: 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
          ].join('; '),
        },
        { key: 'X-Frame-Options', value: 'DENY' },
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
      ],
    }];
  },
};

export default withSentryConfig(nextConfig, {
  org: 'c2pro', project: 'web', silent: true, hideSourceMaps: true,
});
```

### 7.2 `postcss.config.js` — UNCHANGED
```javascript
export default { plugins: { '@tailwindcss/postcss': {} } };
```

### 7.3 State Boundary Rules *(CORRECTED — FLAG-1)*

```
ZUSTAND (Client State)              TANSTACK QUERY (Server State)
─────────────────────               ──────────────────────────────
✅ Auth token cache (CLERK-SYNCED)  ✅ All API GET responses
✅ Sidebar state                    ✅ Mutation results
✅ Theme preference                 ✅ Polling data (doc status)
✅ Filter selections                ✅ Cached computations
✅ App mode (demo/production)       
✅ Processing stages (SSE)
✅ Onboarding step

❌ NEVER: API response data         ❌ NEVER: UI preferences
❌ NEVER: Server-computed values    ❌ NEVER: Auth tokens

⛔ Auth WRITE rule: Only AuthSync.tsx writes to auth store.
⛔ Query Key rule: Only Orval-generated keys. No manual queryKeys.
```

---

## 8. Test-Driven Development Architecture *(NEW — FLAG-11, 12, 13, 26)*

> **Supersedes:** `FRONTEND_TESTING_PLAN.md` (deprecated — written for Next.js 14 + custom JWT auth)

### 8.1 Testing Pyramid

```
                    /\
                   /  \
                  / E2E \           10% — 18 Playwright specs (dual-mode)
                 /------\
                /        \
               /Integration\       30% — 42 page-level tests with MSW
              /------------\
             /              \
            /  Unit Tests    \     60% — 132 component/hook/utility tests
           /------------------\
          / Visual Regression  \   Chromatic snapshots (all pages, both themes)
         /──────────────────────\
```

### 8.2 Test Infrastructure

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/tests/setup.ts'],
    css: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'html'],
      thresholds: {
        statements: 80,
        branches: 75,
        functions: 80,
        lines: 80,
      },
      exclude: [
        'src/lib/api/generated/**',
        'src/mocks/**',
        '**/*.stories.tsx',
        '**/*.test.tsx',
      ],
    },
  },
  resolve: { alias: { '@': '/src' } },
});
```

```typescript
// src/tests/test-utils.tsx (FLAG-26: includes Clerk mock)
import { render, type RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'next-themes';

// Mock Clerk
vi.mock('@clerk/nextjs', () => ({
  ClerkProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({ isSignedIn: true, getToken: async () => 'test-token-jwt' }),
  useUser: () => ({
    user: { id: 'user_test123', emailAddresses: [{ emailAddress: 'test@c2pro.io' }] },
  }),
  useOrganization: () => ({ organization: { id: 'org_test456' } }),
  auth: () => ({ userId: 'user_test123' }),
}));

function AllProviders({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="light">
        {children}
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export function renderWithProviders(ui: React.ReactElement, options?: RenderOptions) {
  return render(ui, { wrapper: AllProviders, ...options });
}

export * from '@testing-library/react';
export { renderWithProviders as render };
```

### 8.3 Three-Layer Server Component Test Strategy (FLAG-13)

```
Layer 1 — Unit (Vitest + RTL):
  ✅ Client Components in isolation (CoherenceGauge, ScoreCard, AlertTable)
  ❌ CANNOT render async Server Components in jsdom

Layer 2 — Integration (Vitest + MSW):
  ✅ Orval-generated hooks with MSW handlers
  ✅ Mutations with optimistic updates
  ❌ CANNOT test full page orchestration

Layer 3 — E2E (Playwright):
  ✅ Full page rendering including Server Components
  ✅ Dual-mode matrix (production + demo)
  ✅ Accessibility audit via @axe-core/playwright
```

### 8.4 Test Phasing by Sprint

| Sprint | Unit | Integration | E2E | Cumulative |
|--------|------|-------------|-----|------------|
| 1 | 30 | 5 | 2 | **37** |
| 2 | 35 | 12 | 4 | **88** |
| 3 | 40 | 15 | 6 | **149** |
| 4 | 27 | 10 | 6 | **192** |

### 8.5 SSE Streaming Test Handler (FLAG-12)

```typescript
// src/mocks/handlers/custom/processing-stream.ts
import { http, HttpResponse } from 'msw';

export const processingStreamHandler = http.get(
  '/api/v1/projects/:projectId/process/stream',
  () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        const stages = [
          { event: 'stage', data: { name: 'Extracting text', progress: 16, stage: 1 } },
          { event: 'stage', data: { name: 'Identifying clauses', progress: 33, stage: 2 } },
          { event: 'stage', data: { name: 'Cross-referencing', progress: 50, stage: 3 } },
          { event: 'stage', data: { name: 'Detecting anomalies', progress: 66, stage: 4 } },
          { event: 'stage', data: { name: 'Calculating weights', progress: 83, stage: 5 } },
          { event: 'complete', data: { global_score: 78, documents_analyzed: 8 } },
        ];

        for (const s of stages) {
          await new Promise(r => setTimeout(r, 50));
          controller.enqueue(encoder.encode(`event: ${s.event}\ndata: ${JSON.stringify(s.data)}\n\n`));
        }
        controller.close();
      },
    });

    return new HttpResponse(stream, {
      headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
    });
  }
);
```

### 8.6 Test Specification Index

| Component/Hook | Unit Tests | Integration | E2E | Sprint |
|---------------|-----------|-------------|-----|--------|
| AuthSync | 5 | 2 | 1 | 1 |
| apiClient (Axios) | 7 | — | — | 1 |
| useAuthStore | 4 | — | — | 1 |
| useAppModeStore | 3 | — | — | 1 |
| useSidebarStore | 3 | — | — | 1 |
| useFilterStore | 5 | — | — | 1 |
| App Shell (sidebar/header) | 3 | 3 | 1 | 1 |
| CoherenceGauge (SVG) | 6 | — | — | 2 |
| ScoreCard | 5 | — | — | 2 |
| WeightAdjuster | 8 | 3 | 1 | 2 |
| useDocumentProcessing | 5 | 3 | 1 | 2 |
| useProcessingStore | 6 | — | — | 2 |
| Project List | 10 | 5 | 2 | 2 |
| Evidence Viewer | 12 | 4 | 2 | 3 |
| Alert Review Center | 10 | 5 | 2 | 3 |
| Stakeholder Map + RACI | 14 | 5 | 2 | 3 |
| Document Upload | 8 | 4 | 2 | 3 |
| Admin Portal | 10 | 5 | 2 | 4 |
| Onboarding Flow | 8 | 3 | 1 | 4 |
| UI Primitives (15 components) | 15 | — | — | 1-2 |
| **TOTAL** | **132** | **42** | **18** | **= 192** |

---

## 9. Security Architecture *(NEW)*

### 9.1 Auth Flow Summary

```
User → Clerk (login/MFA/SSO) → Session cookie + JWT
  → AuthSync → Zustand cache (sync every 50s)
    → Axios interceptor reads .getState() → Bearer header
    → SSE EventSource uses withCredentials → Cookie header
  → Middleware validates session on every route
```

### 9.2 RBAC Gates (UX Convenience — Server Enforces)

```typescript
// src/lib/auth/permissions.ts
type Role = 'admin' | 'manager' | 'analyst' | 'viewer';
type Permission = 'project:write' | 'alert:approve' | 'weight:adjust' | 'admin:access';

const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  admin: ['project:write', 'alert:approve', 'weight:adjust', 'admin:access'],
  manager: ['project:write', 'alert:approve', 'weight:adjust'],
  analyst: ['project:write'],
  viewer: [],
};

export function RequirePermission({ permission, children, fallback = null }: {
  permission: Permission; children: React.ReactNode; fallback?: React.ReactNode;
}) {
  const role = useAuthStore((s) => s.role);
  if (!ROLE_PERMISSIONS[role ?? 'viewer']?.includes(permission)) return <>{fallback}</>;
  return <>{children}</>;
}
```

### 9.3 GDPR Cookie Consent (FLAG-14)

**Sprint 1:** Sentry error tracking only (legitimate interest — no consent needed).
**Sprint 3:** Cookie consent banner before enabling Sentry Replay.

Categories: Essential (always on), Analytics (opt-in). Sentry Replay dynamically initialized after consent.

### 9.4 XSS Prevention Checklist

| Vector | Mitigation | Enforcement |
|--------|-----------|-------------|
| `dangerouslySetInnerHTML` | Audit: must be zero in codebase | `rg` in CI |
| PDF annotations | Sanitize with DOMPurify before render | Code review |
| URL params (clauseId) | Validate against UUID regex | Zod schema |
| SSE event data | Parse with `JSON.parse` + Zod | Hook code |
| Markdown (if added) | `rehype-sanitize` with strict schema | Config |

---

## 10. Accessibility Architecture *(NEW — FLAG-7, FLAG-8)*

### 10.1 WCAG 2.2 AA Compliance Targets

| Criterion | Status | Implementation |
|-----------|--------|----------------|
| 1.1.1 Non-text Content | ✅ | All images have alt text; charts have `aria-label` |
| 1.3.1 Info and Relationships | ✅ | Semantic HTML; tables use `<th scope>` |
| 1.4.3 Contrast (Minimum) | ✅ | `--primary-text` at 4.52:1 (FLAG-8 resolved) |
| 1.4.11 Non-text Contrast | ✅ | UI controls ≥3:1 against background |
| 2.1.1 Keyboard | ✅ | All interactions keyboard-accessible |
| 2.1.4 Character Key Shortcuts | ✅ | Focus-scoped (FLAG-7 resolved) |
| 2.4.7 Focus Visible | ✅ | 2px ring on all focus-visible |
| 2.5.7 Dragging Movements | ✅ | Button alternatives for all drag-and-drop |
| 2.5.8 Target Size | ✅ | Minimum 24×24px, target 44×44px |
| 4.1.2 Name, Role, Value | ✅ | ARIA labels on charts, badges, buttons |

### 10.2 Automated Pipeline

| Tool | Sprint | Scope |
|------|--------|-------|
| `eslint-plugin-jsx-a11y` | 1 | Every commit |
| `@axe-core/playwright` | 3 | E2E a11y tests |
| NVDA + VoiceOver manual | 4 | All P0 flows |
| `@storybook/addon-a11y` | 4 | Component dev |
| Chromatic | 3 | Visual regression (both themes) |

### 10.3 Screen Reader Testing Plan

| Reader | Browser | Priority | Sprint |
|--------|---------|----------|--------|
| NVDA | Firefox/Chrome | P0 | 4 |
| VoiceOver | Safari macOS | P0 | 4 |
| TalkBack | Chrome Android | P1 | Post-launch |

---

## Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| VP Engineering | _________________ | 2026-02-10 | ☐ |
| Frontend Architect | _________________ | __________ | ☐ |
| QA Lead | _________________ | __________ | ☐ |
| Security Lead | _________________ | __________ | ☐ |
| Product Owner | _________________ | __________ | ☐ |
| Accessibility Lead | _________________ | __________ | ☐ |

---

**Document:** C2Pro Technical Design Document v4.0  
**Classification:** INTERNAL — Engineering Team  
**Next Review:** After Sprint 2 completion (Week 4)  
**Flags Resolved:** 31/31 (4 Critical, 8 High, 7 Medium, 12 Low/Monitoring)
