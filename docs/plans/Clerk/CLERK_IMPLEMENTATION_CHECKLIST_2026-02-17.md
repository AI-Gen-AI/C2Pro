# Clerk + Supabase Integration Implementation Checklist

**Created:** February 17, 2026
**Status:** IN PROGRESS
**Lead:** Jesus (C2Pro)
**Estimated Duration:** 8-10 days

---

## Executive Summary

This plan implements Clerk authentication with Supabase RLS for multi-tenant isolation in C2Pro. The implementation follows a frontend-first approach, enabling rapid iteration and immediate user testing.

---

## Current State Analysis

### Already Implemented

| Component | Status | Location |
|-----------|--------|----------|
| `@clerk/nextjs` package | ✅ DONE | `package.json` v6.12.0 |
| Clerk API keys | ✅ DONE | `.env.local` |
| `ClerkProvider` wrapper | ✅ DONE | `app/providers.tsx` |
| `AuthContext` with Clerk hooks | ✅ DONE | `contexts/AuthContext.tsx` |
| `ProtectedRoute` component | ✅ DONE | `components/auth/ProtectedRoute.tsx` |
| `AuthSync` provider | ✅ DONE | `components/providers/AuthSync.tsx` |
| Clerk organizations created | ✅ DONE | Clerk Dashboard |

### Implementation Progress

| Component | Status | Priority | Location |
|-----------|--------|----------|----------|
| `middleware.ts` (route protection) | ✅ DONE | P0 | `apps/web/middleware.ts` |
| Sign-in page with Clerk `<SignIn>` | ✅ DONE | P0 | `app/(auth)/sign-in/[[...sign-in]]/page.tsx` |
| Sign-up page with Clerk `<SignUp>` | ✅ DONE | P0 | `app/(auth)/sign-up/[[...sign-up]]/page.tsx` |
| `/login` redirect to `/sign-in` | ✅ DONE | P0 | `app/(auth)/login/page.tsx` |
| `/register` redirect to `/sign-up` | ✅ DONE | P0 | `app/(auth)/register/page.tsx` |
| `clerk-tenant.ts` bridge layer | ✅ DONE | P1 | `lib/clerk-tenant.ts` |
| RBAC `FeatureGate` component | ✅ DONE | P1 | `components/auth/rbac-components.tsx` |
| RBAC `AdminOnly` component | ✅ DONE | P1 | `components/auth/rbac-components.tsx` |
| Env variables (SIGN_IN_URL, etc.) | ⚠️ MANUAL | P0 | `.env.local` (needs manual update) |
| `DemoModeProvider` context | ✅ DONE | P2 | `contexts/demo-mode.tsx` |
| Backend JWT middleware | ✅ DONE | P2 | `apps/api/src/core/middleware/clerk_auth.py` |
| SQL migration (RLS update) | ✅ DONE | P3 | `supabase/migrations/20260217000000_clerk_integration.sql` |
| Clerk org metadata (tenant_id) | ⚠️ MANUAL | P1 | Clerk Dashboard (user to configure) |
| AuthContext tenant_id exposure | ✅ DONE | P1 | `contexts/AuthContext.tsx` |
| DemoModeProvider in providers | ✅ DONE | P2 | `app/providers.tsx` |
| Config settings for Clerk | ✅ DONE | P2 | `apps/api/src/config.py` |

---

## Phase 1: Frontend Core Authentication (Day 1-2)

### Task 1.1: Create Clerk Middleware

**File:** `apps/web/middleware.ts`

**Status:** ❌ PENDING

**Dependencies:** None

**Description:**
Create Next.js middleware using Clerk v6 `clerkMiddleware` to protect routes and handle authentication redirects.

**Implementation Details:**

```typescript
// apps/web/middleware.ts
import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'

const isPublicRoute = createRouteMatcher([
  '/',
  '/sign-in(.*)',
  '/sign-up(.*)',
  '/pricing',
  '/about',
  '/api/webhooks/clerk(.*)',
  '/api/health',
])

export default clerkMiddleware(async (auth, req) => {
  if (!isPublicRoute(req)) {
    await auth.protect()
  }
})

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
}
```

