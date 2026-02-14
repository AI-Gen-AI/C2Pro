# C2Pro Frontend Master Plan v1.0

> **Document:** Unified Frontend Architecture & Implementation Plan  
> **Version:** 1.0 — Implementation-Ready  
> **Date:** 2026-02-10  
> **Supersedes:** TDD v3.0 frontend sections, FRONTEND_TESTING_PLAN.md  
> **Supersedes:** TDD v3.0 frontend sections, C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_0
> **Source:** Phase 1 (12 Expert Agents) → Phase 2 (6 Cross-Reviewers, 31 Flags) → Phase 3 (10 Verifiers)  
> **Stack:** Next.js 15.3 · React 19.1 · TypeScript 5.7 · Tailwind 4.1 · Zustand 5 · TanStack Query 5 · Orval 7 · Clerk · Vitest · Playwright

---

## 1. Architecture Decisions Record

### 1.1 Corrected Architecture (Post-Verification)

This document is the baseline. This section documents every deviation from previous plans based on Phase 1–3 analysis.

**ADR-001: Auth Architecture — Clerk-Synchronized Zustand Cache**

The TDD defines `stores/auth.ts` as an independent Zustand store AND uses Clerk for auth. Phase 3 confirmed this dual source creates token desynchronization bugs (FLAG-1, 10/10 verifiers).

```
BEFORE (TDD v3.0):                    AFTER (Master Plan):
┌──────────┐   ┌──────────┐          ┌──────────┐   ┌──────────┐
│  Clerk   │   │ Zustand  │          │  Clerk   │──▶│ Zustand  │
│ (tokens) │   │ (tokens) │          │  (sole   │   │ (sync    │
│          │   │          │          │  source) │   │  cache)  │
└────┬─────┘   └────┬─────┘          └──────────┘   └────┬─────┘
     │              │                                     │
     ▼              ▼                                     ▼
   Middleware    Axios interceptor                  Axios interceptor
   (race condition possible)                       (reads .getState())
```

Implementation:

```typescript
// src/components/providers/AuthSync.tsx
'use client';

import { useAuth, useOrganization } from '@clerk/nextjs';
import { useEffect } from 'react';
import { useAuthStore } from '@/stores/auth';
import { useQueryClient } from '@tanstack/react-query';

export function AuthSync({ children }: { children: React.ReactNode }) {
  const { getToken, isSignedIn } = useAuth();
  const { organization } = useOrganization();
  const queryClient = useQueryClient();
  const setAuth = useAuthStore((s) => s.setAuth);
  const prevOrgId = useAuthStore((s) => s.tenantId);

  // Sync Clerk token → Zustand on every render cycle
  useEffect(() => {
    if (!isSignedIn) return;
    const sync = async () => {
      const token = await getToken();
      const tenantId = organization?.id ?? null;
      setAuth({ token, tenantId });
    };
    sync();
    // Re-sync every 50 seconds (Clerk tokens expire at 60s)
    const interval = setInterval(sync, 50_000);
    return () => clearInterval(interval);
  }, [isSignedIn, organization?.id, getToken, setAuth]);

  // FLAG-4: Clear ALL cache on organization switch
  useEffect(() => {
    if (prevOrgId && organization?.id && prevOrgId !== organization.id) {
      queryClient.clear();
    }
  }, [organization?.id, prevOrgId, queryClient]);

  return <>{children}</>;
}
```

```typescript
// src/stores/auth.ts — REFACTORED: Write-only from AuthSync
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

interface AuthState {
  token: string | null;
  tenantId: string | null;
  setAuth: (auth: { token: string | null; tenantId: string | null }) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>()(
  devtools((set) => ({
    token: null,
    tenantId: null,
    setAuth: ({ token, tenantId }) => set({ token, tenantId }),
    clear: () => set({ token: null, tenantId: null }),
  }), { name: 'c2pro-auth' })
);
// ⛔ RULE: Only AuthSync.tsx may call setAuth(). No other file.
```

```typescript
// src/lib/api/client.ts — CORRECTED: No require(), no useAuth()
import Axios, { type AxiosRequestConfig } from 'axios';
import { env } from '@/config/env';
import { useAuthStore } from '@/stores/auth'; // Direct import (no circular dep)

const axiosInstance = Axios.create({
  baseURL: env.API_BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

axiosInstance.interceptors.request.use((config) => {
  // Synchronous read from Zustand — always has latest Clerk token
  const { token, tenantId } = useAuthStore.getState();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  if (tenantId) config.headers['X-Tenant-ID'] = tenantId;
  return config;
});

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

    if (error.response?.status === 401) {
      useAuthStore.getState().clear();
      if (typeof window !== 'undefined') window.location.href = '/login';
    }

    if (error.response?.status === 429) {
      // Let TanStack Query handle retry — just surface to UI
      console.warn('[C2Pro] Rate limited');
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

**ADR-002: Layer Rules — Server Component Exception**

```
RULE (amended from Agent 4):

Server Components:
  ✅ MAY fetch data directly via lib/api/generated/ functions
  ✅ MAY call lib/api/client.ts server utilities
  ❌ MUST NOT use hooks (useQuery, useState, useEffect)

Client Components:
  ✅ MUST use Orval-generated TanStack Query hooks for server data
  ✅ MAY use Zustand stores for client state
  ❌ MUST NOT import from lib/api/generated/ directly (use hooks)
```

**ADR-003: Query Keys — Orval-Generated Only**

```
❌ DELETED — Do not create this:
const queryKeys = {
  projects: { all: ['projects'] as const, ... },
  coherence: { dashboard: (id) => ['coherence', 'dashboard', id] },
};

✅ USE — Orval-generated key factories:
import { getGetCoherenceDashboardQueryKey } from '@/lib/api/generated/coherence';
import { getGetAlertsByCategoryQueryKey } from '@/lib/api/generated/alerts';

