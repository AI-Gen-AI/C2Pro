"use client";

import React from "react";
import { useAuth, useOrganization } from "@clerk/nextjs";
import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { handleAuthErrorStatus } from "@/lib/api/client";
import { useAuthStore } from "@/stores/auth";
import { getTenantIdFromOrganizationMetadata } from "@/lib/clerk-tenant";

export function AuthSync({ children }: { children: React.ReactNode }) {
  const { getToken, isSignedIn, isLoaded } = useAuth();
  // Only use organization when signed in to avoid Clerk warnings
  const { organization } = useOrganization();
  const queryClient = useQueryClient();
  const setAuth = useAuthStore((s) => s.setAuth);
  const clearAuth = useAuthStore((s) => s.clear);
  const prevOrgId = useAuthStore((s) => s.tenantId);

  useEffect(() => {
    // Wait for Clerk to load before doing anything
    if (!isLoaded) return;

    if (!isSignedIn) {
      clearAuth();
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

    sync();
    const interval = setInterval(sync, 50_000);
    return () => clearInterval(interval);
  }, [isLoaded, isSignedIn, organization, getToken, setAuth, clearAuth]);

  useEffect(() => {
    const tenantId = getTenantIdFromOrganizationMetadata(organization);

    if (prevOrgId && tenantId && prevOrgId !== tenantId) {
      queryClient.clear();
    }
  }, [organization, prevOrgId, queryClient]);

  return <>{children}</>;
}
