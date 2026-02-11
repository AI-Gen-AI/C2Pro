"use client";

import { createContext, useContext, type ReactNode, useMemo } from "react";
import { useAuth as useClerkAuth, useOrganization, useUser } from "@clerk/nextjs";
import { useAuthStore } from "@/stores/auth";

interface AuthContextType {
  user: {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
    role: string | null;
  } | null;
  tenant: {
    id: string;
    name: string;
  } | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  userRole: string | null;
  logout: () => Promise<void>;
  login: () => Promise<void>;
  register: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const { isLoaded, isSignedIn, signOut } = useClerkAuth();
  const { user } = useUser();
  const { organization } = useOrganization();
  const accessToken = useAuthStore((s) => s.token);

  const value = useMemo<AuthContextType>(() => {
    const role =
      (user?.publicMetadata?.role as string | undefined) ??
      (user?.unsafeMetadata?.role as string | undefined) ??
      null;

    return {
      user: user
        ? {
            id: user.id,
            email: user.primaryEmailAddress?.emailAddress ?? "",
            first_name: user.firstName ?? "",
            last_name: user.lastName ?? "",
            role,
          }
        : null,
      tenant: organization
        ? {
            id: organization.id,
            name: organization.name,
          }
        : null,
      accessToken,
      isAuthenticated: !!isSignedIn,
      isLoading: !isLoaded,
      userRole: role,
      logout: () => signOut(),
      login: async () => {
        throw new Error("Use Clerk SignIn component for login.");
      },
      register: async () => {
        throw new Error("Use Clerk SignUp component for registration.");
      },
    };
  }, [accessToken, isLoaded, isSignedIn, organization, signOut, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