**Acceptance Criteria:**
- [ ] File created at `apps/web/middleware.ts`
- [ ] Public routes accessible without auth
- [ ] Protected routes redirect to `/sign-in`
- [ ] API routes return 401 without valid token
- [ ] No TypeScript errors

---

### Task 1.2: Create Sign-In Page

**File:** `apps/web/app/(auth)/sign-in/[[...sign-in]]/page.tsx`

**Status:** ❌ PENDING

**Dependencies:** Task 1.1

**Description:**
Replace custom login page with Clerk's `<SignIn>` component using C2Pro's dark theme styling.

**Implementation Details:**

```typescript
// apps/web/app/(auth)/sign-in/[[...sign-in]]/page.tsx
import { SignIn } from '@clerk/nextjs'

export default function SignInPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white">C2Pro</h1>
          <p className="text-slate-400 mt-2">Contract Intelligence Platform</p>
        </div>
        <SignIn
          appearance={{
            elements: {
              rootBox: 'w-full',
              card: 'bg-slate-800 border border-slate-700 shadow-2xl rounded-lg',
              headerTitle: 'text-white text-xl font-semibold',
              headerSubtitle: 'text-slate-400',
              socialButtonsBlockButton: 'bg-slate-700 border-slate-600 text-white hover:bg-slate-600',
              socialButtonsBlockButtonText: 'text-white',
              dividerLine: 'bg-slate-600',
              dividerText: 'text-slate-400',
              formFieldLabel: 'text-slate-300',
              formFieldInput: 'bg-slate-700 border-slate-600 text-white placeholder:text-slate-500',
              formButtonPrimary: 'bg-cyan-600 hover:bg-cyan-700 text-white',
              footerActionLink: 'text-cyan-400 hover:text-cyan-300',
              identityPreviewText: 'text-white',
              identityPreviewEditButton: 'text-cyan-400',
            },
          }}
          routing="path"
          path="/sign-in"
          signUpUrl="/sign-up"
        />
      </div>
    </div>
  )
}
```

**Acceptance Criteria:**
- [ ] Page accessible at `/sign-in`
- [ ] Clerk sign-in form displays with C2Pro styling
- [ ] Google OAuth button works
- [ ] Email/password sign-in works
- [ ] Redirects to `/dashboard` after successful sign-in
- [ ] Link to `/sign-up` works

---

### Task 1.3: Create Sign-Up Page

**File:** `apps/web/app/(auth)/sign-up/[[...sign-up]]/page.tsx`

**Status:** ❌ PENDING

**Dependencies:** Task 1.1

**Description:**
Create sign-up page with Clerk's `<SignUp>` component.

**Implementation Details:**

```typescript
// apps/web/app/(auth)/sign-up/[[...sign-up]]/page.tsx
import { SignUp } from '@clerk/nextjs'

export default function SignUpPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white">C2Pro</h1>
          <p className="text-slate-400 mt-2">Create your account</p>
        </div>
        <SignUp
          appearance={{
            elements: {
              rootBox: 'w-full',
              card: 'bg-slate-800 border border-slate-700 shadow-2xl rounded-lg',
              headerTitle: 'text-white text-xl font-semibold',
              headerSubtitle: 'text-slate-400',
              socialButtonsBlockButton: 'bg-slate-700 border-slate-600 text-white hover:bg-slate-600',
              formFieldLabel: 'text-slate-300',
              formFieldInput: 'bg-slate-700 border-slate-600 text-white',
              formButtonPrimary: 'bg-cyan-600 hover:bg-cyan-700 text-white',
              footerActionLink: 'text-cyan-400 hover:text-cyan-300',
            },
          }}
          routing="path"
          path="/sign-up"
          signInUrl="/sign-in"
        />
      </div>
    </div>
  )
}
```