// For broad invalidation:
queryClient.invalidateQueries({ queryKey: ['coherence'] }); // Matches all Orval coherence keys
```

**ADR-004: SSE Authentication via Cookies**

Standard `EventSource` API cannot send custom headers. Solution:

```typescript
// src/hooks/useDocumentProcessing.ts
export function useDocumentProcessing(projectId: string) {
  const [stages, setStages] = useState<ProcessingStage[]>([]);
  const queryClient = useQueryClient();
  const updateProcessing = useProcessingStore((s) => s.update);

  useEffect(() => {
    // withCredentials sends Clerk's __clerk_db_jwt cookie
    const source = new EventSource(
      `${env.API_BASE_URL}/api/v1/projects/${projectId}/process/stream`,
      { withCredentials: true }
    );

    source.addEventListener('stage', (e) => {
      const stage = JSON.parse(e.data);
      setStages(prev => [...prev, stage]);
      // FLAG-22: Persist to Zustand for cross-page visibility
      updateProcessing(projectId, stage);
    });

    source.addEventListener('complete', async (e) => {
      const result = JSON.parse(e.data);
      // FLAG-25: Await refetch BEFORE navigation
      await queryClient.refetchQueries({
        queryKey: ['coherence'],
        predicate: (q) => q.queryKey.includes(projectId),
      });
      await queryClient.invalidateQueries({ queryKey: ['alerts'] });
      source.close();
      updateProcessing(projectId, { complete: true, score: result.global_score });
    });

    source.addEventListener('error', () => {
      // Safari reconnection quirk: EventSource auto-reconnects
      // but Safari may drop after ~60s. Manual fallback:
      setTimeout(() => {
        if (source.readyState === EventSource.CLOSED) {
          // Fallback to polling
          updateProcessing(projectId, { fallbackToPolling: true });
        }
      }, 5000);
    });

    return () => source.close();
  }, [projectId, queryClient, updateProcessing]);

  return { stages };
}
```

**Backend requirement:** FastAPI SSE endpoint must validate Clerk's `__clerk_db_jwt` session cookie in addition to Bearer tokens. If this is not feasible, fall back to `fetch()` + `ReadableStream`:

```typescript
// FALLBACK: fetch-based SSE with Bearer token
const response = await fetch(url, {
  headers: { Authorization: `Bearer ${useAuthStore.getState().token}` },
});
const reader = response.body!.getReader();
const decoder = new TextDecoder();
// Parse SSE format manually from chunks
```

---

### 1.2 Technology Stack — Final Validated Decisions

| Technology | Version | Verdict | Notes |
|-----------|---------|---------|-------|
| Next.js | 15.3 | ✅ Keep | PPR incremental, Turbopack, React Compiler |
| React | 19.1 | ✅ Keep | Server Components, use() hook |
| TypeScript | 5.7 | ✅ Keep | Strict mode enabled |
| Tailwind CSS | 4.1 | ⚠️ Keep + fallback | Pin ≥4.1, keep CSS var approach for v3.4 rollback |
| Zustand | 5 | ✅ Keep | 4 stores: auth (refactored), app-mode, sidebar, filters + 2 new: onboarding, processing |
| TanStack Query | 5 | ✅ Keep | Orval-generated hooks exclusively |
| Orval | 7 | ✅ Keep | `orval --check` in CI, never commit generated files |
| Clerk | ^6.12 | ✅ Keep | Sole auth source, AuthSync pattern |
| Recharts | 2.15 | ⚠️ Keep for complex charts | Custom SVG for hero gauge (see §3.3) |
| Vitest | 3.2 | ✅ Keep | jsdom, v8 coverage |
| Playwright | 1.50 | ✅ Keep | Dual-mode E2E |
| MSW | 2.7 | ✅ Keep | Demo mode + test mode |
| Sentry | Latest | ✅ Keep | Error tracking Sprint 1, Replay Sprint 3 (post-consent) |
| Storybook | Latest | ⚠️ Deferred | Sprint 2 for `ui/` only, not feature components |
| Chromatic | Latest | ⚠️ Sprint 3 | After design stabilizes |
| @fontsource | — | ❌ Replace | Switch to `next/font/local` (FLAG-10) |
| Tremor | 3.x | ⚠️ Sprint 4 | Lazy-load, admin only |

---

## 2. Design System — Corrected Tokens

### 2.1 Color System Fix (FLAG-8)

Computed contrast ratios (verified programmatically):

| Color | Hex | On White | On #162A38 | Usage |
|-------|-----|----------|------------|-------|
| `--primary` | `#00ACC1` | **2.74:1 ❌** | — | Backgrounds, decorative, large text ≥18px only |
| `--primary-text` | `#00838F` | **4.52:1 ✅ AA** | — | **All text on light backgrounds** |
| `--primary` (dark) | `#4DD0E1` | — | **8.03:1 ✅ AAA** | Text on dark backgrounds |

Updated `globals.css`:

```css
@layer base {
  :root {
    --primary: oklch(0.56 0.12 195);           /* #00ACC1 — bg, decorative, large text */
    --primary-foreground: oklch(1 0 0);         /* white on primary bg */
    --primary-text: oklch(0.42 0.10 195);       /* #00838F — ALL text on light bg */

    /* ... rest unchanged from TDD ... */
  }
}
```

**Migration rule:** Audit all `text-primary` Tailwind classes. Replace with custom `text-primary-text` utility:

```css
@layer utilities {
  .text-primary-text {
    color: var(--primary-text);
  }
}
```

ESLint rule to flag `text-primary` usage on light backgrounds (Sprint 2).

### 2.2 Font Loading Fix (FLAG-10)

Remove from `globals.css`:
```css
/* ❌ DELETE these lines */
@import "@fontsource-variable/inter";
@import "@fontsource/jetbrains-mono";
```

Replace in `layout.tsx`:
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
  preload: false, // Only used in code blocks — lazy load
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
```

**Impact:** ~140KB → ~40KB font payload. `font-display: swap` prevents invisible text. Latin subset automatic.

### 2.3 Severity Encoding (Unchanged — Validated)

Triple encoding confirmed accessible by 9/10 verifiers:

```
● Good     — green circle + "Good" text     — 4.55:1 contrast ✅
◆ Warning  — amber diamond + "Warning" text — 6.67:1 contrast ✅
▲ Critical — red triangle + "Critical" text — 5.89:1 contrast ✅
```

---

## 3. State Management — Corrected Architecture

### 3.1 Store Inventory (6 Stores Total)

| Store | Purpose | Persistence | Sprint |
|-------|---------|-------------|--------|
| `useAuthStore` | Clerk token cache (read-only except AuthSync) | None | 1 |
| `useAppModeStore` | Demo/production toggle | None (env-derived) | 1 |
| `useSidebarStore` | Sidebar state + width | `localStorage` | 1 |
| `useFilterStore` | Alert severity/category/search filters | `sessionStorage` (FLAG-30) | 1 (no persist), 3 (add persist) |
| `useOnboardingStore` | 4-step onboarding progress | `localStorage` | 2 |
| `useProcessingStore` | SSE processing state per project (FLAG-22) | None (transient) | 2 |

```typescript
// src/stores/processing.ts — NEW (FLAG-22)
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

