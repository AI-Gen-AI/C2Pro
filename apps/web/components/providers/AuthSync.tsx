"use client";

import React from "react";
import { useAuth, useOrganization, useOrganizationList } from "@clerk/nextjs";
import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { handleAuthErrorStatus } from "@/lib/api/client";
import { useAuthStore } from "@/stores/auth";
import { getTenantIdFromOrganizationMetadata } from "@/lib/clerk-tenant";

interface SignedInOrganizationEffectsProps {
  getToken: () => Promise<string | null>;
  isLoaded: boolean;
  organization: ReturnType<typeof useOrganization>["organization"];
  setAuth: (auth: { token: string | null; tenantId: string | null }) => void;
}

function SignedInOrganizationEffects({
  getToken,
  isLoaded,
  organization,
  setAuth,
}: SignedInOrganizationEffectsProps) {
  const { isLoaded: orgListLoaded, setActive, userMemberships } =
    useOrganizationList({
      userMemberships: {
        infinite: true,
      },
    });
  const organizationMemberships = userMemberships.data ?? [];

  useEffect(() => {
    if (!isLoaded || !orgListLoaded || organization) {
      return;
    }

    if (organizationMemberships.length !== 1) {
      return;
    }

    const [membership] = organizationMemberships;
    void setActive?.({ organization: membership.organization.id });
  }, [isLoaded, orgListLoaded, organization, organizationMemberships, setActive]);

  useEffect(() => {
    if (!isLoaded) return;

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
    organization,
    organizationMemberships.length,
    getToken,
    setAuth,
  ]);

  return null;
}

interface SignedInAuthSyncProps {
  getToken: () => Promise<string | null>;
  isLoaded: boolean;
  queryClient: ReturnType<typeof useQueryClient>;
  setAuth: (auth: { token: string | null; tenantId: string | null }) => void;
  prevOrgId: string | null;
}

function SignedInAuthSync({
  getToken,
  isLoaded,
  queryClient,
  setAuth,
  prevOrgId,
}: SignedInAuthSyncProps) {
  const { organization } = useOrganization();

  useEffect(() => {
    const tenantId = getTenantIdFromOrganizationMetadata(organization);

    if (prevOrgId && tenantId && prevOrgId !== tenantId) {
      queryClient.clear();
    }
  }, [organization, prevOrgId, queryClient]);

  return (
    <SignedInOrganizationEffects
      getToken={getToken}
      isLoaded={isLoaded}
      organization={organization}
      setAuth={setAuth}
    />
  );
}
 
export function AuthSync({ children }: { children: React.ReactNode }) {
  const { getToken, isSignedIn, isLoaded } = useAuth();
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
  }, [isLoaded, isSignedIn, clearAuth]);

  return (
    <>
      {isSignedIn ? (
        <SignedInAuthSync
          getToken={getToken}
          isLoaded={isLoaded}
          queryClient={queryClient}
          setAuth={setAuth}
          prevOrgId={prevOrgId}
        />
      ) : null}
      {children}
    </>
  );
}