**Acceptance Criteria:**
- [ ] Page accessible at `/sign-up`
- [ ] Clerk sign-up form displays
- [ ] Account creation works
- [ ] Email verification flow works
- [ ] Redirects to onboarding after sign-up

---

### Task 1.4: Update Environment Variables

**File:** `apps/web/.env.local`

**Status:** ❌ PENDING

**Dependencies:** None

**Description:**
Add Clerk URL configuration variables.

**Implementation Details:**

Add to `.env.local`:
```bash
# Clerk URL Configuration
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/onboarding

# Clerk Domain (for backend JWKS)
CLERK_DOMAIN=content-cardinal-74.clerk.accounts.dev
```

**Acceptance Criteria:**
- [ ] Variables added to `.env.local`
- [ ] Clerk redirects work correctly
- [ ] No hardcoded URLs in components

---

### Task 1.5: Update Auth Layout

**File:** `apps/web/app/(auth)/layout.tsx`

**Status:** ❌ PENDING

**Dependencies:** Tasks 1.2, 1.3

**Description:**
Create/update auth layout for sign-in/sign-up pages.

**Implementation Details:**

```typescript
// apps/web/app/(auth)/layout.tsx
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {children}
    </div>
  )
}
```

**Acceptance Criteria:**
- [ ] Layout applies to auth pages
- [ ] Consistent styling across sign-in/sign-up

---

### Task 1.6: Deprecate Old Login/Register Pages

**Files:**
- `apps/web/app/(auth)/login/page.tsx`
- `apps/web/app/(auth)/register/page.tsx`

**Status:** ❌ PENDING

**Dependencies:** Tasks 1.2, 1.3

**Description:**
Add redirects from old `/login` and `/register` to new Clerk pages.

**Implementation Details:**

```typescript
// apps/web/app/(auth)/login/page.tsx
import { redirect } from 'next/navigation'

export default function LoginPage() {
  redirect('/sign-in')
}
```

```typescript
// apps/web/app/(auth)/register/page.tsx
import { redirect } from 'next/navigation'

export default function RegisterPage() {
  redirect('/sign-up')
}
```

**Acceptance Criteria:**
- [ ] `/login` redirects to `/sign-in`
- [ ] `/register` redirects to `/sign-up`
- [ ] No broken links in app

---

## Phase 2: Bridge Layer & Tenant Context (Day 3-4)

### Task 2.1: Create Clerk-Tenant Bridge Layer

**File:** `apps/web/lib/clerk-tenant.ts`

**Status:** ❌ PENDING

**Dependencies:** Phase 1 complete

**Description:**
Create bridge layer that maps Clerk organization to Supabase tenant_id. This is the CRITICAL layer for multi-tenancy.

**Implementation Details:**