interface ProcessingState {
  activeJobs: Record<string, {
    stages: ProcessingStage[];
    progress: number;
    complete: boolean;
    score?: number;
    fallbackToPolling: boolean;
  }>;
  update: (projectId: string, data: Partial<ProcessingState['activeJobs'][string]> | { stage: ProcessingStage }) => void;
  clear: (projectId: string) => void;
}

export const useProcessingStore = create<ProcessingState>()(
  devtools((set) => ({
    activeJobs: {},
    update: (projectId, data) => set((state) => ({
      activeJobs: {
        ...state.activeJobs,
        [projectId]: {
          ...state.activeJobs[projectId],
          ...(('stage' in data) ? {
            stages: [...(state.activeJobs[projectId]?.stages ?? []), data.stage],
            progress: data.stage.progress,
          } : data),
        },
      },
    })),
    clear: (projectId) => set((state) => {
      const { [projectId]: _, ...rest } = state.activeJobs;
      return { activeJobs: rest };
    }),
  }), { name: 'c2pro-processing' })
);
```

### 3.2 State Boundary Enforcement

```
ZUSTAND (Client State)              TANSTACK QUERY (Server State)
─────────────────────               ──────────────────────────────
✅ Clerk token cache (read-only)    ✅ All API GET responses
✅ Sidebar state                    ✅ Mutation results + onSettled invalidation
✅ Theme preference                 ✅ Polling data (document processing status)
✅ Filter selections                ✅ Cached computations
✅ App mode (demo/production)
✅ Processing stage display
✅ Onboarding step

❌ NEVER: Raw API response data     ❌ NEVER: UI preferences
❌ NEVER: Server-computed values    ❌ NEVER: Auth tokens
❌ NEVER: Written by anything       ❌ NEVER: Transient display state
   except its designated writer
```

ESLint custom rule (`eslint-plugin-c2pro`):
```javascript
// Flag: Zustand store receiving TanStack Query data
// Pattern: useXxxStore(s => s.set(useQueryResult.data))
// Flag: Manual queryKeys that don't match Orval pattern
```

### 3.3 TanStack Query Configuration

```typescript
// src/lib/query-client.ts
import { QueryClient } from '@tanstack/react-query';

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,           // 1 minute
        gcTime: 5 * 60_000,          // 5 minutes
        retry: 2,
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10_000),
        refetchOnWindowFocus: false,  // Opt-in per query (FLAG-23)
        refetchOnReconnect: true,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}
```

**Coherence dashboard override** (solves FLAG-25 staleTime race):
```typescript
// In Orval override config or wrapper hook:
useGetCoherenceDashboard(projectId, {
  staleTime: 30_000,           // Shorter for the most important view
  refetchOnMount: 'always',    // Always fresh on navigation
  refetchOnWindowFocus: true,  // Cross-tab freshness (FLAG-23)
});
```

---

## 4. Performance Budget — Corrected

### 4.1 Bundle Budgets (Gzipped)

| Route | Budget | Strategy | Change from TDD |
|-------|--------|----------|----------------|
| Shared JS (framework) | ≤ 90 KB | React Compiler tree-shaking | Unchanged |
| Dashboard (coherence) | ≤ **80 KB** | Custom SVG gauge + ScoreCards | ↑ from 50KB (FLAG-9) |
| Evidence Viewer | ≤ 120 KB | PDF viewer `next/dynamic ssr:false` | Unchanged |
| Alert Review | ≤ 60 KB | Server Component + client table | New |
| Admin | ≤ 100 KB | Tremor lazy, admin-only chunk | ↑ from 80KB (FLAG-24) |
| Fonts | ≤ **40 KB** | `next/font/local` latin subset | ↓ from ~140KB (FLAG-10) |

### 4.2 Hero Gauge — Custom SVG (FLAG-9 Resolution)

The CoherenceGauge is the hero metric. Recharts `RadialBarChart` adds ~50-65KB gzipped. A custom SVG radial gauge costs ~2KB:

```tsx
// src/components/features/coherence/CoherenceGauge.tsx
'use client';

import { cn } from '@/lib/utils';

interface CoherenceGaugeProps {
  score: number;       // 0-100
  label?: string;
  size?: number;       // px, default 200
  strokeWidth?: number; // px, default 12
}

