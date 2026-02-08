/**
 * Authentication Context
 * Manages user authentication state and provides auth methods throughout the app
 */

'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import {
  authApi,
  LoginRequest,
  RegisterRequest,
  UserResponse,
  TenantResponse,
} from '@/lib/api/auth';

interface AuthContextType {
  user: UserResponse | null;
  tenant: TenantResponse | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  userRole?: 'user' | 'tenant_admin' | 'c2pro_admin';
  login: (credentials: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
  refreshUserData: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const ACCESS_TOKEN_KEY = 'c2pro_access_token';
const REFRESH_TOKEN_KEY = 'c2pro_refresh_token';
const USER_DATA_KEY = 'c2pro_user_data';
const TENANT_DATA_KEY = 'c2pro_tenant_data';

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [tenant, setTenant] = useState<TenantResponse | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  /**
   * Load user data from localStorage on mount
   */
  useEffect(() => {
    const loadStoredAuth = () => {
      try {
        const storedToken = localStorage.getItem(ACCESS_TOKEN_KEY);
        const storedUser = localStorage.getItem(USER_DATA_KEY);
        const storedTenant = localStorage.getItem(TENANT_DATA_KEY);

        if (storedToken && storedUser && storedTenant) {
          setAccessToken(storedToken);
          setUser(JSON.parse(storedUser));
          setTenant(JSON.parse(storedTenant));
        }
      } catch (error) {
        console.error('Failed to load stored auth data:', error);
        clearStoredAuth();
      } finally {
        setIsLoading(false);
      }
    };

    loadStoredAuth();
  }, []);

  /**
   * Auto-refresh token before expiration
   * JWT tokens expire after 24 hours, refresh 1 hour before
   */
  useEffect(() => {
    if (!accessToken) return;

    const refreshInterval = setInterval(async () => {
      await refreshTokenSilently();
    }, 23 * 60 * 60 * 1000); // 23 hours

    return () => clearInterval(refreshInterval);
  }, [accessToken]);

  /**
   * Save auth data to localStorage
   */
  const saveAuthData = useCallback(
    (
      newAccessToken: string,
      newRefreshToken: string,
      newUser: UserResponse,
      newTenant: TenantResponse
    ) => {
      try {
        localStorage.setItem(ACCESS_TOKEN_KEY, newAccessToken);
        localStorage.setItem(REFRESH_TOKEN_KEY, newRefreshToken);
        localStorage.setItem(USER_DATA_KEY, JSON.stringify(newUser));
        localStorage.setItem(TENANT_DATA_KEY, JSON.stringify(newTenant));

        setAccessToken(newAccessToken);
        setUser(newUser);
        setTenant(newTenant);
      } catch (error) {
        console.error('Failed to save auth data:', error);
        throw new Error('Failed to save authentication data');
      }
    },
    []
  );

  /**
   * Clear all auth data
   */
  const clearStoredAuth = useCallback(() => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(USER_DATA_KEY);
    localStorage.removeItem(TENANT_DATA_KEY);

    setAccessToken(null);
    setUser(null);
    setTenant(null);
  }, []);

  /**
   * Refresh token silently in background
   */
  const refreshTokenSilently = useCallback(async () => {
    try {
      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
      if (!refreshToken) {
        throw new Error('No refresh token available');
      }

      const response = await authApi.refreshToken(refreshToken);

      // Update only the access token
      localStorage.setItem(ACCESS_TOKEN_KEY, response.access_token);
      localStorage.setItem(REFRESH_TOKEN_KEY, response.refresh_token);
      setAccessToken(response.access_token);

      console.log('Token refreshed successfully');
    } catch (error) {
      console.error('Failed to refresh token:', error);
      // If refresh fails, logout user
      logout();
    }
  }, []);

  /**
   * Refresh user data from API
   */
  const refreshUserData = useCallback(async () => {
    if (!accessToken) return;

    try {
      const response = await authApi.getMe(accessToken);

      localStorage.setItem(USER_DATA_KEY, JSON.stringify(response.user));
      localStorage.setItem(TENANT_DATA_KEY, JSON.stringify(response.tenant));

      setUser(response.user);
      setTenant(response.tenant);
    } catch (error) {
      console.error('Failed to refresh user data:', error);
      // If fetching user data fails, token might be invalid
      logout();
    }
  }, [accessToken]);

  /**
   * Login user
   */
  const login = useCallback(
    async (credentials: LoginRequest) => {
      try {
        setIsLoading(true);
        const response = await authApi.login(credentials);

        saveAuthData(
          response.access_token,
          response.refresh_token,
          response.user,
          response.tenant
        );

        // Redirect to dashboard
        router.push('/');
      } catch (error) {
        console.error('Login failed:', error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [router, saveAuthData]
  );

  /**
   * Register new user
   */
  const register = useCallback(
    async (data: RegisterRequest) => {
      try {
        setIsLoading(true);
        const response = await authApi.register(data);

        saveAuthData(
          response.access_token,
          response.refresh_token,
          response.user,
          response.tenant
        );

        // Redirect to dashboard
        router.push('/');
      } catch (error) {
        console.error('Registration failed:', error);
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [router, saveAuthData]
  );

  /**
   * Logout user
   */
  const logout = useCallback(() => {
    // Call logout API (for logging purposes)
    if (accessToken) {
      authApi.logout(accessToken).catch(console.error);
    }

    clearStoredAuth();
    router.push('/login');
  }, [accessToken, clearStoredAuth, router]);

  const value = {
    user,
    tenant,
    accessToken,
    isAuthenticated: !!user && !!accessToken,
    isLoading,
    userRole: (user?.role as 'user' | 'tenant_admin' | 'c2pro_admin') || 'user',
    login,
    register,
    logout,
    refreshUserData,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Hook to use auth context
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