```typescript
// apps/web/lib/clerk-tenant.ts
'use client'

import { useAuth, useUser, useOrganization } from '@clerk/nextjs'
import { useEffect, useState } from 'react'

/**
 * Main hook to get tenant context from Clerk organization
 */
export function useTenantContext() {
  const { userId, isLoaded: authLoaded } = useAuth()
  const { organization, membership, isLoaded: orgLoaded } = useOrganization()

  const [tenantId, setTenantId] = useState<string | null>(null)
  const [isDemoMode, setIsDemoMode] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoaded || !orgLoaded) {
      setIsLoading(true)
      return
    }

    try {
      if (!userId) {
        setTenantId(null)
        setIsDemoMode(false)
        setIsLoading(false)
        return
      }

      if (!organization) {
        setTenantId(null)
        setIsDemoMode(false)
        setIsLoading(false)
        return
      }

      // Extract tenant_id from Clerk organization metadata
      const clerkTenantId = (organization.publicMetadata as Record<string, unknown>)?.tenant_id as string | undefined

      if (!clerkTenantId) {
        setError(`Organization ${organization.name} has no tenant_id configured`)
        setTenantId(null)
        setIsLoading(false)
        return
      }

      const isDemoOrg = (organization.publicMetadata as Record<string, unknown>)?.is_demo === true

      setTenantId(clerkTenantId)
      setIsDemoMode(isDemoOrg)
      setError(null)
      setIsLoading(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      setTenantId(null)
      setIsLoading(false)
    }
  }, [userId, organization, authLoaded, orgLoaded])

  return {
    userId,
    tenantId,
    isDemoMode,
    organization,
    membership,
    isLoading,
    error,
    isAuthenticated: !!userId,
    isAuthorized: !!tenantId,
  }
}

/**
 * Hook to check user role within their organization
 */
export function useUserRole() {
  const { membership, isLoaded } = useOrganization()

  const [role, setRole] = useState<'admin' | 'member' | null>(null)
  const [permissions, setPermissions] = useState<string[]>([])

  useEffect(() => {
    if (!isLoaded || !membership) {
      setRole(null)
      setPermissions([])
      return
    }

    const userRole = membership.role === 'org:admin' ? 'admin' : 'member'
    setRole(userRole)

    const rolePermissions =
      userRole === 'admin'
        ? [
            'read:projects',
            'write:projects',
            'delete:projects',
            'manage:users',
            'manage:documents',
            'view:analytics',
            'manage:settings',
          ]
        : [
            'read:projects',
            'write:projects',
            'manage:documents',
            'view:analytics',
          ]

    setPermissions(rolePermissions)
  }, [membership, isLoaded])

  return {
    role,
    permissions,
    isAdmin: role === 'admin',
    isMember: role === 'member',
    hasPermission: (permission: string) => permissions.includes(permission),
  }
}

/**
 * Hook to get service tier from organization metadata
 */
export function useServiceTier() {
  const { organization, isLoaded: orgLoaded } = useOrganization()
  const { user, isLoaded: userLoaded } = useUser()

  const [tier, setTier] = useState<'free' | 'pro' | 'enterprise'>('free')
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!orgLoaded || !userLoaded) {
      setIsLoading(true)
      return
    }

    try {
      const orgTier = (organization?.publicMetadata as Record<string, unknown>)?.tier as string | undefined

      if (orgTier && ['free', 'pro', 'enterprise'].includes(orgTier)) {
        setTier(orgTier as 'free' | 'pro' | 'enterprise')
        setIsLoading(false)
        return
      }

      const userTier = (user?.publicMetadata as Record<string, unknown>)?.tier as string || 'free'

      if (['free', 'pro', 'enterprise'].includes(userTier)) {
        setTier(userTier as 'free' | 'pro' | 'enterprise')
      } else {
        setTier('free')
      }

      setIsLoading(false)
    } catch (error) {
      console.error('Error getting service tier:', error)
      setTier('free')
      setIsLoading(false)
    }
  }, [organization, user, orgLoaded, userLoaded])

  return {
    tier,
    isLoading,
    isFree: tier === 'free',
    isPro: tier === 'pro',
    isEnterprise: tier === 'enterprise',
  }
}

/**
 * Service tier feature matrix
 */
export const TIER_FEATURES = {
  free: {
    maxProjects: 1,
    maxUsers: 1,
    maxDocuments: 10,
    stakeholderRaci: false,
    apiAccess: false,
    webhooks: false,
    sso: false,
    supportLevel: 'email',
  },
  pro: {
    maxProjects: 10,
    maxUsers: 5,
    maxDocuments: 100,
    stakeholderRaci: true,
    apiAccess: true,
    webhooks: false,
    sso: false,
    supportLevel: 'chat',
  },
  enterprise: {
    maxProjects: -1, // unlimited
    maxUsers: -1,
    maxDocuments: -1,
    stakeholderRaci: true,
    apiAccess: true,
    webhooks: true,
    sso: true,
    supportLevel: 'dedicated',
  },
} as const

export type TierFeatures = typeof TIER_FEATURES
export type Tier = keyof TierFeatures
```