export function CoherenceGauge({ score, label = 'Coherence Score', size = 200, strokeWidth = 12 }: CoherenceGaugeProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = ((100 - score) / 100) * circumference;
  const color = score >= 80 ? 'var(--success)' : score >= 60 ? 'var(--warning)' : 'var(--error)';

  return (
    <figure className="flex flex-col items-center gap-2">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={`${label}: ${score} out of 100`}
      >
        {/* Background track */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="var(--muted)" strokeWidth={strokeWidth}
        />
        {/* Score arc */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={progress}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          className="transition-[stroke-dashoffset] duration-[1500ms] ease-[cubic-bezier(0.16,1,0.3,1)]"
        />
        {/* Score text */}
        <text
          x="50%" y="50%"
          textAnchor="middle" dominantBaseline="central"
          className="fill-foreground font-mono text-4xl font-bold tabular-nums"
        >
          {score}
        </text>
      </svg>
      <figcaption className="text-sm text-muted-foreground">{label}</figcaption>
    </figure>
  );
}
```

**Recharts is KEPT** for complex charts (StakeholderMap scatter, admin dashboards) where it's lazy-loaded:
```typescript
const StakeholderChart = dynamic(
  () => import('./StakeholderScatter').then(m => m.StakeholderScatter),
  { ssr: false, loading: () => <Skeleton className="h-[400px]" /> }
);
```

### 4.3 Lighthouse Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| LCP | ≤ 2.5s | Coherence dashboard with 6 ScoreCards |
| INP | ≤ 200ms | Weight slider drag interaction |
| CLS | ≤ 0.1 | Page with skeleton → content swap |
| FCP | ≤ 1.8s | First paint after login redirect |
| TTFB | ≤ 800ms | PPR static shell delivery |
| TBT | ≤ 200ms | Main thread during hydration |

**CI enforcement** (Sprint 2):
```bash
# .github/workflows/ci.yml
- name: Bundle analysis
  run: |
    pnpm build
    npx @next/bundle-analyzer --json > bundle-stats.json
    node scripts/check-budgets.js bundle-stats.json
```

---

## 5. Security — Hardened Configuration

### 5.1 CSP Headers (Corrected for Sentry — FLAG-15b)

```typescript
// next.config.ts — headers()
headers: [{
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
        "worker-src blob: 'self'",          // FLAG-15b: Required for Sentry Replay
        "frame-ancestors 'none'",
        "base-uri 'self'",
      ].join('; '),
    },
    { key: 'X-Frame-Options', value: 'DENY' },
    { key: 'X-Content-Type-Options', value: 'nosniff' },
    { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
    { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
  ],
}],
```

### 5.2 RBAC — Frontend Gates (UX Only, Server-Enforced)

```typescript
// src/lib/auth/permissions.ts — Unchanged from Agent 3
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
  const role = useAuthStore((s) => s.role); // Synced from Clerk org metadata
  if (!ROLE_PERMISSIONS[role]?.includes(permission)) return <>{fallback}</>;
  return <>{children}</>;
}
// ⚠️ UX convenience only. ALL authorization enforced server-side.
```

### 5.3 PDF Watermark (FLAG-31 — Pseudonymized)

```tsx
// Use hashed short ID instead of raw email
const watermarkText = `${user.publicMetadata.shortId} · ${format(new Date(), 'yyyy-MM-dd HH:mm')}`;
// Maps to real email only in backend audit logs
```

### 5.4 GDPR Consent (FLAG-14)

```typescript
// src/components/layout/CookieConsent.tsx — Sprint 3
'use client';

import { useState, useEffect } from 'react';

type ConsentLevel = 'essential' | 'analytics';

export function CookieConsent() {
  const [consent, setConsent] = useState<ConsentLevel[]>(['essential']);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem('c2pro-consent');
    if (!stored) { setVisible(true); return; }
    const parsed = JSON.parse(stored) as ConsentLevel[];
    setConsent(parsed);
    if (parsed.includes('analytics')) initSentryReplay();
  }, []);

  const accept = (levels: ConsentLevel[]) => {
    localStorage.setItem('c2pro-consent', JSON.stringify(levels));
    setConsent(levels);
    setVisible(false);
    if (levels.includes('analytics')) initSentryReplay();
  };

  if (!visible) return null;
  // Render bottom banner with Essential (always on) + Analytics (opt-in)
}

function initSentryReplay() {
  // Dynamically import and initialize Sentry Replay ONLY after consent
  import('@sentry/nextjs').then(Sentry => {
    Sentry.addIntegration(Sentry.replayIntegration());
  });
}
```

**Sprint 1:** Sentry error tracking only (legitimate interest, no consent needed).
**Sprint 3:** Cookie banner + Sentry Replay conditional on consent.

---

## 6. Accessibility — WCAG 2.2 AA Compliance

### 6.1 Keyboard Shortcuts (FLAG-7 — Corrected)

```typescript
// src/components/features/alerts/AlertReviewCenter.tsx
// Shortcuts are FOCUS-SCOPED (WCAG 2.1.4 "active only on focus" exception)

