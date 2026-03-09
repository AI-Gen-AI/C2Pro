
# C2Pro v3.0 — Technical Design Document (TDD)

> **Document Type:** Engineering Kick-off — Technical Implementation Plan  
> **Version:** 3.0  
> **Date:** 2026-02-08  
> **Status:** APPROVED — Ready for Sprint Planning  
> **Input:** Master Design & Product Experience Plan v3.0 (approved)  
> **Audience:** Engineering Team, Tech Leads, DevOps  
> **Author:** VP Engineering / Principal Software Architect

---

## Table of Contents

1. [Definitive Technology Stack (v3.0)](#1-definitive-technology-stack-v30)
2. [Architecture Patterns & Code Blueprints](#2-architecture-patterns--code-blueprints)
3. [Directory Structure (App Router v3.0)](#3-directory-structure-app-router-v30)
4. [Expert Engineering Decisions (12 Leads)](#4-expert-engineering-decisions-12-leads)
5. [Sprint Plan (4 × 2-Week Sprints)](#5-sprint-plan-4--2-week-sprints)
6. [Technical Risks & Mitigation](#6-technical-risks--mitigation)
7. [Appendices](#7-appendices)

---

## 1. Definitive Technology Stack (v3.0)

### 1.1 Migration Delta: v2.0 → v3.0

| Category | v2.0 (Current) | v3.0 (Target) | Migration Risk |
|----------|----------------|----------------|----------------|
| Framework | Next.js 14.1 | **Next.js 15.3** (stable) | Medium — PPR, React Compiler |
| React | 18.2 | **19.1** | Low — concurrent features stable |
| CSS Framework | Tailwind 3.4 | **Tailwind 4.1** | High — CSS-first config, new engine |
| OpenAPI Codegen | openapi-typescript 6.7 | **Orval 7.x** | Medium — new toolchain |
| Client State | Zustand 4.4 | **Zustand 5.x** | Low — API compatible |
| Mocking | MSW 2.1 | **MSW 2.7+** | Low — same major version |
| PDF Viewer | react-pdf 7.7 | **@react-pdf-viewer 4.x** | Medium — different API |
| Animation | None | **motion/react 12+** | Low — new addition |
| Charts | Recharts 2.10 | **Recharts 2.15+** | Low — minor bump |
| Testing | Vitest 1.2 + Playwright 1.41 | **Vitest 3.2 + Playwright 1.50** | Low |
| Visual Regression | None | **Chromatic** | Low — new addition |
| Admin Dashboard | None | **Tremor 3.x** | Low — new addition |

### 1.2 Partial `package.json` — Production Dependencies

```jsonc
{
  "name": "@c2pro/web",
  "version": "3.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev --turbopack",
    "dev:demo": "NEXT_PUBLIC_APP_MODE=demo next dev --turbopack",
    "build": "next build",
    "build:demo": "NEXT_PUBLIC_APP_MODE=demo next build",
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
    "chromatic": "chromatic --exit-zero-on-changes"
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
    "@fontsource-variable/inter": "^5.1.1",
    "@fontsource/jetbrains-mono": "^5.1.1",
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
    "@playwright/test": "^1.50.0",
    "@axe-core/playwright": "^4.10.0",
    "storybook": "^8.5.0",
    "@storybook/addon-a11y": "^8.5.0",
    "chromatic": "^11.22.0",
    "eslint": "^9.18.0",
    "eslint-config-next": "^15.3.0",
    "eslint-plugin-jsx-a11y": "^6.10.0",
    "prettier": "^3.4.0",
    "ajv": "^8.17.0"
  }
}
```

### 1.3 Critical Version Pins

| Package | Pinned | Reason |
|---------|--------|--------|
| `next` ≥15.3 | Stable PPR, Turbopack default, React Compiler GA | Required for dashboard streaming |
| `tailwindcss` ≥4.1 | CSS-first config stabilized | v4.0 had oxide engine issues |
| `react` ≥19.1 | Stable concurrent features, `use()` hook | Required by Next.js 15.3 |
| `orval` ≥7.5 | TanStack Query v5 + MSW v2 mock generation | Core of dual-mode pipeline |
| `zustand` ≥5.0 | New `createWithEqualityFn`, ES2018 target | Breaking selectors from v4 |
| `motion` ≥12.0 | `LazyMotion` tree-shaking, React 19 support | Renamed from framer-motion |

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
} as const;
```

#### 2.1.2 Server-Side MSW (Next.js 15 `instrumentation.ts` hook)

```typescript
// src/instrumentation.ts
export async function register() {
  if (process.env.NEXT_PUBLIC_APP_MODE === 'demo') {
    const { server } = await import('@/mocks/node');
    server.listen({ onUnhandledRequest: 'bypass' });
    console.log('[C2Pro] MSW server-side mocking active (demo mode)');
  }
}
```

#### 2.1.3 Client-Side MSW Provider

```tsx
// src/app/providers.tsx
'use client';

import { useState, useEffect, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { ThemeProvider } from 'next-themes';
import { env } from '@/config/env';

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        refetchOnWindowFocus: false,
        retry: env.IS_DEMO ? false : 3,
      },
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
    <QueryClientProvider client={getQueryClient()}>
      <ThemeProvider attribute="class" defaultTheme="light" enableSystem disableTransitionOnChange>
        {children}
      </ThemeProvider>
      {env.IS_DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}
```

### 2.2 Orval Configuration — Single Codegen for Hooks + Mocks

```typescript
// orval.config.ts
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

#### 2.2.1 API Client (Orval mutator)

```typescript
// src/lib/api/client.ts
import Axios, { type AxiosRequestConfig } from 'axios';
import { env } from '@/config/env';

const axiosInstance = Axios.create({
  baseURL: env.API_BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

axiosInstance.interceptors.request.use((config) => {
  const { useAuthStore } = require('@/stores/auth');
  const state = useAuthStore.getState();
  if (state.token) config.headers.Authorization = `Bearer ${state.token}`;
  if (state.tenantId) config.headers['X-Tenant-ID'] = state.tenantId;
  return config;
});

axiosInstance.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      const { useAuthStore } = require('@/stores/auth');
      useAuthStore.getState().logout();
      if (typeof window !== 'undefined') window.location.href = '/login';
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

### 2.3 Design Tokens — Tailwind v4 CSS-First Configuration

```css
/* src/app/globals.css */
@import "tailwindcss";
@import "@fontsource-variable/inter";
@import "@fontsource/jetbrains-mono";

@theme {
  --font-sans: "Inter Variable", "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;

  --radius-sm: 4px;
  --radius-md: 6px;    /* Distinctive non-default */
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
    --primary: oklch(0.56 0.12 195);       /* #00ACC1 */
    --primary-foreground: oklch(1 0 0);
    --secondary: oklch(0.96 0.01 195);
    --secondary-foreground: oklch(0.25 0 0);
    --muted: oklch(0.96 0.005 0);
    --muted-foreground: oklch(0.55 0 0);
    --accent: oklch(0.96 0.01 195);
    --accent-foreground: oklch(0.25 0 0);
    --destructive: oklch(0.55 0.22 27);    /* #DA1E28 */
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
    --primary: oklch(0.72 0.12 195);       /* #4DD0E1 — brighter on dark */
    --destructive: oklch(0.65 0.22 27);
    --border: oklch(0.28 0.005 0);
    --ring: oklch(0.72 0.12 195);
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

### 2.4 Zustand v5 Stores — Strict Separation from Server State

```typescript
// src/stores/app-mode.ts
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
// src/stores/sidebar.ts
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

type SidebarState = 'expanded' | 'collapsed' | 'hidden';

export const useSidebarStore = create<{
  state: SidebarState;
  width: number;
  toggle: () => void;
}>()(
  devtools(persist((set, get) => ({
    state: 'expanded' as SidebarState,
    width: 240,
    toggle: () => {
      const next = get().state === 'expanded' ? 'collapsed' : 'expanded';
      set({ state: next, width: next === 'expanded' ? 240 : 56 });
    },
  }), { name: 'c2pro-sidebar' }), { name: 'c2pro-sidebar' })
);
```

```typescript
// src/stores/filters.ts — with useShallow selector
import { create } from 'zustand';
import { useShallow } from 'zustand/shallow';

type AlertSeverity = 'critical' | 'high' | 'medium' | 'low';
type Category = 'SCOPE' | 'BUDGET' | 'QUALITY' | 'TECHNICAL' | 'LEGAL' | 'TIME';

interface FilterState {
  alertSeverities: AlertSeverity[];
  categories: Category[];
  searchQuery: string;
  toggleSeverity: (s: AlertSeverity) => void;
  toggleCategory: (c: Category) => void;
  setSearchQuery: (q: string) => void;
  resetFilters: () => void;
}

export const useFilterStore = create<FilterState>()((set) => ({
  alertSeverities: [],
  categories: [],
  searchQuery: '',
  toggleSeverity: (s) => set((state) => ({
    alertSeverities: state.alertSeverities.includes(s)
      ? state.alertSeverities.filter((x) => x !== s)
      : [...state.alertSeverities, s],
  })),
  toggleCategory: (c) => set((state) => ({
    categories: state.categories.includes(c)
      ? state.categories.filter((x) => x !== c)
      : [...state.categories, c],
  })),
  setSearchQuery: (q) => set({ searchQuery: q }),
  resetFilters: () => set({ alertSeverities: [], categories: [], searchQuery: '' }),
}));

// Selector helper to prevent unnecessary re-renders
export const useFilterSelectors = () =>
  useFilterStore(useShallow((s) => ({
    alertSeverities: s.alertSeverities,
    categories: s.categories,
    searchQuery: s.searchQuery,
  })));
```

**Hard Rule:** Server data (projects, scores, alerts) lives EXCLUSIVELY in TanStack Query. Never `set()` API response data into Zustand.

### 2.5 ScoreCard Component — Design Tokens in Action

```tsx
// src/components/features/coherence/ScoreCard.tsx
'use client';

import { useRef, useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Target, DollarSign, CheckCircle, Settings, Scale, Clock } from 'lucide-react';

const CATEGORY_CONFIG = {
  SCOPE:     { icon: Target,      color: 'var(--color-chart-scope)',     label: 'Scope' },
  BUDGET:    { icon: DollarSign,  color: 'var(--color-chart-budget)',    label: 'Budget' },
  QUALITY:   { icon: CheckCircle, color: 'var(--color-chart-quality)',   label: 'Quality' },
  TECHNICAL: { icon: Settings,    color: 'var(--color-chart-technical)', label: 'Technical' },
  LEGAL:     { icon: Scale,       color: 'var(--color-chart-legal)',     label: 'Legal' },
  TIME:      { icon: Clock,       color: 'var(--color-chart-time)',      label: 'Time' },
} as const;

function getSeverity(score: number) {
  if (score >= 80) return { label: 'Good',     variant: 'success' as const,      shape: '●' };
  if (score >= 60) return { label: 'Warning',  variant: 'warning' as const,      shape: '◆' };
  return                  { label: 'Critical',  variant: 'destructive' as const,  shape: '▲' };
}

function useCountUp(target: number, duration = 1500) {
  const [value, setValue] = useState(0);
  const raf = useRef(0);
  useEffect(() => {
    const start = performance.now();
    function animate(now: number) {
      const p = Math.min((now - start) / duration, 1);
      setValue(Math.round((1 - Math.pow(1 - p, 4)) * target));
      if (p < 1) raf.current = requestAnimationFrame(animate);
    }
    raf.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(raf.current);
  }, [target, duration]);
  return value;
}

interface ScoreCardProps {
  category: string; score: number; weight: number;
  alertCount: number; onClick?: () => void;
}

export function ScoreCard({ category, score, weight, alertCount, onClick }: ScoreCardProps) {
  const config = CATEGORY_CONFIG[category as keyof typeof CATEGORY_CONFIG];
  const severity = getSeverity(score);
  const animated = useCountUp(score);
  const Icon = config?.icon ?? Target;

  return (
    <Card
      className={cn('cursor-pointer transition-shadow hover:shadow-lg',
        'focus-visible:ring-ring focus-visible:ring-2 focus-visible:ring-offset-2')}
      onClick={onClick} tabIndex={0} role="button"
      aria-label={`${config?.label} score ${score}/100, ${alertCount} alerts, ${severity.label}`}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick?.(); } }}
    >
      <CardContent className="flex items-center gap-4 p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md"
          style={{ backgroundColor: `color-mix(in oklch, ${config?.color} 15%, transparent)` }}>
          <Icon className="h-5 w-5" style={{ color: config?.color }} strokeWidth={1.75} aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-2xl font-bold tabular-nums">{animated}</span>
            <span className="text-muted-foreground text-xs">/ 100</span>
          </div>
          <span className="text-muted-foreground text-sm">
            {config?.label} · <span className="font-mono text-xs">{Math.round(weight * 100)}%</span>
          </span>
        </div>
        <Badge variant={severity.variant} className="shrink-0 gap-1 text-xs">
          <span aria-hidden>{severity.shape}</span>{severity.label}
        </Badge>
        {alertCount > 0 && (
          <span className="bg-destructive/10 text-destructive flex h-6 w-6 items-center justify-center rounded-full font-mono text-xs"
            aria-label={`${alertCount} alerts`}>{alertCount}</span>
        )}
      </CardContent>
    </Card>
  );
}
```

### 2.6 CoherenceGauge — Radial Chart with Count-Up

```tsx
// src/components/features/coherence/CoherenceGauge.tsx
'use client';

import { useMemo } from 'react';
import { RadialBarChart, RadialBar, ResponsiveContainer } from 'recharts';
import { motion, useReducedMotion } from 'motion/react';

function getColor(score: number) {
  if (score >= 70) return 'var(--color-severity-low)';
  if (score >= 40) return 'var(--color-severity-medium)';
  return 'var(--color-severity-critical)';
}

function getLabel(score: number) {
  if (score >= 85) return 'Excellent';
  if (score >= 70) return 'Good';
  if (score >= 55) return 'Acceptable';
  if (score >= 40) return 'At Risk';
  return 'Critical';
}

interface Props {
  score: number; documentsAnalyzed: number;
  dataPointsChecked: number; calculatedAt: string;
}

export function CoherenceGauge({ score, documentsAnalyzed, dataPointsChecked }: Props) {
  const reduced = useReducedMotion();
  const color = getColor(score);
  const data = useMemo(() => [
    { name: 'bg', value: 100, fill: 'var(--muted)' },
    { name: 'score', value: score, fill: color },
  ], [score, color]);

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative h-48 w-48" role="img"
        aria-label={`Coherence Score: ${score}/100, ${getLabel(score)}`}>
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart cx="50%" cy="50%" innerRadius="75%" outerRadius="100%"
            startAngle={90} endAngle={-270} data={data} barSize={12}>
            <RadialBar dataKey="value" cornerRadius={6}
              background={{ fill: 'var(--muted)' }}
              isAnimationActive={!reduced} animationDuration={1500} />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <motion.span className="font-mono text-4xl font-bold tabular-nums" style={{ color }}
            initial={reduced ? {} : { opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: 1.0 }}>
            {score}
          </motion.span>
          <span className="text-muted-foreground text-sm">/100</span>
        </div>
      </div>
      <span className="rounded-full px-3 py-1 text-sm font-medium"
        style={{ color, backgroundColor: `color-mix(in oklch, ${color} 10%, transparent)` }}>
        {getLabel(score)}
      </span>
      <p className="text-muted-foreground max-w-xs text-center text-xs">
        Based on <span className="font-mono font-medium">{documentsAnalyzed}</span> documents
        and <span className="font-mono font-medium">{dataPointsChecked.toLocaleString()}</span> data points.
      </p>
    </div>
  );
}
```

---

## 3. Directory Structure (App Router v3.0)

```
apps/web/src/
├── app/
│   ├── layout.tsx                    # Root: fonts, Providers wrapper
│   ├── globals.css                   # Tailwind v4 @theme + Shadcn vars
│   ├── not-found.tsx                 # 404
│   ├── error.tsx                     # Root error boundary
│   │
│   ├── (auth)/                       # Public auth routes (centered card layout)
│   │   ├── layout.tsx
│   │   ├── login/page.tsx
│   │   ├── register/page.tsx
│   │   └── forgot-password/page.tsx
│   │
│   ├── (onboarding)/                 # 4-step onboarding (stepper layout)
│   │   ├── layout.tsx
│   │   ├── welcome/page.tsx          # Role selection
│   │   ├── first-upload/page.tsx     # Upload or sample project
│   │   ├── processing/page.tsx       # SSE streaming analysis view
│   │   └── guided-review/page.tsx    # First alert walkthrough
│   │
│   ├── (dashboard)/                  # Protected app (sidebar + header)
│   │   ├── layout.tsx                # AppSidebar + Header + DemoBanner
│   │   ├── page.tsx                  # Redirect → projects
│   │   ├── projects/
│   │   │   ├── page.tsx              # Project list (Server Component)
│   │   │   └── [projectId]/
│   │   │       ├── layout.tsx        # Project tabs
│   │   │       ├── coherence/page.tsx    # PPR: Gauge + Breakdown
│   │   │       ├── evidence/
│   │   │       │   ├── page.tsx          # Evidence list
│   │   │       │   └── [clauseId]/page.tsx  # PDF + highlights
│   │   │       ├── alerts/page.tsx       # Alert Review Center
│   │   │       ├── stakeholders/page.tsx # Map + RACI
│   │   │       ├── documents/page.tsx    # Upload + status
│   │   │       ├── procurement/page.tsx  # WBS + BOM
│   │   │       └── settings/page.tsx     # Project weights
│   │   └── settings/page.tsx         # User account settings
│   │
│   └── (admin)/                      # Internal admin (Tremor-enhanced)
│       ├── layout.tsx                # Admin sidebar, role-gated
│       ├── tenants/page.tsx          # Tenant management
│       ├── users/page.tsx            # Global users
│       ├── ai-costs/page.tsx         # AI cost monitoring
│       ├── audit/page.tsx            # Audit trail
│       └── system/page.tsx           # Feature flags, health
│
├── components/
│   ├── ui/                           # Shadcn/ui primitives
│   ├── features/
│   │   ├── coherence/                # CoherenceGauge, ScoreCard, WeightAdjuster
│   │   ├── evidence/                 # EvidenceViewer, PDFRenderer, Watermark
│   │   ├── alerts/                   # AlertReviewCenter, ApprovalModal, SeverityBadge
│   │   ├── documents/                # DocumentUpload, ProcessingStepper
│   │   ├── stakeholders/             # StakeholderMap, RACIMatrix
│   │   ├── projects/                 # ProjectList, ProjectCard
│   │   └── admin/                    # TenantOverview, AICostDashboard
│   └── layout/                       # AppSidebar, Header, DemoBanner, MobileBottomNav
│
├── lib/
│   ├── api/
│   │   ├── client.ts                 # Axios instance (Orval mutator)
│   │   └── generated/                # ⚠️ AUTO-GENERATED by Orval
│   ├── utils.ts
│   └── constants.ts
│
├── stores/                           # Zustand (client-only)
│   ├── auth.ts, app-mode.ts, sidebar.ts, filters.ts, onboarding.ts
│
├── hooks/                            # Cross-cutting hooks
│   ├── useCountUp.ts, useMediaQuery.ts, useEventSource.ts
│
├── mocks/                            # MSW (demo mode)
│   ├── browser.ts, node.ts
│   ├── handlers/
│   │   ├── generated/                # ⚠️ AUTO-GENERATED by Orval
│   │   └── custom/                   # SSE stream, @mswjs/data seed
│   └── db.ts                         # @mswjs/data entity models
│
├── config/env.ts
└── instrumentation.ts                # Next.js 15 server startup hook
```

**Key decisions:** Route groups `(auth)`, `(dashboard)`, `(admin)`, `(onboarding)` provide distinct layouts without URL segments. `generated/` directories are gitignored (CI regenerates). Server Components are default in `page.tsx`; Client Components only where interactivity is needed (charts, forms, PDF viewer).

---

## 4. Expert Engineering Decisions (12 Leads)

### 4.1 Frontend Architect — Next.js 15 Migration & PPR

**Migration steps:** (1) Bump `next` to 15.3, `react` to 19.1 via `npx @next/codemod@latest upgrade`. (2) Fix async Request APIs: `cookies()`, `headers()`, `params`, `searchParams` are now `async`. (3) Caching: Next.js 15 no longer auto-caches `fetch()` — explicit `cache: 'force-cache'` needed for static data (correct for C2Pro's dynamic data). (4) Turbopack is default in dev.

**PPR on dashboard pages:**

```typescript
// next.config.ts
const nextConfig = {
  experimental: {
    ppr: 'incremental',
    reactCompiler: true,
    optimizePackageImports: ['lucide-react', 'recharts', 'date-fns', 'motion'],
    instrumentationHook: true,
  },
};
```

```tsx
// src/app/(dashboard)/projects/[projectId]/coherence/page.tsx
export const experimental_ppr = true;  // PPR enabled per-route

export default async function CoherencePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Coherence Dashboard</h1>
      {/* Static shell renders instantly. Dynamic holes stream via Suspense. */}
      <Suspense fallback={<GaugeSkeleton />}>
        <CoherenceGaugeServer projectId={projectId} />
      </Suspense>
    </div>
  );
}
```

### 4.2 Performance Engineer — PDF Lazy Loading

```tsx
// PDF viewer is ~600KB — NEVER import at module scope
const PDFViewerCore = dynamic(
  () => import('@react-pdf-viewer/core').then((mod) => mod.Viewer),
  { ssr: false, loading: () => <Skeleton className="h-[600px] w-full" /> }
);
```

| Route | Bundle Budget (gzipped) | Strategy |
|-------|------------------------|----------|
| Shared JS | ≤ 90 KB | Tree-shake, React Compiler |
| Dashboard | ≤ 50 KB | Recharts lazy, SSR gauge |
| Evidence Viewer | ≤ 120 KB | PDF viewer dynamic import |
| Admin | ≤ 80 KB | Tremor lazy |

### 4.3 Security Engineer — Dynamic PDF Watermarks

Canvas overlay rendering semi-transparent diagonal text (user email + timestamp). `pointer-events: none` and `print:hidden` via CSS. No JS needed by the viewer — the watermark sits as a sibling element.

### 4.4 AI UX Engineer — SSE Streaming for Document Processing

```typescript
// src/hooks/useEventSource.ts — production mode uses EventSource API
// Demo mode simulates with setTimeout chain: 8-second deterministic sequence
// Steps: "Extracting text..." → "Cross-referencing..." → "Calculating Score..."
// Partial results stream as each document pair completes
```

### 4.5 Mobile/Responsive Engineer — @container Queries

```tsx
// Tailwind v4 native @container support
<div className="@container">
  <div className="@max-md:hidden">{/* Table view ≥768px */}</div>
  <div className="@md:hidden space-y-3">{/* Card view <768px */}</div>
</div>
```

### 4.6 A11y Developer — Accessible Charts

Every chart wrapped in `<figure>` with `<figcaption>`. Toggle between chart and accessible data table. Recharts `accessibilityLayer` prop for keyboard navigation. Triple-encoded severity: color + shape (▲◆●) + text. WCAG 2.5.7: all drag interactions have button alternatives. WCAG 2.5.8: all targets ≥24×24px (48×48 for field use).

### 4.7 Backend/DevOps Liaison — Frontend Telemetry

`navigator.sendBeacon()` for fire-and-forget AI usage reporting. OpenTelemetry `trace_id` correlates frontend→backend traces. Sentry captures errors with `trace_id` context.

---

## 5. Sprint Plan (4 × 2-Week Sprints)

### Sprint 1: Infrastructure & Design System (Weeks 1–2)

**Goal:** `pnpm dev:demo` shows styled app shell with mock data.

| ID | Task | Days | Deliverable |
|----|------|------|-------------|
| S1-01 | Next.js 15.3 project init + Turbopack | 1 | `apps/web/` boots in <2s |
| S1-02 | Tailwind v4 CSS-first config | 2 | All v3.0 color/type/spacing tokens |
| S1-03 | Shadcn/ui init + 15 base components | 1 | Button, Card, Badge, Dialog, Sheet, Sidebar, etc. |
| S1-04 | App shell (sidebar + header + breadcrumbs) | 3 | Responsive: full/collapsed/bottom-nav |
| S1-05 | Zustand stores (auth, app-mode, sidebar, filters) | 1 | 4 stores with DevTools |
| S1-06 | MSW v2 setup (browser + node + instrumentation) | 1 | Demo mode serves mock responses |
| S1-07 | Orval config + first codegen | 2 | TanStack hooks + MSW handlers generated |
| S1-08 | Auth flow (Clerk) | 2 | Login/register/forgot-password |
| S1-09 | CI pipeline | 1 | Typecheck + lint + test on PR |
| S1-10 | Storybook + 5 stories | 1 | Visual development environment |
| S1-11 | Demo banner + dark mode | 1 | Mode indicator + theme toggle |

**Acceptance:** Login → empty dashboard with sidebar/header/demo banner. All v3.0 tokens active. CI passes.

### Sprint 2: Dual-Mode Pipeline & Core Data (Weeks 3–4)

**Goal:** Project list and Coherence Dashboard render with real/mock data.

| ID | Task | Days | Deliverable |
|----|------|------|-------------|
| S2-01 | @mswjs/data seed models (8 entities) | 2 | Deterministic demo dataset (faker seed=42) |
| S2-02 | Custom MSW handlers (SSE streaming) | 2 | 8-second simulated processing flow |
| S2-03 | Orval CI check integration | 1 | `orval --check` blocks merge |
| S2-04 | Project list page (Server Component) | 2 | Tenant-filtered list with score badges |
| S2-05 | Project detail layout (tabs) | 1 | 7-tab navigation |
| S2-06 | Coherence Dashboard (gauge + breakdown) | 3 | Count-up donut + 6 ScoreCards |
| S2-07 | Weight adjuster (sliders, sum=100%) | 2 | PUT mutation via Orval |
| S2-08 | Document upload (drag-drop) | 2 | PDF/XLSX/BC3, max 50MB, chunked |
| S2-09 | Processing stepper (SSE consumer) | 2 | Multi-stage animated progress |
| S2-10 | Contract validation (Ajv) | 1 | MSW responses match OpenAPI schema |
| S2-11 | Chromatic integration | 1 | Visual snapshots in CI |

**Acceptance:** Navigate → project → Coherence Score (animated) → adjust weights → upload → stepper. Works in both modes.

### Sprint 3: Core Views & Evidence Viewer (Weeks 5–6)

**Goal:** All P0 views functional: Evidence Viewer, Alerts, Stakeholders.

| ID | Task | Days | Deliverable |
|----|------|------|-------------|
| S3-01 | PDF renderer (lazy loaded) | 3 | Bundle ≤120KB gzipped |
| S3-02 | Clause highlighting (overlay) | 2 | Click-through to alert |
| S3-03 | Alert sidebar (split pane) | 2 | Resizable panels |
| S3-04 | Dynamic watermark (Canvas) | 1 | Print-hidden, user-specific |
| S3-05 | Alert Review Center (table + filters) | 2 | Sortable, filterable |
| S3-06 | Approve/reject modal (Gate 6) | 2 | Justification required for critical |
| S3-07 | Severity badge (triple-encoded) | 1 | Color + shape + text, 4.5:1 contrast |
| S3-08 | Stakeholder Map (scatter quadrants) | 2 | Recharts ScatterChart |
| S3-09 | RACI Matrix (editable grid) | 3 | Inline R/A/C/I dropdowns |
| S3-10 | Legal Disclaimer modal (Gate 8) | 1 | Blocks access until accepted |
| S3-11 | A11y audit pass 1 | 2 | Zero critical axe violations |
| S3-12 | Responsive pass (tablet) | 2 | @container card fallback |

**Acceptance:** Full flow: Dashboard → Evidence → PDF highlighting → alert approve → Stakeholder Map → RACI. axe-core clean. Tablet responsive.

### Sprint 4: Admin Portal, Polish & Production (Weeks 7–8)

**Goal:** Admin portal, performance targets, WCAG 2.2 AA, production readiness.

| ID | Task | Days | Deliverable |
|----|------|------|-------------|
| S4-01 | Admin layout + Tremor | 2 | Admin shell, role-gated |
| S4-02 | Tenant management | 2 | Card grid with status/tier/sparklines |
| S4-03 | AI cost monitoring dashboard | 3 | Token usage, cost/tenant, model breakdown, budget gauge |
| S4-04 | Audit trail viewer | 2 | Filterable timeline, CSV export |
| S4-05 | User management | 1 | Sortable table, bulk ops |
| S4-06 | Onboarding flow (4 steps) | 3 | Welcome→Upload→Processing→Review |
| S4-07 | Error boundaries + fallbacks | 1 | Graceful degradation |
| S4-08 | Loading skeletons (all pages) | 1 | No layout shift |
| S4-09 | Performance optimization | 2 | Lighthouse ≥90 |
| S4-10 | WCAG 2.2 full audit | 2 | All criteria pass, NVDA/VoiceOver manual test |
| S4-11 | E2E test suite (Playwright) | 3 | 15+ specs, dual-mode matrix |
| S4-12 | OpenTelemetry + Sentry | 1 | Frontend traces correlate with backend |
| S4-13 | Production deploy checklist | 1 | Env vars, CSP, security headers |

**Acceptance:** All flows E2E. Admin portal functional. Lighthouse ≥90. WCAG 2.2 AA verified. Playwright green. Deploy-ready.

---

## 6. Technical Risks & Mitigation

### 6.1 High Risk

| ID | Risk | P | I | Mitigation |
|----|------|---|---|------------|
| R1 | **Tailwind v4 instability** — CSS-first engine is new | High | High | Pin ≥4.1. Keep `tailwind.config.ts` as escape hatch via `@config`. Visual regression on every CSS change. +2 days buffer in Sprint 1. |
| R2 | **React Compiler breaks 3rd-party libs** — Recharts/dnd-kit memo assumptions | Med | High | Add `"use no memo"` per-component opt-out. Test all chart/pdf components. Disable per-file via `reactCompilerOptions.sources`. |
| R3 | **Orval codegen drift** — Backend changes spec without notice | High | Med | `orval --check` in CI. Webhook triggers codegen. Weekly sync meeting. |
| R4 | **PPR hydration mismatches** | Med | Med | Enable per-route (`experimental_ppr = true`) only on dashboards. E2E testing. Disable flag as fallback. |
| R5 | **PDF viewer bundle size** (600KB) | Med | High | `next/dynamic` with `ssr: false`. Separate chunk. Never module-scope import. |
| R6 | **MSW + Server Components** — browser worker can't intercept server fetch | High | High | `instrumentation.ts` hook for server-side MSW. Test both paths in CI. |

### 6.2 Contingency Table

| Trigger | Fallback | Time Impact |
|---------|----------|-------------|
| Tailwind v4 blocker | Fall back to v3.4 (tokens still work via CSS vars) | +0 days |
| React Compiler breaks Recharts | `"use no memo"` on chart components | +0.5 days |
| PPR hydration errors | Disable `ppr` flag — full SSR fallback | +0 days |
| Orval can't generate MSW handlers | Manual MSW handlers from Zod schemas | +3 days |
| PDF viewer exceeds budget | Switch to `react-pdf` with custom highlight | +2 days |

---

## 7. Appendices

### 7.1 `next.config.ts`

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
        { key: 'X-Frame-Options', value: 'DENY' },
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      ],
    }];
  },
};

export default withSentryConfig(nextConfig, {
  org: 'c2pro', project: 'web', silent: true, hideSourceMaps: true,
});
```

### 7.2 `postcss.config.js` (Tailwind v4)

```javascript
export default { plugins: { '@tailwindcss/postcss': {} } };
```

### 7.3 State Boundary Rules

```
ZUSTAND (Client State)              TANSTACK QUERY (Server State)
─────────────────────               ──────────────────────────────
✅ Auth token + tenant ID           ✅ All API GET responses
✅ Sidebar state                    ✅ Mutation results
✅ Theme preference                 ✅ Polling data (doc status)
✅ Filter selections                ✅ Cached computations
✅ App mode (demo/production)       
                                    
❌ NEVER: API response data         ❌ NEVER: UI preferences
❌ NEVER: Server-computed values    ❌ NEVER: Auth tokens
```

---

## Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| VP Engineering | _________________ | 2026-02-08 | ☐ |
| Frontend Architect | _________________ | __________ | ☐ |
| QA Lead | _________________ | __________ | ☐ |
| Security Lead | _________________ | __________ | ☐ |
| Product Owner | _________________ | __________ | ☐ |

---

**Document:** C2Pro Technical Design Document v3.0  
**Classification:** INTERNAL — Engineering Team  
**Next Review:** After Sprint 2 completion (Week 4)
