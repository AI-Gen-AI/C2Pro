/**
 * Protected Routes & RBAC Components
 * 
 * Location: apps/web/src/components/auth/
 * 
 * These components enforce role-based and tier-based access control
 */

'use client'

import { useAuth } from '@clerk/nextjs'
import { useOrganization } from '@clerk/nextjs'
import { redirect } from 'next/navigation'
import { ReactNode } from 'react'
import { useTenantContext, useServiceTier, useUserRole } from '@/lib/clerk-tenant'

/**
 * ProtectedRoute Component
 * 
 * Enforces:
 * - Authentication (must be logged in)
 * - Role-based access (admin, member, etc.)
 * - Organization context (must have tenant_id)
 */
interface ProtectedRouteProps {
  children: ReactNode
  requiredRole?: 'admin' | 'member' | 'c2pro_admin'
  fallback?: ReactNode
}

export function ProtectedRoute({
  children,
  requiredRole,
  fallback,
}: ProtectedRouteProps) {
  const { isLoaded, userId } = useAuth()
  const { tenantId, isLoading } = useTenantContext()
  const { role } = useUserRole()

  // Loading state
  if (!isLoaded || isLoading) {
    return fallback || <LoadingSpinner />
  }

  // Not authenticated
  if (!userId) {
    redirect('/sign-in')
  }

  // No tenant context
  if (!tenantId) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-white mb-4">No Organization</h1>
          <p className="text-slate-400 mb-8">
            Please select an organization or create one to continue.
          </p>
          <button
            onClick={() => redirect('/onboarding')}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg"
          >
            Set Up Organization
          </button>
        </div>
      </div>
    )
  }

  // Check role
  if (requiredRole && role !== requiredRole) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-white mb-4">Access Denied</h1>
          <p className="text-slate-400">
            This page requires {requiredRole} role. You have {role} role.
          </p>
        </div>
      </div>
    )
  }

  return <>{children}</>
}

/**
 * FeatureGate Component
 * 
 * Enforces service tier requirements
 * Shows upgrade prompt if user doesn't meet tier requirement
 */
interface FeatureGateProps {
  children: ReactNode
  requiredTier?: 'free' | 'pro' | 'enterprise'
  featureName?: string
  showBanner?: boolean
}

export function FeatureGate({
  children,
  requiredTier = 'free',
  featureName = 'Advanced Feature',
  showBanner = true,
}: FeatureGateProps) {
  const { tier, isLoading } = useServiceTier()

  if (isLoading) {
    return <LoadingSpinner />
  }

  const tierLevels = { free: 1, pro: 2, enterprise: 3 }
  const hasAccess =
    tierLevels[tier] >= tierLevels[requiredTier]

  if (!hasAccess) {
    if (showBanner) {
      return <UpgradeBanner feature={featureName} requiredTier={requiredTier} />
    }
    return null
  }

  return <>{children}</>
}

/**
 * AdminOnly Component
 * 
 * Only renders if user is admin of current organization
 */
interface AdminOnlyProps {
  children: ReactNode
  fallback?: ReactNode
}

export function AdminOnly({ children, fallback }: AdminOnlyProps) {
  const { isLoaded } = useOrganization()
  const { role } = useUserRole()

  if (!isLoaded) {
    return fallback || <LoadingSpinner />
  }

  if (role !== 'admin') {
    return fallback || <AccessDenied message="Admin access required" />
  }

  return <>{children}</>
}

/**
 * C2ProAdminOnly Component
 * 
 * Only renders for C2Pro platform administrators
 */
interface C2ProAdminOnlyProps {
  children: ReactNode
  fallback?: ReactNode
}

export function C2ProAdminOnly({ children, fallback }: C2ProAdminOnlyProps) {
  const { organization } = useOrganization()
  const isClerksAdmin = organization?.id === 'c2pro-platform'

  if (!isClerksAdmin) {
    return fallback || <AccessDenied message="Platform admin access required" />
  }

  return <>{children}</>
}

/**
 * DemoModeGuard Component
 * 
 * Prevents write operations in demo mode
 */
interface DemoModeGuardProps {
  children: ReactNode
  action: string
  onDemoMode?: () => void
}

export function DemoModeGuard({
  children,
  action,
  onDemoMode,
}: DemoModeGuardProps) {
  const { isDemoMode } = useTenantContext()

  if (isDemoMode) {
    onDemoMode?.()
    return (
      <div className="p-4 bg-yellow-600/10 border border-yellow-600/30 rounded-lg">
        <p className="text-yellow-400 text-sm">
          ⚠️ Cannot {action} in demo mode. Switch to production workspace to make changes.
        </p>
      </div>
    )
  }

  return <>{children}</>
}

/**
 * TenantRequired Component
 * 
 * Ensures user has selected a valid tenant
 */
interface TenantRequiredProps {
  children: ReactNode
}

export function TenantRequired({ children }: TenantRequiredProps) {
  const { tenantId, isLoading } = useTenantContext()

  if (isLoading) {
    return <LoadingSpinner />
  }

  if (!tenantId) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="text-center max-w-md">
          <h1 className="text-2xl font-bold text-white mb-4">
            Organization Required
          </h1>
          <p className="text-slate-400 mb-8">
            Please select or create an organization to access this page.
          </p>
        </div>
      </div>
    )
  }

  return <>{children}</>
}

// ============================================
// UI Components
// ============================================

function LoadingSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-slate-400">Loading...</p>
      </div>
    </div>
  )
}

interface AccessDeniedProps {
  message?: string
}

function AccessDenied({ message = 'Access Denied' }: AccessDeniedProps) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900">
      <div className="text-center max-w-md">
        <div className="mb-4">
          <svg
            className="w-16 h-16 text-red-500 mx-auto"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
            />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-white mb-2">{message}</h1>
        <p className="text-slate-400 mb-8">
          You don't have permission to access this page.
        </p>
        <button
          onClick={() => (window.location.href = '/dashboard')}
          className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg"
        >
          Go to Dashboard
        </button>
      </div>
    </div>
  )
}

interface UpgradeBannerProps {
  feature: string
  requiredTier: 'free' | 'pro' | 'enterprise'
}

function UpgradeBanner({ feature, requiredTier }: UpgradeBannerProps) {
  const tierLabels = {
    free: 'Free Plan',
    pro: 'Pro Plan',
    enterprise: 'Enterprise Plan',
  }

  return (
    <div className="p-6 bg-blue-600/10 border border-blue-600/30 rounded-lg">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-blue-400 mb-2">
            {feature} Requires {tierLabels[requiredTier]}
          </h3>
          <p className="text-blue-300 text-sm">
            Upgrade your account to unlock this feature and get access to advanced capabilities.
          </p>
        </div>
        <button
          onClick={() => (window.location.href = '/pricing')}
          className="ml-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm whitespace-nowrap"
        >
          Upgrade Now
        </button>
      </div>
    </div>
  )
}

// ============================================
// Export all components
// ============================================

export {
  LoadingSpinner,
  AccessDenied,
  UpgradeBanner,
}
