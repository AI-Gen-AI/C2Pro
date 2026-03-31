/**
 * Clerk-Tenant Bridge Layer
 *
 * Maps Clerk organization to Supabase tenant_id for multi-tenancy.
 * This is the CRITICAL layer that connects:
 * Clerk (Identity) -> tenant_id -> Supabase RLS
 *
 * @module lib/clerk-tenant
 */

"use client";

import { useAuth, useUser, useOrganization } from "@clerk/nextjs";
import { useEffect, useState } from "react";

// =============================================================================
// Types
// =============================================================================

export interface TenantContextType {
  userId: string | null | undefined;
  tenantId: string | null;
  isDemoMode: boolean;
  organization: ReturnType<typeof useOrganization>["organization"];
  membership: ReturnType<typeof useOrganization>["membership"];
  isLoading: boolean;
  error: string | null;
  isAuthenticated: boolean;
  isAuthorized: boolean;
}

export function hasOrganizationAccess(
  organization: ReturnType<typeof useOrganization>["organization"],
): boolean {
  return !!organization;
}

export type UserRole = "admin" | "member" | null;
export type ServiceTier = "free" | "pro" | "enterprise";

export function getTenantIdFromOrganizationMetadata(
  organization: ReturnType<typeof useOrganization>["organization"],
): string | null {
  const metadata = organization?.publicMetadata as
    | Record<string, unknown>
    | undefined;
  const tenantId = metadata?.tenant_id;

  return typeof tenantId === "string" && tenantId.length > 0 ? tenantId : null;
}

export function isDemoOrganization(
  organization: ReturnType<typeof useOrganization>["organization"],
): boolean {
  const metadata = organization?.publicMetadata as
    | Record<string, unknown>
    | undefined;

  return metadata?.is_demo === true;
}

// =============================================================================
// Hooks
// =============================================================================

/**
 * Main hook to get tenant context from Clerk organization
 */
export function useTenantContext(): TenantContextType {
  const { userId, isLoaded: authLoaded } = useAuth();
  const { organization, membership, isLoaded: orgLoaded } = useOrganization();

  const [tenantId, setTenantId] = useState<string | null>(null);
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoaded || !orgLoaded) {
      setIsLoading(true);
      return;
    }

    try {
      if (!userId) {
        setTenantId(null);
        setIsDemoMode(false);
        setIsLoading(false);
        return;
      }

      if (!organization) {
        setTenantId(null);
        setIsDemoMode(false);
        setIsLoading(false);
        return;
      }

      const clerkTenantId = getTenantIdFromOrganizationMetadata(organization);
      const isDemoOrg = isDemoOrganization(organization);

      setIsDemoMode(isDemoOrg);

      if (!clerkTenantId) {
        setError(null);
        setTenantId(null);
        setIsLoading(false);
        return;
      }

      setTenantId(clerkTenantId);
      setError(null);
      setIsLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setTenantId(null);
      setIsLoading(false);
    }
  }, [userId, organization, authLoaded, orgLoaded]);

  return {
    userId,
    tenantId,
    isDemoMode,
    organization,
    membership,
    isLoading,
    error,
    isAuthenticated: !!userId,
    isAuthorized: hasOrganizationAccess(organization),
  };
}

/**
 * Hook to check user role within their organization
 */
export function useUserRole() {
  const { membership, isLoaded } = useOrganization();

  const [role, setRole] = useState<UserRole>(null);
  const [permissions, setPermissions] = useState<string[]>([]);

  useEffect(() => {
    if (!isLoaded || !membership) {
      setRole(null);
      setPermissions([]);
      return;
    }

    const userRole = membership.role === "org:admin" ? "admin" : "member";
    setRole(userRole);

    const rolePermissions =
      userRole === "admin"
        ? [
            "read:projects",
            "write:projects",
            "delete:projects",
            "manage:users",
            "manage:documents",
            "view:analytics",
            "manage:settings",
            "manage:billing",
          ]
        : [
            "read:projects",
            "write:projects",
            "manage:documents",
            "view:analytics",
          ];

    setPermissions(rolePermissions);
  }, [membership, isLoaded]);

  return {
    role,
    permissions,
    isAdmin: role === "admin",
    isMember: role === "member",
    hasPermission: (permission: string) => permissions.includes(permission),
  };
}

