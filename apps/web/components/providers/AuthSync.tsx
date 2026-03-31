"use client";

import React from "react";
import { useAuth, useOrganization, useOrganizationList } from "@clerk/nextjs";
import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { handleAuthErrorStatus } from "@/lib/api/client";
import { useAuthStore } from "@/stores/auth";
import { getTenantIdFromOrganizationMetadata } from "@/lib/clerk-tenant";

export function AuthSync({ children }: { children: React.ReactNode }) {
  const { getToken, isSignedIn, isLoaded } = useAuth();
  // Only use organization when signed in to avoid Clerk warnings
  const { organization } = useOrganization();
  const { isLoaded: orgListLoaded, setActive, userMemberships } =
    useOrganizationList({
      userMemberships: {
        infinite: true,
      },
    });
  const queryClient = useQueryClient();
  const setAuth = useAuthStore((s) => s.setAuth);
  const clearAuth = useAuthStore((s) => s.clear);
  const prevOrgId = useAuthStore((s) => s.tenantId);
  const organizationMemberships = userMemberships.data ?? [];

  useEffect(() => {
    if (!isLoaded || !orgListLoaded || !isSignedIn || organization) {
      return;
    }

    if (organizationMemberships.length !== 1) {
      return;
    }

    const [membership] = organizationMemberships;
    void setActive?.({ organization: membership.organization.id });
  }, [
    isLoaded,
    orgListLoaded,
    isSignedIn,
    organization,
    organizationMemberships,
    setActive,
  ]);

  useEffect(() => {
    // Wait for Clerk to load before doing anything
    if (!isLoaded) return;

    if (!isSignedIn) {
      clearAuth();
      return;
    }

    if (!organization && organizationMemberships.length === 1) {
      return;
    }

    const sync = async () => {
      try {
        const token = await getToken();
        if (!token) {
          handleAuthErrorStatus(401);
          return;
        }
        const tenantId = getTenantIdFromOrganizationMetadata(organization);
        setAuth({ token, tenantId });
      } catch (error) {
        console.error("AuthSync: Failed to get token", error);
        handleAuthErrorStatus(401);
      }
    };

    void sync();
    const interval = setInterval(sync, 50_000);
    return () => clearInterval(interval);
  }, [
    isLoaded,
    isSignedIn,
    organization,
    organizationMemberships.length,
    getToken,
    setAuth,
    clearAuth,
  ]);

  useEffect(() => {
    const tenantId = getTenantIdFromOrganizationMetadata(organization);

    if (prevOrgId && tenantId && prevOrgId !== tenantId) {
      queryClient.clear();
    }
  }, [organization, prevOrgId, queryClient]);

  return <>{children}</>;
}
