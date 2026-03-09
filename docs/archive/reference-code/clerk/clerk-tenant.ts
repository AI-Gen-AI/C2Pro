/**
 * Bridge Layer - Maps Clerk organization to Supabase tenant_id
 * 
 * Location: apps/web/src/lib/clerk-tenant.ts
 * 
 * This is the CRITICAL layer that connects:
 * Clerk (Identity) → tenant_id → Supabase RLS
 */

import { useAuth } from '@clerk/nextjs'
import { useOrganization } from '@clerk/nextjs'
import { useEffect, useState, useCallback } from 'react'

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
      // Not authenticated
      if (!userId) {
        setTenantId(null)
        setIsDemoMode(false)
        setIsLoading(false)
        return
      }

      // No organization selected
      if (!organization) {
        setTenantId(null)
        setIsDemoMode(false)
        setIsLoading(false)
        return
      }

      // Extract tenant_id from Clerk organization metadata
      const clerkTenantId = (organization.publicMetadata as any)?.tenant_id

      if (!clerkTenantId) {
        setError(`Organization ${organization.name} has no tenant_id configured`)
        setTenantId(null)
        setIsLoading(false)
        return
      }

      // Check if this is demo mode
      const isDemoOrg = (organization.publicMetadata as any)?.is_demo === true

      setTenantId(clerkTenantId as string)
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

    // Clerk roles: 'admin', 'member', 'guest'
    const userRole = membership.role === 'admin' ? 'admin' : 'member'
    setRole(userRole)

    // Map role to permissions
    const rolePermissions =
      userRole === 'admin'
        ? [
            'read:projects',
            'write:projects',
            'delete:projects',
            'manage:users',
            'manage:documents',
            'view:analytics',
          ]
        : [
            'read:projects',
            'write:projects', // Can only write their own
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
 * Hook to get service tier from organization or user metadata
 */
export function useServiceTier() {
  const { organization, isLoaded: orgLoaded } = useOrganization()
  const { user, isLoaded: userLoaded } = useAuth()

  const [tier, setTier] = useState<'free' | 'pro' | 'enterprise'>('free')
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!orgLoaded || !userLoaded) {
      setIsLoading(true)
      return
    }

    try {
      // Try to get from organization metadata first
      const orgTier = (organization?.publicMetadata as any)?.tier

      if (orgTier && ['free', 'pro', 'enterprise'].includes(orgTier)) {
        setTier(orgTier)
        setIsLoading(false)
        return
      }

      // Fall back to user metadata
      const userTier = (user?.publicMetadata as any)?.tier || 'free'

      if (['free', 'pro', 'enterprise'].includes(userTier)) {
        setTier(userTier)
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
 * Utility to create authorization headers for API requests
 */
export function createAuthHeaders() {
  return {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
  }
}

/**
 * Utility to add tenant context to API requests
 */
export function addTenantToParams(
  params: Record<string, any>,
  tenantId: string
) {
  return {
    ...params,
    tenant_id: tenantId,
  }
}

/**
 * Type definitions for tenant context
 */
export type TenantContext = ReturnType<typeof useTenantContext>
export type UserRole = ReturnType<typeof useUserRole>
export type ServiceTier = ReturnType<typeof useServiceTier>

/**
 * Constants for feature tiers
 */
export const TIER_FEATURES = {
  free: {
    maxProjects: 1,
    maxUsers: 1,
    maxDocuments: 10,
    maxAlerts: 'basic',
    stakeholderRaci: false,
    apiAccess: false,
    webhook: false,
    sso: false,
    supportLevel: 'email',
    sla: 'none',
  },
  pro: {
    maxProjects: 10,
    maxUsers: 5,
    maxDocuments: 100,
    maxAlerts: 'full',
    stakeholderRaci: true,
    apiAccess: true,
    webhook: false,
    sso: false,
    supportLevel: 'chat',
    sla: '99%',
  },
  enterprise: {
    maxProjects: -1, // unlimited
    maxUsers: -1,
    maxDocuments: -1,
    maxAlerts: 'full',
    stakeholderRaci: true,
    apiAccess: true,
    webhook: true,
    sso: true,
    supportLevel: 'dedicated',
    sla: '99.9%',
  },
}

/**
 * Helper to check if feature is available for tier
 */
export function hasFeature(
  tier: 'free' | 'pro' | 'enterprise',
  feature: keyof (typeof TIER_FEATURES)['free']
): boolean {
  const tierFeatures = TIER_FEATURES[tier]
  const featureValue = tierFeatures[feature]

  // Boolean features
  if (typeof featureValue === 'boolean') {
    return featureValue
  }

  // Numeric limits
  if (typeof featureValue === 'number') {
    return featureValue !== 0 && featureValue !== -1
  }

  // String features (like support level)
  return !!featureValue
}

/**
 * Clerk JWT Payload Type (for server-side)
 */
export interface ClerkJWTPayload {
  sub: string // user_id
  email: string
  email_verified: boolean
  first_name: string | null
  last_name: string | null
  picture: string | null
  organization_id?: string
  organization_role?: string
  org_id?: string
  org_slug?: string
  org_role?: string
}