**Acceptance Criteria:**
- [ ] File created at `apps/web/lib/clerk-tenant.ts`
- [ ] `useTenantContext()` returns tenant_id from org metadata
- [ ] `useUserRole()` returns admin/member role
- [ ] `useServiceTier()` returns free/pro/enterprise
- [ ] No TypeScript errors
- [ ] Unit tests pass

---

### Task 2.2: Create RBAC Components

**File:** `apps/web/components/auth/rbac-components.tsx`

**Status:** ❌ PENDING

**Dependencies:** Task 2.1

**Description:**
Create role-based and tier-based access control components.

**Implementation Details:**

```typescript
// apps/web/components/auth/rbac-components.tsx
'use client'

import { ReactNode } from 'react'
import { useAuth } from '@clerk/nextjs'
import { redirect } from 'next/navigation'
import { useTenantContext, useServiceTier, useUserRole, TIER_FEATURES, Tier } from '@/lib/clerk-tenant'
import { Loader2, Lock, Sparkles } from 'lucide-react'

interface FeatureGateProps {
  children: ReactNode
  requiredTier?: Tier
  featureName?: string
  showUpgrade?: boolean
}

export function FeatureGate({
  children,
  requiredTier = 'free',
  featureName = 'This feature',
  showUpgrade = true,
}: FeatureGateProps) {
  const { tier, isLoading } = useServiceTier()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-4">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const tierLevels = { free: 1, pro: 2, enterprise: 3 }
  const hasAccess = tierLevels[tier] >= tierLevels[requiredTier]

  if (!hasAccess) {
    if (showUpgrade) {
      return (
        <div className="p-6 bg-gradient-to-r from-cyan-500/10 to-blue-500/10 border border-cyan-500/20 rounded-lg">
          <div className="flex items-start gap-4">
            <div className="p-2 bg-cyan-500/20 rounded-lg">
              <Sparkles className="h-5 w-5 text-cyan-400" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-white mb-1">
                {featureName} requires {requiredTier.charAt(0).toUpperCase() + requiredTier.slice(1)} Plan
              </h3>
              <p className="text-sm text-slate-400 mb-4">
                Upgrade your plan to unlock this feature and get access to advanced capabilities.
              </p>
              <button
                onClick={() => window.location.href = '/settings/billing'}
                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white text-sm font-medium rounded-lg transition-colors"
              >
                Upgrade Now
              </button>
            </div>
          </div>
        </div>
      )
    }
    return null
  }

  return <>{children}</>
}

interface AdminOnlyProps {
  children: ReactNode
  fallback?: ReactNode
}

export function AdminOnly({ children, fallback }: AdminOnlyProps) {
  const { isAdmin, role } = useUserRole()

  if (role === null) {
    return (
      <div className="flex items-center justify-center p-4">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!isAdmin) {
    return fallback || (
      <div className="p-6 bg-red-500/10 border border-red-500/20 rounded-lg">
        <div className="flex items-center gap-3">
          <Lock className="h-5 w-5 text-red-400" />
          <p className="text-red-400 font-medium">Admin access required</p>
        </div>
      </div>
    )
  }

  return <>{children}</>
}

interface TenantRequiredProps {
  children: ReactNode
}

export function TenantRequired({ children }: TenantRequiredProps) {
  const { tenantId, isLoading, error } = useTenantContext()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-cyan-500" />
      </div>
    )
  }

  if (!tenantId) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="text-center max-w-md">
          <h1 className="text-2xl font-bold text-white mb-4">
            Organization Required
          </h1>
          <p className="text-slate-400 mb-6">
            {error || 'Please select or create an organization to continue.'}
          </p>
          <button
            onClick={() => window.location.href = '/onboarding'}
            className="px-6 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg"
          >
            Set Up Organization
          </button>
        </div>
      </div>
    )
  }

  return <>{children}</>
}

interface DemoModeGuardProps {
  children: ReactNode
  action: string
}

export function DemoModeGuard({ children, action }: DemoModeGuardProps) {
  const { isDemoMode } = useTenantContext()

  if (isDemoMode) {
    return (
      <div className="p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
        <p className="text-yellow-400 text-sm font-medium">
          Cannot {action} in demo mode. Switch to your production workspace to make changes.
        </p>
      </div>
    )
  }

  return <>{children}</>
}
```

