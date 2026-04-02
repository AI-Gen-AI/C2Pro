/**
 * RBAC Components
 *
 * Role-based and tier-based access control components for C2Pro.
 * These components enforce authorization at the UI level.
 *
 * @module components/auth/rbac-components
 */

"use client";

import { ReactNode } from "react";
import {
  useTenantContext,
  useServiceTier,
  useUserRole,
  ServiceTier,
} from "@/lib/clerk-tenant";
import { Loader2, Lock, Sparkles, Building2 } from "lucide-react";

// =============================================================================
// FeatureGate - Tier-based feature gating
// =============================================================================

interface FeatureGateProps {
  children: ReactNode;
  requiredTier?: ServiceTier;
  featureName?: string;
  showUpgrade?: boolean;
  fallback?: ReactNode;
}

/**
 * Gates content based on service tier
 *
 * @example
 * <FeatureGate requiredTier="pro" featureName="RACI Matrix">
 *   <RACIMatrix />
 * </FeatureGate>
 */
export function FeatureGate({
  children,
  requiredTier = "free",
  featureName = "This feature",
  showUpgrade = true,
  fallback,
}: FeatureGateProps) {
  const { tier, isLoading } = useServiceTier();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-4">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const tierLevels = { free: 1, pro: 2, enterprise: 3 };
  const hasAccess = tierLevels[tier] >= tierLevels[requiredTier];

  if (!hasAccess) {
    if (fallback) {
      return <>{fallback}</>;
    }

    if (showUpgrade) {
      return (
        <div className="p-6 bg-gradient-to-r from-cyan-500/10 to-blue-500/10 border border-cyan-500/20 rounded-lg">
          <div className="flex items-start gap-4">
            <div className="p-2 bg-cyan-500/20 rounded-lg shrink-0">
              <Sparkles className="h-5 w-5 text-cyan-400" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-white mb-1">
                {featureName} requires{" "}
                {requiredTier.charAt(0).toUpperCase() + requiredTier.slice(1)}{" "}
                Plan
              </h3>
              <p className="text-sm text-slate-400 mb-4">
                Upgrade your plan to unlock this feature and get access to
                advanced capabilities.
              </p>
              <button
                onClick={() => (window.location.href = "/settings/billing")}
                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white text-sm font-medium rounded-lg transition-colors"
              >
                Upgrade Now
              </button>
            </div>
          </div>
        </div>
      );
    }

    return null;
  }

  return <>{children}</>;
}

// =============================================================================
// AdminOnly - Role-based admin access
// =============================================================================

interface AdminOnlyProps {
  children: ReactNode;
  fallback?: ReactNode;
  showMessage?: boolean;
}

/**
 * Only renders content for organization admins
 *
 * @example
 * <AdminOnly>
 *   <UserManagementPanel />
 * </AdminOnly>
 */
export function AdminOnly({
  children,
  fallback,
  showMessage = true,
}: AdminOnlyProps) {
  const { isAdmin, role } = useUserRole();

  if (role === null) {
    return (
      <div className="flex items-center justify-center p-4">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!isAdmin) {
    if (fallback) {
      return <>{fallback}</>;
    }

    if (showMessage) {
      return (
        <div className="p-6 bg-red-500/10 border border-red-500/20 rounded-lg">
          <div className="flex items-center gap-3">
            <Lock className="h-5 w-5 text-red-400 shrink-0" />
            <div>
              <p className="text-red-400 font-medium">Admin access required</p>
              <p className="text-sm text-red-400/70 mt-1">
                Contact your organization admin for access.
              </p>
            </div>
          </div>
        </div>
      );
    }

    return null;
  }

  return <>{children}</>;
}

// =============================================================================
// TenantRequired - Organization/tenant context required
// =============================================================================

interface TenantRequiredProps {
  children: ReactNode;
}

/**
 * Requires user to have selected a valid tenant/organization
 *
 * @example
 * <TenantRequired>
 *   <ProjectsList />
 * </TenantRequired>
 */
export function TenantRequired({ children }: TenantRequiredProps) {
  const { isAuthorized, isLoading, error } = useTenantContext();

  if (isLoading) {
    return (
      <div className="min-h-[400px] flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-cyan-500 mx-auto mb-4" />
          <p className="text-sm text-muted-foreground">
            Loading organization...
          </p>
        </div>
      </div>
    );
  }

  if (!isAuthorized) {
    return (
      <div className="min-h-[400px] flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="p-3 bg-slate-800 rounded-full w-fit mx-auto mb-4">
            <Building2 className="h-8 w-8 text-slate-400" />
          </div>
          <h2 className="text-xl font-semibold text-white mb-2">
            Organization Required
          </h2>
          <p className="text-slate-400 mb-6">
            {error ||
              "Please select or create an organization to access this content."}
          </p>
          <button
            onClick={() => (window.location.href = "/onboarding")}
            className="px-6 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg transition-colors"
          >
            Set Up Organization
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

// =============================================================================
// DemoModeGuard - Prevents write operations in demo mode
// =============================================================================

interface DemoModeGuardProps {
  children: ReactNode;
  action: string;
  onDemoMode?: () => void;
}

/**
 * Prevents write operations when in demo mode
 *
 * @example
 * <DemoModeGuard action="create projects">
 *   <CreateProjectButton />
 * </DemoModeGuard>
 */
export function DemoModeGuard({
  children,
  action,
  onDemoMode,
}: DemoModeGuardProps) {
  const { isDemoMode } = useTenantContext();

  if (isDemoMode) {
    onDemoMode?.();
    return (
      <div className="p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
        <p className="text-yellow-400 text-sm font-medium">
          Cannot {action} in demo mode. Switch to your production workspace to
          make changes.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}

// =============================================================================
// PermissionGate - Fine-grained permission check
// =============================================================================

interface PermissionGateProps {
  children: ReactNode;
  permission: string;
  fallback?: ReactNode;
}

/**
 * Gates content based on specific permission
 *
 * @example
 * <PermissionGate permission="manage:users">
 *   <UserManagement />
 * </PermissionGate>
 */
export function PermissionGate({
  children,
  permission,
  fallback,
}: PermissionGateProps) {
  const { hasPermission, role } = useUserRole();

  if (role === null) {
    return (
      <div className="flex items-center justify-center p-4">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!hasPermission(permission)) {
    return fallback ? <>{fallback}</> : null;
  }

  return <>{children}</>;
}

// =============================================================================
// Export all
// =============================================================================

export { Loader2, Lock, Sparkles, Building2 };
