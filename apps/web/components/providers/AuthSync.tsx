"use client";

import React from "react";
import { useAuth, useOrganization } from "@clerk/nextjs";
import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/auth";

export function AuthSync({ children }: { children: React.ReactNode }) {
  const { getToken, isSignedIn } = useAuth();
  const { organization } = useOrganization();
  const queryClient = useQueryClient();
  const setAuth = useAuthStore((s) => s.setAuth);
  const clearAuth = useAuthStore((s) => s.clear);
  const prevOrgId = useAuthStore((s) => s.tenantId);

  useEffect(() => {
    if (!isSignedIn) {
      clearAuth();
      return;
    }

    const sync = async () => {
      const token = await getToken();
      const tenantId = organization?.id ?? null;
      setAuth({ token, tenantId });
    };

    sync();
    const interval = setInterval(sync, 50_000);
    return () => clearInterval(interval);
  }, [isSignedIn, organization?.id, getToken, setAuth, clearAuth]);

  useEffect(() => {
    if (prevOrgId && organization?.id && prevOrgId !== organization.id) {
      queryClient.clear();
    }
  }, [organization?.id, prevOrgId, queryClient]);

  return <>{children}</>;
}