**Acceptance Criteria:**
- [ ] `FeatureGate` shows upgrade prompt for insufficient tier
- [ ] `AdminOnly` hides content from non-admins
- [ ] `TenantRequired` shows org setup prompt
- [ ] `DemoModeGuard` prevents writes in demo
- [ ] Components use consistent C2Pro styling

---

### Task 2.3: Configure Clerk Organization Metadata

**Location:** Clerk Dashboard

**Status:** ❌ PENDING

**Dependencies:** Organizations created in Clerk

**Description:**
Configure publicMetadata for each organization with tenant_id and tier.

**Implementation Details:**

1. Go to Clerk Dashboard > Organizations > C2Pro Platform Admin
2. Click Settings > Metadata > Edit Public Metadata
3. Add:
```json
{
  "tenant_id": "c2pro-platform-uuid",
  "tier": "enterprise",
  "is_platform_admin": true
}
```

4. Go to Demo Workspace organization
5. Add:
```json
{
  "tenant_id": "demo-tenant-uuid",
  "tier": "enterprise",
  "is_demo": true
}
```

**Generate UUIDs:**
```bash
python -c "import uuid; print(uuid.uuid4())"
```

**Acceptance Criteria:**
- [ ] C2Pro Platform Admin org has `tenant_id` and `tier`
- [ ] Demo Workspace org has `tenant_id`, `tier`, and `is_demo: true`
- [ ] `useTenantContext()` correctly extracts metadata

---

### Task 2.4: Update AuthContext to Use Bridge Layer

**File:** `apps/web/contexts/AuthContext.tsx`

**Status:** ❌ PENDING

**Dependencies:** Task 2.1

**Description:**
Update existing AuthContext to expose tenant_id from bridge layer.

**Implementation Details:**

Update the `AuthContextType` interface and `AuthProvider`:

```typescript
// Add to AuthContextType interface:
tenantId: string | null;
isDemoMode: boolean;
serviceTier: 'free' | 'pro' | 'enterprise';

// In AuthProvider, add:
const { tenantId, isDemoMode } = useTenantContext();
const { tier } = useServiceTier();

// Update value:
tenantId,
isDemoMode,
serviceTier: tier,
```

**Acceptance Criteria:**
- [ ] `useAuth()` returns `tenantId`
- [ ] `useAuth()` returns `isDemoMode`
- [ ] `useAuth()` returns `serviceTier`
- [ ] Existing functionality preserved

---

## Phase 3: Demo Mode Context (Day 5)

### Task 3.1: Create Demo Mode Provider

**File:** `apps/web/contexts/demo-mode.tsx`

**Status:** ❌ PENDING

**Dependencies:** Phase 2 complete

**Description:**
Create context for demo mode with sample data and UI indicators.

**Implementation Details:**

Copy and adapt from `docs/plans/Clerk/demo-mode-context.tsx` with:
- Sample projects matching C2Pro domain
- Sample alerts with coherence categories
- Sample stakeholders with RACI roles
- Demo mode indicator banner
- Demo/Production toggle

**Acceptance Criteria:**
- [ ] `DemoModeProvider` wraps app
- [ ] `useDemoMode()` returns demo state and data
- [ ] `DemoModeIndicator` shows when in demo
- [ ] Sample data matches C2Pro entities

---

## Phase 4: Backend Integration (Day 6-7)

### Task 4.1: Create Backend JWT Middleware

**File:** `apps/api/src/middleware/clerk_auth.py`

**Status:** ❌ PENDING

**Dependencies:** Phase 1 complete