/**
 * Hook to get service tier from organization metadata
 */
export function useServiceTier() {
  const { organization, isLoaded: orgLoaded } = useOrganization();
  const { user, isLoaded: userLoaded } = useUser();

  const [tier, setTier] = useState<ServiceTier>("free");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!orgLoaded || !userLoaded) {
      setIsLoading(true);
      return;
    }

    try {
      const orgMetadata = organization?.publicMetadata as
        | Record<string, unknown>
        | undefined;
      const orgTier = orgMetadata?.tier as string | undefined;

      if (orgTier && ["free", "pro", "enterprise"].includes(orgTier)) {
        setTier(orgTier as ServiceTier);
        setIsLoading(false);
        return;
      }

      const userMetadata = user?.publicMetadata as
        | Record<string, unknown>
        | undefined;
      const userTier = (userMetadata?.tier as string) || "free";

      if (["free", "pro", "enterprise"].includes(userTier)) {
        setTier(userTier as ServiceTier);
      } else {
        setTier("free");
      }

      setIsLoading(false);
    } catch (error) {
      console.error("Error getting service tier:", error);
      setTier("free");
      setIsLoading(false);
    }
  }, [organization, user, orgLoaded, userLoaded]);

  return {
    tier,
    isLoading,
    isFree: tier === "free",
    isPro: tier === "pro",
    isEnterprise: tier === "enterprise",
  };
}

// =============================================================================
// Constants
// =============================================================================

export const TIER_FEATURES = {
  free: {
    maxProjects: 1,
    maxUsers: 1,
    maxDocuments: 10,
    maxAlerts: 50,
    stakeholderRaci: false,
    apiAccess: false,
    webhooks: false,
    sso: false,
    supportLevel: "email" as const,
    dataRetentionDays: 30,
  },
  pro: {
    maxProjects: 10,
    maxUsers: 5,
    maxDocuments: 100,
    maxAlerts: 500,
    stakeholderRaci: true,
    apiAccess: true,
    webhooks: false,
    sso: false,
    supportLevel: "chat" as const,
    dataRetentionDays: 365,
  },
  enterprise: {
    maxProjects: -1,
    maxUsers: -1,
    maxDocuments: -1,
    maxAlerts: -1,
    stakeholderRaci: true,
    apiAccess: true,
    webhooks: true,
    sso: true,
    supportLevel: "dedicated" as const,
    dataRetentionDays: -1,
  },
} as const;

export type TierFeatures = typeof TIER_FEATURES;
export type TierFeatureKey = keyof (typeof TIER_FEATURES)["free"];

export function hasFeature(
  tier: ServiceTier,
  feature: TierFeatureKey,
): boolean {
  const tierFeatures = TIER_FEATURES[tier];
  const featureValue = tierFeatures[feature];

  if (typeof featureValue === "boolean") {
    return featureValue;
  }

  // For numeric values: -1 means unlimited (enabled), positive means enabled
  // All our tier limits are non-zero, so any number means the feature is available
  if (typeof featureValue === "number") {
    return true;
  }

  return !!featureValue;
}

export function getFeatureLimit(
  tier: ServiceTier,
  feature: TierFeatureKey,
): number {
  const tierFeatures = TIER_FEATURES[tier];
  const featureValue = tierFeatures[feature];

  if (typeof featureValue === "number") {
    return featureValue;
  }

  return 0;
}

// =============================================================================
// Utilities
// =============================================================================

export function createTenantHeaders(tenantId: string): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "X-Tenant-ID": tenantId,
    "X-Requested-With": "XMLHttpRequest",
  };
}

export function addTenantToParams(
  params: Record<string, unknown>,
  tenantId: string,
): Record<string, unknown> {
  return {
    ...params,
    tenant_id: tenantId,
  };
}
