/**
 * Authentication API Client
 * Handles all authentication-related API calls
 */

import type { AxiosError } from 'axios';
import { apiClient } from '@/lib/api/client';

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export interface RegisterRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  company_name: string;
  accept_terms: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface UserResponse {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
  tenant_id: string;
  created_at: string;
  avatar_url?: string;
  phone?: string;
}

export interface TenantResponse {
  id: string;
  name: string;
  subscription_plan: string;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginResponse extends TokenResponse {
  user: UserResponse;
  tenant: TenantResponse;
}

export interface RegisterResponse extends TokenResponse {
  user: UserResponse;
  tenant: TenantResponse;
}

export interface MeResponse {
  user: UserResponse;
  tenant: TenantResponse;
}

export interface ApiError {
  detail: string;
}

class AuthApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private getErrorMessage(error: unknown, fallback: string) {
    const axiosError = error as AxiosError<ApiError>;
    return axiosError?.response?.data?.detail || fallback;
  }

  /**
   * Register a new user and company
   */
  async register(data: RegisterRequest): Promise<RegisterResponse> {
    try {
      const response = await apiClient.post<RegisterResponse>(
        `${this.baseUrl}/auth/register`,
        data
      );
      return response.data;
    } catch (error) {
      throw new Error(this.getErrorMessage(error, 'Registration failed'));
    }
  }

  /**
   * Login with email and password
   */
  async login(data: LoginRequest): Promise<LoginResponse> {
    try {
      const response = await apiClient.post<LoginResponse>(
        `${this.baseUrl}/auth/login`,
        data
      );
      return response.data;
    } catch (error) {
      throw new Error(this.getErrorMessage(error, 'Login failed'));
    }
  }

  /**
   * Refresh access token using refresh token
   */
  async refreshToken(refreshToken: string): Promise<TokenResponse> {
    try {
      const response = await apiClient.post<TokenResponse>(
        `${this.baseUrl}/auth/refresh`,
        { refresh_token: refreshToken }
      );
      return response.data;
    } catch (error) {
      throw new Error(this.getErrorMessage(error, 'Token refresh failed'));
    }
  }

  /**
   * Get current user info
   */
  async getMe(accessToken: string): Promise<MeResponse> {
    try {
      const response = await apiClient.get<MeResponse>(`${this.baseUrl}/auth/me`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      return response.data;
    } catch (error) {
      throw new Error(this.getErrorMessage(error, 'Failed to get user info'));
    }
  }

  /**
   * Logout (client-side token removal)
   */
  async logout(accessToken: string): Promise<void> {
    try {
      await apiClient.post(
        `${this.baseUrl}/auth/logout`,
        {},
        {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        }
      );
    } catch (error) {
      // Logout endpoint is mainly for logging - don't fail if it errors
      console.error('Logout API call failed:', error);
    }
  }
}

export const authApi = new AuthApiClient();