function AlertReviewCenter() {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!shortcutsEnabled) return; // User can disable in settings
    switch (e.key) {
      case 'j': selectNextAlert(); break;
      case 'k': selectPrevAlert(); break;
      case 'a': if (selectedAlert) openApproveModal(); break;
      case 'r': if (selectedAlert) openRejectModal(); break;
    }
  };

  return (
    <div
      role="region"
      aria-label="Alert Review Center"
      tabIndex={0}
      onKeyDown={handleKeyDown}      // Only fires when this container has focus
      className="focus:outline-none"  // Custom focus ring handled by parent
    >
      {/* ... */}
    </div>
  );
}
```

### 6.2 Charts — Always Provide Data Table Alternative

```tsx
// Every chart component wraps with AccessibleChart
function AccessibleChart({ data, label, children }: {
  data: Array<{ name: string; value: number }>;
  label: string;
  children: React.ReactNode;
}) {
  const [showTable, setShowTable] = useState(false);
  return (
    <figure>
      <div role="img" aria-label={label}>
        {showTable ? (
          <table>
            <caption className="sr-only">{label}</caption>
            <thead><tr><th>Category</th><th>Score</th></tr></thead>
            <tbody>
              {data.map(d => <tr key={d.name}><td>{d.name}</td><td>{d.value}</td></tr>)}
            </tbody>
          </table>
        ) : children}
      </div>
      <button
        onClick={() => setShowTable(s => !s)}
        className="mt-2 text-xs underline text-primary-text"
      >
        {showTable ? 'Show chart' : 'Show as table'}
      </button>
    </figure>
  );
}
```

### 6.3 Touch Targets

All interactive elements: minimum 24×24px (WCAG 2.5.8), target 44×44px for primary actions.
Dense data tables: 24×24px with 8px spacing between targets.

### 6.4 A11y Pipeline

| Tool | Sprint | Purpose |
|------|--------|---------|
| `eslint-plugin-jsx-a11y` | 1 | Static analysis on every commit |
| `@axe-core/playwright` | 3 | Automated E2E a11y testing |
| NVDA + VoiceOver manual | 4 | Screen reader verification |
| `@storybook/addon-a11y` | 4 | Component-level a11y dev |

---

## 7. Testing Strategy — Corrected

### 7.1 Test Infrastructure (Supersedes FRONTEND_TESTING_PLAN.md)

```typescript
// src/tests/test-utils.tsx — CORRECTED (FLAG-26: includes Clerk mock)
import { render, type RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'next-themes';
import { ClerkProvider } from '@clerk/nextjs';

// Mock Clerk for tests
jest.mock('@clerk/nextjs', () => ({
  ClerkProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({ isSignedIn: true, getToken: async () => 'test-token' }),
  useUser: () => ({ user: { id: 'test-user', emailAddresses: [{ emailAddress: 'test@c2pro.io' }] } }),
  useOrganization: () => ({ organization: { id: 'test-org' } }),
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

### 7.2 Test Locations (FLAG-27 — Resolved)

```
Convention:
  Unit tests      → co-located: ScoreCard.test.tsx next to ScoreCard.tsx
  Integration     → src/tests/integration/  (page-level with MSW)
  E2E             → e2e/  (Playwright, project root)
  Visual          → Chromatic (via Storybook stories)
```

### 7.3 Server Component Testing (FLAG-13 — Three-Layer Strategy)

```
Layer 1 — Unit (RTL):
  Test Client Components in isolation
  ✅ CoherenceGauge.test.tsx
  ✅ ScoreCard.test.tsx
  ❌ CoherencePage.test.tsx  (async Server Component — CANNOT render in jsdom)

Layer 2 — Integration (MSW):
  Test data flow via Orval hooks (not page components)
  ✅ useGetCoherenceDashboard.test.tsx (hook + MSW)
  ✅ useUpdateWeights.test.tsx (mutation + optimistic update)

Layer 3 — E2E (Playwright):
  Test full page rendering including Server Component orchestration
  ✅ coherence-dashboard.spec.ts (against running demo mode)
  ✅ evidence-viewer.spec.ts
```

### 7.4 SSE Testing (FLAG-12 — MSW Streaming Handler)

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
          await new Promise(r => setTimeout(r, 50)); // Fast in tests
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

### 7.5 Test Phasing (FLAG-28 — Realistic for Solo Developer)

| Sprint | Unit | Integration | E2E | Total | Cumulative |
|--------|------|-------------|-----|-------|------------|
| 1 | 30 | 5 | 2 | **37** | 37 |
| 2 | 35 | 12 | 4 | **51** | 88 |
| 3 | 40 | 15 | 6 | **61** | 149 |
| 4 | 27 | 10 | 6 | **43** | **192** |

**Sprint 1 priority tests:** Auth flow (5), app shell (5), project list (10), ScoreCard (5), Zustand stores (5), Orval codegen validation (2), E2E login + empty dashboard (2).

**Coverage thresholds:** Statements 80%, Branches 75%, Functions 80%, Lines 80%.
Generated code (`lib/api/generated/`) and mocks (`mocks/`) excluded from coverage.

---

## 8. UX Patterns — Corrected

### 8.1 Mobile Evidence Viewer (FLAG-18)

```
Desktop (≥1280px):  Split pane (react-resizable-panels)
                    [PDF Viewer  |  Alert Sidebar]

Tablet (768-1279px): Stacked with toggle
                    [PDF Viewer (70vh)]
                    [Alert Sidebar (30vh, expandable)]

Mobile (≤767px):    Tab interface
                    [PDF] [Alerts]   ← tab bar
                    [Full-width content area]
                    Tapping alert → switches to PDF tab, scrolls to clause
```

### 8.2 Onboarding Sample Project (FLAG-19)

```
Step 1: Welcome → Role selection
Step 2: First Upload → Two CTAs:
  [Upload your documents]  ← primary
  [Try with sample data]   ← secondary, calls POST /api/v1/onboarding/sample-project
                              Backend creates pre-analyzed project with 8 demo docs
Step 3: Processing → SSE stepper (real for upload, instant for sample)
Step 4: Guided Review → Highlight first alert, explain score
```

**Demo mode:** MSW simulates both paths with `@mswjs/data` seed data.
**Production mode:** Backend endpoint required by Sprint 2.

### 8.3 Alert Review — Undo Pattern (FLAG-17)

```typescript
// Both approve AND undo invalidate coherence dashboard
const approveMutation = useMutation({
  mutationFn: postAlertApprove,
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: ['coherence'] });
    queryClient.invalidateQueries({ queryKey: ['alerts'] });
  },
});

// Undo uses soft-delete: POST /api/v1/alerts/{id}/undo within 5s window
const undoMutation = useMutation({
  mutationFn: postAlertUndo,
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: ['coherence'] }); // Same invalidation!
    queryClient.invalidateQueries({ queryKey: ['alerts'] });
  },
});
```

### 8.4 Processing State Visibility (FLAG-22)

Global indicator in sidebar when any project is processing:

```tsx
// src/components/layout/AppSidebar.tsx
function ProcessingIndicator() {
  const activeJobs = useProcessingStore((s) => s.activeJobs);
  const jobCount = Object.keys(activeJobs).filter(
    id => !activeJobs[id].complete
  ).length;

  if (jobCount === 0) return null;

  return (
    <div className="mx-3 rounded-md bg-primary/10 p-2 text-xs">
      <div className="flex items-center gap-2">
        <Spinner className="h-3 w-3" />
        <span>{jobCount} project{jobCount > 1 ? 's' : ''} processing</span>
      </div>
    </div>
  );
}
```

---

## 9. Sprint Execution Plan — Corrected & Sequenced

### Sprint 1: Foundation + Critical Fixes (Weeks 1–2)

**Goal:** `pnpm dev:demo` shows styled app shell with mock data. All critical flags resolved.

| Day | Task | Flag Resolution | Deliverable |
|-----|------|-----------------|-------------|
| 1 | Next.js 15.3 + Turbopack init | — | `apps/web/` boots <2s |
| 1 | `pnpm-workspace.yaml` + monorepo basics | FLAG-16 | Root config |
| 2-3 | Tailwind v4 CSS-first + corrected tokens | **FLAG-8** | `--primary-text` token, all vars |
| 3 | `next/font/local` Inter + JetBrains | **FLAG-10** | ~40KB fonts |
| 4 | Shadcn/ui init (15 components) | — | Button, Card, Badge, Dialog... |
| 5 | App shell (sidebar + header + breadcrumb) | — | Responsive layout |
| 6 | Clerk auth + **AuthSync component** | **FLAG-1, FLAG-2** | Sole auth source |
| 6 | Refactored `stores/auth.ts` | **FLAG-5** | No more `require()` |
| 7 | Org-switch cache clear | **FLAG-4** | `queryClient.clear()` |
| 7 | Zustand stores (app-mode, sidebar, filters) | — | 4 stores |
| 8 | MSW v2 setup (browser + node + instrumentation) | — | Demo mode |
| 8 | Orval config + first codegen | — | Generated hooks + mocks |
| 9 | **Delete manual queryKeys**, use Orval-generated | **FLAG-21** | Single cache key source |
| 9 | Test-utils with **Clerk mock** | **FLAG-26** | Shared test wrapper |
| 9 | Document layer rules (Server vs Client) | **FLAG-6** | ADR-002 |
| 10 | CI pipeline (typecheck + lint + test + orval --check) | **FLAG-11** (supersede old test plan) | Green CI |
| 10 | Sentry error tracking (no Replay yet) | — | Error capture |

**Sprint 1 Flag Resolution: 10 flags (FLAG-1, 2, 4, 5, 6, 8, 10, 11, 21, 26)**

**Acceptance criteria:**
- Login → empty dashboard with sidebar/header/demo banner
- Auth works exclusively through Clerk → AuthSync → Zustand
- `text-primary-text` used for all text on light backgrounds (2.74:1 → 4.52:1)
- Fonts load via `next/font/local` (~40KB, swap)
- `orval --check` passes in CI
- 37 tests passing (30 unit, 5 integration, 2 E2E)

---

### Sprint 2: Dual-Mode Pipeline + Data Views (Weeks 3–4)

**Goal:** Project list and Coherence Dashboard render with real/mock data.

| Day | Task | Flag Resolution | Deliverable |
|-----|------|-----------------|-------------|
| 1-2 | @mswjs/data seed models (8 entities) | — | Deterministic demo |
| 2 | Custom MSW handlers (**SSE streaming**) | **FLAG-12** | Test-ready stream |
| 3 | Orval CI check enforcement | — | Blocks merge on drift |
| 3 | `useProcessingStore` (Zustand) | **FLAG-22** | Cross-page processing state |
| 4-5 | Project list page (Server Component) | — | Tenant-filtered |
| 5 | Project detail layout (7 tabs) | — | Tab navigation |
| 6-7 | **Custom SVG CoherenceGauge** + 6 ScoreCards | **FLAG-9** | <80KB dashboard |
| 8 | Weight adjuster (sliders, sum=100%) | — | PUT via Orval |
| 8 | Optimistic update with weighted average | — | Instant feedback |
| 9 | Document upload (drag-drop, PDF/XLSX/BC3) | — | Chunked upload |
| 9 | **SSE processing stepper** + `withCredentials` | **FLAG-3** | Authenticated stream |
| 10 | Bundle analyzer CI check | — | Budget enforcement |
| 10 | Three-layer test strategy documented | **FLAG-13** | SC testing approach |

**Sprint 2 Flag Resolution: 5 flags (FLAG-3, 9, 12, 13, 22)**

**Acceptance criteria:**
- Navigate → project → Coherence Score (animated SVG gauge) → adjust weights → upload → stepper
- SSE stream authenticated via Clerk cookie
- Processing visible from sidebar when navigating away
- Dashboard route ≤80KB gzipped (verified by bundle analyzer)
- 88 cumulative tests passing

---

### Sprint 3: Core Views + A11y + GDPR (Weeks 5–6)

**Goal:** All P0 views functional. WCAG 2.2 audit pass 1. GDPR consent.

| Day | Task | Flag Resolution | Deliverable |
|-----|------|-----------------|-------------|
| 1-3 | PDF renderer (lazy) + clause highlighting | — | ≤120KB |
| 3 | **Mobile Evidence Viewer** (tab interface) | **FLAG-18** | Responsive |
| 4 | Dynamic watermark (**pseudonymized ID**) | **FLAG-31** | No raw PII |
| 5-6 | Alert Review Center + approve/reject modal | — | Full CRUD |
| 6 | **Focus-scoped keyboard shortcuts** | **FLAG-7** | WCAG 2.1.4 |
| 6 | **Undo pattern** with double invalidation | **FLAG-17** | Coherence stays fresh |
| 7 | Severity badge (triple-encoded) | — | Color+shape+text |
| 8 | Stakeholder Map + RACI Matrix | — | Scatter + grid |
| 9 | Legal disclaimer modal (Gate 8) | — | Backend-persisted |
| 9 | **Cookie consent banner** | **FLAG-14** | GDPR compliance |
| 9 | `sessionStorage` persistence for filters | FLAG-30 | Preserved on refresh |
| 10 | **Onboarding sample project** frontend | **FLAG-19** | Time-to-value <5min |
| 10 | A11y audit pass 1 (axe-core) | — | Zero critical violations |
| 10 | Responsive pass (tablet `@container`) | — | Tablet-friendly |

**Sprint 3 Flag Resolution: 7 flags (FLAG-7, 14, 17, 18, 19, 30, 31)**

**Acceptance criteria:**
- Full flow: Dashboard → Evidence → PDF highlighting → alert approve → undo → RACI
- Mobile Evidence Viewer works on 375px viewport
- `axe-core` returns zero critical/serious violations
- Cookie consent appears for new EU users
- 149 cumulative tests

---

### Sprint 4: Admin + Polish + Production (Weeks 7–8)

**Goal:** Production-ready. Admin portal. Performance targets met. WCAG verified.

| Task | Flag Resolution | Deliverable |
|------|-----------------|-------------|
| Admin layout + Tremor (lazy-loaded) | FLAG-24 | Role-gated admin |
| Tenant management, AI cost dashboard | — | Admin views |
| Onboarding flow (4 steps, full) | — | Welcome→Upload→Process→Review |
| Error boundaries (root → dashboard → feature) | — | Graceful degradation |
| Loading skeletons (all pages, zero CLS) | — | Skeleton per component |
| Performance optimization (Lighthouse ≥90) | — | Verified targets |
| WCAG 2.2 full audit (NVDA + VoiceOver) | — | Manual SR testing |
| E2E test suite (Playwright, dual-mode) | — | 15+ specs |
| `refetchOnWindowFocus` for coherence/alerts | FLAG-23 | Cross-tab freshness |
| Command palette scope definition | FLAG-29 | `Cmd+K` navigation |
| OpenTelemetry + Sentry correlation | — | Frontend→backend traces |
| Production deploy checklist | — | Env vars, CSP, headers |

**Sprint 4 Flag Resolution: remaining flags (23, 24, 29 + monitoring 15, 20, 25, 27)**

---

## 10. Remaining Gotchas — Detection & Mitigation

### 10.1 State Desync Scenarios

| Scenario | Detection | Mitigation |
|----------|-----------|------------|
| Clerk token expires, Zustand holds stale | AuthSync re-syncs every 50s. 401 interceptor calls `clear()`. | Automatic. Monitored via Sentry breadcrumb "auth-sync-expired". |
| SSE completes but TanStack serves cached score | `refetchOnMount: 'always'` for coherence dashboard. SSE handler awaits `refetchQueries` before navigation. | Automatic per ADR-004. |
| User opens Tab 2, approves alert, Tab 1 stale | Sprint 4: `refetchOnWindowFocus: true` for coherence + alerts. | Self-correcting on tab focus. |
| Org switch leaves old tenant data in memory | `queryClient.clear()` in AuthSync on org change. | Automatic per ADR-001. |
| Processing store shows stale progress after page refresh | Store has no persistence. On page mount, check `GET /api/v1/projects/{id}/processing/status`. | REST fallback + SSE reconnect. |

### 10.2 UX Regression Risks

| Risk | Trigger | Prevention |
|------|---------|------------|
| Score count-up animation breaks with custom gauge | Switching from Recharts to SVG | Count-up is CSS `transition-[stroke-dashoffset]` — test with `prefers-reduced-motion` |
| Dark mode breaks chart colors | Inline hex in Recharts, missing CSS var in custom gauge | `useThemeColors()` hook + Chromatic snapshots in both themes |
| Onboarding dead-ends if sample project API fails | Network error on `POST /api/v1/onboarding/sample-project` | Fallback: "Upload your own documents" CTA, don't block onboarding |
| Legal disclaimer blocks navigation after session clear | Clerk session drops, disclaimer state lost | Re-check disclaimer via API on each authenticated load, not `localStorage` |
| Filter reset frustrates power users | Page refresh clears complex filter sets | Sprint 3: `sessionStorage` persistence (FLAG-30) |

### 10.3 Bundle Size Creep Prevention

| Checkpoint | Where | Action |
|------------|-------|--------|
| PR-level | `next build && npx @next/bundle-analyzer` in CI | Hard fail if any route exceeds budget |
| Weekly | Manual `npx depcheck` for unused deps | Remove dead dependencies |
| Per-sprint | `importcost` VS Code extension for new imports | Catch heavy imports early |
| Before merge | ESLint `no-restricted-imports` for known heavy packages | Block top-level Recharts/Tremor/PDF imports |

```javascript
// .eslintrc.js — no-restricted-imports
rules: {
  'no-restricted-imports': ['error', {
    patterns: [
      { group: ['recharts'], message: 'Use next/dynamic for Recharts. Import via lazy wrapper.' },
      { group: ['@tremor/react'], message: 'Tremor is admin-only. Use next/dynamic.' },
      { group: ['@react-pdf-viewer/*'], message: 'PDF viewer must use next/dynamic with ssr:false.' },
    ],
  }],
},
```

### 10.4 Browser/Device Edge Cases

| Edge Case | Affected | Detection | Fix |
|-----------|----------|-----------|-----|
| Safari SSE drops after ~60s idle | Safari 16-17 | `source.readyState === CLOSED` in `setTimeout` | Fallback to polling (implemented in ADR-004) |
| `oklch()` parse failure | Chrome <111, Firefox <113 | CSS `@supports not (color: oklch(0 0 0))` | Hex fallback in token layer (Tailwind v4 handles) |
| PDF.js Web Worker blocked by CSP | All browsers if worker-src missing | Blank PDF viewer + console error | `worker-src blob: 'self'` in CSP (§5.1) |
| iOS Safari viewport resize on keyboard show | iPhone | CLS spike when input focused | `height: 100dvh` instead of `100vh` in layout |
| Pinch-zoom on PDF interferes with page zoom | Mobile Safari | Inadvertent page zoom | `touch-action: pan-x pan-y` on PDF container |
| Zustand `persist` hydration mismatch (SSR) | All — Next.js SSR | Hydration warning in console | Use `onRehydrateStorage` callback, skip SSR for persisted values |

---

## 11. Feature Flag Strategy

```typescript
// src/stores/app-mode.ts — Extended with feature flags
export const useAppModeStore = create<{
  mode: 'production' | 'demo';
  features: {
    ppr: boolean;              // Partial Pre-Rendering
    reactCompiler: boolean;    // React Compiler optimizations
    sentryReplay: boolean;     // Sentry session replay (post-consent)
    onboarding: boolean;       // 4-step onboarding flow
    adminPortal: boolean;      // Admin portal access
    commandPalette: boolean;   // Cmd+K command palette
    keyboardShortcuts: boolean;// j/k/a/r shortcuts
  };
  demoProjectId: string;
  showDemoBanner: boolean;
}>()( /* ... */ );
```

**Rollout schedule:**

| Feature | Sprint 1 | Sprint 2 | Sprint 3 | Sprint 4 |
|---------|----------|----------|----------|----------|
| PPR | ✅ ON (coherence only) | ✅ ON | ✅ ON | ✅ ON |
| React Compiler | ✅ ON | ✅ ON (monitor) | ✅ ON | ✅ ON |
| Sentry Replay | ❌ OFF | ❌ OFF | ✅ ON (post-consent) | ✅ ON |
| Onboarding | ❌ OFF | ❌ OFF | ✅ ON (Beta) | ✅ ON |
| Admin Portal | ❌ OFF | ❌ OFF | ❌ OFF | ✅ ON |
| Command Palette | ❌ OFF | ❌ OFF | ❌ OFF | ✅ ON (Beta) |
| Keyboard Shortcuts | ❌ OFF | ❌ OFF | ✅ ON (focus-scoped) | ✅ ON |

---

## 12. Refactor Order — Mental Execution Simulation

This is the exact sequence for a solo developer executing Sprint 1, Day 1 through Day 10:

```
Day 1 Morning:
  $ pnpm create next-app@latest apps/web --ts --tailwind --app --turbopack
  $ echo 'packages:\n  - "apps/*"' > pnpm-workspace.yaml
  Verify: pnpm dev starts in <2s

Day 1 Afternoon:
  Create globals.css with CORRECTED tokens (--primary-text: oklch(0.42 0.10 195))
  Download InterVariable.woff2, JetBrainsMono.woff2 to src/fonts/
  Configure next/font/local in layout.tsx
  DELETE @fontsource from package.json
  Verify: text renders in Inter, no FOIT

Day 2-3:
  npx shadcn-ui@latest init
  Add 15 components (button, card, badge, dialog, sheet, sidebar, select, input,
    textarea, label, skeleton, toast, dropdown-menu, command, table)
  Audit: grep for text-primary, replace with text-primary-text where on light bg
  Verify: all components render correctly in Storybook (optional) or in a test page

Day 4:
  Build app shell: AppSidebar + Header + DemoBanner + MobileBottomNav
  Use sidebar.tsx from Shadcn + useSidebarStore
  Verify: sidebar toggles, responsive breakpoints work

Day 5:
  npm install @clerk/nextjs
  Create AuthSync.tsx (§1.1 — exact code)
  Refactor stores/auth.ts (§1.1 — exact code)
  Refactor lib/api/client.ts (§1.1 — exact code)
  Wire AuthSync into providers: ClerkProvider → AuthSync → QueryClientProvider → ThemeProvider
  Create middleware.ts with Clerk route protection
  Verify: login → Zustand shows token → API calls include Bearer header

Day 6:
  Add org-switch cache clear to AuthSync (FLAG-4 code from §1.1)
  Create stores: app-mode.ts, sidebar.ts, filters.ts (TDD code, unchanged)
  Verify: org switch clears all cached data

Day 7:
  MSW v2 setup: browser.ts, node.ts, instrumentation.ts
  Orval config (TDD orval.config.ts, unchanged)
  First orval codegen run
  DELETE any manual queryKeys object
  Verify: demo mode serves mock data, Orval hooks work

Day 8:
  Create test-utils.tsx (§7.1 — with Clerk mock)
  Write first 15 unit tests (stores, ui components)
  Verify: vitest --run passes

Day 9:
  Create ADR-002 document (layer rules)
  Write 15 more unit tests + 5 integration tests
  Verify: coverage meets 80% for touched files

Day 10:
  CI pipeline: .github/workflows/ci.yml
    typecheck → lint → test → orval --check → coverage report
  Sentry init (error tracking only, no Replay)
  Tag: v0.1.0-sprint1
  Verify: CI green, Sentry receives test error
```

---

## 13. Deployment Configuration

### 13.1 Environment Variables

```bash
# .env.local (development)
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_SENTRY_DSN=https://...@sentry.io/...
NEXT_PUBLIC_IS_DEMO=true

# .env.production
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...
CLERK_SECRET_KEY=sk_live_...
NEXT_PUBLIC_API_BASE_URL=https://api.c2pro.io
NEXT_PUBLIC_SENTRY_DSN=https://...@sentry.io/...
NEXT_PUBLIC_IS_DEMO=false
```

### 13.2 Production Checklist

| Item | Status | Sprint | Owner |
|------|--------|--------|-------|
| CSP headers configured | ⬜ → ✅ | 1 | FE |
| Security headers (X-Frame, X-Content-Type, Referrer) | ✅ | 1 | FE |
| Sentry error tracking (no Replay) | ⬜ → ✅ | 1 | FE |
| Environment variables validated at build | ⬜ → ✅ | 1 | FE |
| `next/font/local` (no @fontsource) | ⬜ → ✅ | 1 | FE |
| `--primary-text` contrast fix | ⬜ → ✅ | 1 | FE |
| AuthSync pattern (no dual auth) | ⬜ → ✅ | 1 | FE |
| Bundle size budgets enforced in CI | ⬜ → ✅ | 2 | FE |
| SSE authentication (withCredentials) | ⬜ → ✅ | 2 | FE + BE |
| Cookie consent (GDPR) | ⬜ → ✅ | 3 | FE |
| Sentry Replay (post-consent only) | ⬜ → ✅ | 3 | FE |
| WCAG 2.2 AA audit (automated + manual) | ⬜ → ✅ | 4 | FE |
| Lighthouse ≥90 all routes | ⬜ → ✅ | 4 | FE |
| E2E suite green (dual-mode) | ⬜ → ✅ | 4 | FE |
| OpenTelemetry trace correlation | ⬜ → ✅ | 4 | FE + BE |
| Source maps hidden from client | ✅ | 1 | FE |
| Vercel preview deployments on PR | ⬜ → ✅ | 1 | DevOps |

---

## 14. Document Supersession Notice

This Frontend Master Plan v1.0 **supersedes** the following sections and documents:

| Document | Sections Superseded | Reason |
|----------|-------------------|--------|
| TDD v3.0 §2.2.1 | API Client (Axios interceptor) | AUTH redesign (FLAG-1, 2, 5) |
| TDD v3.0 §2.3 | globals.css `@import` fonts | Replaced with `next/font/local` (FLAG-10) |
| TDD v3.0 §2.3 | `--primary` color definition | Extended with `--primary-text` (FLAG-8) |
| TDD v3.0 §7.3 | State boundary rules | `Auth token + tenant ID` moved from Zustand-owned to Clerk-synced |
| TDD v3.0 §3 | Directory: `stores/auth.ts` | Refactored to sync-only cache |
| `FRONTEND_TESTING_PLAN.md` | **Entire document** | Outdated (Next.js 14, custom JWT) — replaced by §7 (FLAG-11) |

All other TDD v3.0 sections remain valid and are incorporated by reference.

---

> **Document status:** Implementation-ready. All 31 Phase 2 flags resolved or accepted with documented mitigations. Zero open critical or high-severity items.

---

> Do you want to refine any frontend dimension further (UX, accessibility, performance, state management, design system, or testing strategy)?