**Description:**
Create FastAPI middleware to verify Clerk JWT tokens.

**Implementation Details:**

Copy from `docs/plans/Clerk/clerk_auth_middleware.py` and:
- Add proper error handling
- Add logging with structlog
- Integrate with existing auth system
- Add dependency injection for routes

**Acceptance Criteria:**
- [ ] JWT verification works
- [ ] `ClerkUser` class extracts claims
- [ ] `get_current_tenant_id()` maps org to tenant
- [ ] 401 returned for invalid tokens
- [ ] Integration with existing middleware

---

### Task 4.2: Run Database Migration

**File:** `infrastructure/supabase/migrations/003_clerk_integration.sql`

**Status:** ❌ PENDING

**Dependencies:** Task 4.1

**Description:**
Run SQL migration to update RLS policies for Clerk integration.

**Implementation Details:**

1. Copy from `docs/plans/Clerk/003_clerk_integration.sql`
2. Verify table names match C2Pro schema
3. Run in Supabase SQL editor
4. Verify RLS policies applied

**Acceptance Criteria:**
- [ ] `organizations` table created
- [ ] `organization_members` table created
- [ ] RLS policies updated
- [ ] Helper functions created
- [ ] Verification queries pass

---

## Phase 5: Testing & Verification (Day 8)

### Task 5.1: End-to-End Auth Flow Test

**Status:** ❌ PENDING

**Dependencies:** All phases complete

**Description:**
Test complete authentication and authorization flow.

**Test Cases:**

1. **Sign Up Flow**
   - [ ] User can create account
   - [ ] Email verification works
   - [ ] Redirected to onboarding

2. **Sign In Flow**
   - [ ] User can sign in with email/password
   - [ ] User can sign in with Google
   - [ ] Redirected to dashboard

3. **Organization Flow**
   - [ ] User can see organization switcher
   - [ ] Switching orgs updates tenant_id
   - [ ] Demo org shows demo indicator

4. **RBAC Flow**
   - [ ] Admin sees admin-only content
   - [ ] Member cannot access admin content
   - [ ] Feature gates work by tier

5. **API Flow**
   - [ ] API calls include JWT
   - [ ] Backend verifies token
   - [ ] RLS filters by tenant_id

---

### Task 5.2: Security Verification

**Status:** ❌ PENDING

**Test Cases:**

- [ ] Cannot access protected routes without auth
- [ ] Cannot access other tenant's data
- [ ] Demo mode prevents writes
- [ ] JWT expiration handled correctly
- [ ] No sensitive data in client-side logs

---

## Verification Script

Run after implementation:

```bash
# Frontend checks
cd apps/web
npm run typecheck
npm run lint
npm run test

# Test sign-in page
curl -I http://localhost:3000/sign-in

# Test protected route redirect
curl -I http://localhost:3000/dashboard
# Should redirect to /sign-in

# Backend checks
cd apps/api
python -m pytest tests/middleware/test_clerk_auth.py -v
```

---

## Rollback Plan

If issues arise:

1. **Remove middleware.ts** - Routes become unprotected
2. **Revert AuthContext** - Remove tenant_id exposure
3. **Keep ClerkProvider** - Basic auth still works
4. **Database** - RLS policies are additive, no data loss

---

## Success Metrics

- [ ] Sign-up to dashboard flow < 30 seconds
- [ ] Zero auth-related console errors
- [ ] 100% of protected routes require auth
- [ ] Tenant isolation verified via RLS logs
- [ ] Demo mode indicator visible when active

---

## Notes & Decisions

1. **Clerk v6 Migration**: Using `clerkMiddleware` instead of deprecated `authMiddleware`
2. **Login URL Strategy**: New `/sign-in` route, `/login` redirects for backwards compatibility
3. **Frontend-First**: Backend JWT verification added after frontend is stable
4. **Demo Mode**: Uses Clerk organization metadata, not separate flag

---

**Last Updated:** February 17, 2026
**Next Review:** After Phase 1 completion
