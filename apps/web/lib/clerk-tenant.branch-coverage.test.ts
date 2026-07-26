/**
 * Test Suite ID: TS-QA-337-CLERK-TENANT-BRANCH-COV
 * Branch coverage tests for clerk-tenant hooks and helpers
 */
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  hasFeature,
  getFeatureLimit,
  createTenantHeaders,
  addTenantToParams,
} from "./clerk-tenant";

const { useAuthMock, useUserMock, useOrganizationMock } = vi.hoisted(() => ({
  useAuthMock: vi.fn(),
  useUserMock: vi.fn(),
  useOrganizationMock: vi.fn(),
}));

vi.mock("@clerk/nextjs", () => ({
  useAuth: useAuthMock,
  useUser: useUserMock,
  useOrganization: useOrganizationMock,
}));

import { useTenantContext, useUserRole, useServiceTier } from "./clerk-tenant";

describe("clerk-tenant branch coverage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("hasFeature", () => {
    it("returns boolean feature values directly", () => {
      expect(hasFeature("free", "stakeholderRaci")).toBe(false);
      expect(hasFeature("pro", "stakeholderRaci")).toBe(true);
    });

    it("returns true for numeric features (non-zero = available)", () => {
      expect(hasFeature("free", "maxProjects")).toBe(true);
      expect(hasFeature("enterprise", "maxProjects")).toBe(true);
    });

    it("returns truthy for string features", () => {
      expect(hasFeature("free", "supportLevel")).toBe(true);
      expect(hasFeature("pro", "supportLevel")).toBe(true);
    });
  });

  describe("getFeatureLimit", () => {
    it("returns numeric limit for number features", () => {
      expect(getFeatureLimit("free", "maxProjects")).toBe(1);
      expect(getFeatureLimit("enterprise", "maxProjects")).toBe(-1);
    });

    it("returns 0 for non-number features", () => {
      expect(getFeatureLimit("free", "supportLevel")).toBe(0);
      expect(getFeatureLimit("free", "stakeholderRaci")).toBe(0);
    });
  });

  describe("createTenantHeaders", () => {
    it("creates headers with X-Tenant-ID", () => {
      const headers = createTenantHeaders("tenant-xyz");
      expect(headers["X-Tenant-ID"]).toBe("tenant-xyz");
      expect(headers["Content-Type"]).toBe("application/json");
      expect(headers["X-Requested-With"]).toBe("XMLHttpRequest");
    });
  });

  describe("addTenantToParams", () => {
    it("spreads existing params and adds tenant_id", () => {
      const result = addTenantToParams({ page: 1 }, "tenant-xyz");
      expect(result).toEqual({ page: 1, tenant_id: "tenant-xyz" });
    });
  });

  describe("useTenantContext hook", () => {
    it("sets loading true when auth or org not loaded", async () => {
      useAuthMock.mockReturnValue({ userId: null, isLoaded: false });
      useOrganizationMock.mockReturnValue({
        organization: null,
        membership: null,
        isLoaded: false,
      });

      const { result } = renderHook(() => useTenantContext());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(true);
      });
    });

    it("returns null tenantId when userId is absent", async () => {
      useAuthMock.mockReturnValue({ userId: null, isLoaded: true });
      useOrganizationMock.mockReturnValue({
        organization: { publicMetadata: { tenant_id: "tenant-abc" } },
        membership: null,
        isLoaded: true,
      });

      const { result } = renderHook(() => useTenantContext());

      await waitFor(() => {
        expect(result.current.tenantId).toBeNull();
        expect(result.current.isAuthenticated).toBe(false);
      });
    });

    it("returns null tenantId when organization is absent", async () => {
      useAuthMock.mockReturnValue({ userId: "user_123", isLoaded: true });
      useOrganizationMock.mockReturnValue({
        organization: null,
        membership: null,
        isLoaded: true,
      });

      const { result } = renderHook(() => useTenantContext());

      await waitFor(() => {
        expect(result.current.tenantId).toBeNull();
        expect(result.current.isAuthorized).toBe(false);
      });
    });

    it("returns null tenantId when metadata has no tenant_id", async () => {
      useAuthMock.mockReturnValue({ userId: "user_123", isLoaded: true });
      useOrganizationMock.mockReturnValue({
        organization: { publicMetadata: { is_demo: false } },
        membership: { role: "org:admin" },
        isLoaded: true,
      });

      const { result } = renderHook(() => useTenantContext());

      await waitFor(() => {
        expect(result.current.tenantId).toBeNull();
        expect(result.current.error).toBeNull();
      });
    });

    it("detects demo mode from organization metadata", async () => {
      useAuthMock.mockReturnValue({ userId: "user_123", isLoaded: true });
      useOrganizationMock.mockReturnValue({
        organization: {
          publicMetadata: { tenant_id: "tenant-demo", is_demo: true },
        },
        membership: { role: "org:member" },
        isLoaded: true,
      });

      const { result } = renderHook(() => useTenantContext());

      await waitFor(() => {
        expect(result.current.isDemoMode).toBe(true);
        expect(result.current.tenantId).toBe("tenant-demo");
      });
    });
  });

  describe("useUserRole hook", () => {
    it("returns admin role and full permissions for org:admin", async () => {
      useOrganizationMock.mockReturnValue({
        membership: { role: "org:admin" },
        isLoaded: true,
      });

      const { result } = renderHook(() => useUserRole());

      await waitFor(() => {
        expect(result.current.role).toBe("admin");
        expect(result.current.isAdmin).toBe(true);
        expect(result.current.permissions).toContain("manage:users");
      });
    });

    it("returns member role and limited permissions for org:member", async () => {
      useOrganizationMock.mockReturnValue({
        membership: { role: "org:member" },
        isLoaded: true,
      });

      const { result } = renderHook(() => useUserRole());

      await waitFor(() => {
        expect(result.current.role).toBe("member");
        expect(result.current.isMember).toBe(true);
        expect(result.current.permissions).not.toContain("manage:users");
        expect(result.current.permissions).toContain("read:projects");
      });
    });

    it("returns null role when membership is absent", async () => {
      useOrganizationMock.mockReturnValue({
        membership: null,
        isLoaded: true,
      });

      const { result } = renderHook(() => useUserRole());

      await waitFor(() => {
        expect(result.current.role).toBeNull();
        expect(result.current.permissions).toEqual([]);
      });
    });

    it("hasPermission checks correctly", async () => {
      useOrganizationMock.mockReturnValue({
        membership: { role: "org:admin" },
        isLoaded: true,
      });

      const { result } = renderHook(() => useUserRole());

      await waitFor(() => {
        expect(result.current.hasPermission("manage:users")).toBe(true);
        expect(result.current.hasPermission("nonexistent")).toBe(false);
      });
    });
  });

  describe("useServiceTier hook", () => {
    it("uses org tier when available and valid", async () => {
      useOrganizationMock.mockReturnValue({
        organization: { publicMetadata: { tier: "enterprise" } },
        isLoaded: true,
      });
      useUserMock.mockReturnValue({
        user: { publicMetadata: {} },
        isLoaded: true,
      });

      const { result } = renderHook(() => useServiceTier());

      await waitFor(() => {
        expect(result.current.tier).toBe("enterprise");
        expect(result.current.isEnterprise).toBe(true);
      });
    });

    it("falls back to user tier when org tier is invalid", async () => {
      useOrganizationMock.mockReturnValue({
        organization: { publicMetadata: { tier: "invalid-tier" } },
        isLoaded: true,
      });
      useUserMock.mockReturnValue({
        user: { publicMetadata: { tier: "pro" } },
        isLoaded: true,
      });

      const { result } = renderHook(() => useServiceTier());

      await waitFor(() => {
        expect(result.current.tier).toBe("pro");
        expect(result.current.isPro).toBe(true);
      });
    });

    it("defaults to free when both tiers are invalid", async () => {
      useOrganizationMock.mockReturnValue({
        organization: { publicMetadata: { tier: "invalid" } },
        isLoaded: true,
      });
      useUserMock.mockReturnValue({
        user: { publicMetadata: { tier: "ultra" } },
        isLoaded: true,
      });

      const { result } = renderHook(() => useServiceTier());

      await waitFor(() => {
        expect(result.current.tier).toBe("free");
        expect(result.current.isFree).toBe(true);
      });
    });

    it("defaults to free when user tier is missing", async () => {
      useOrganizationMock.mockReturnValue({
        organization: { publicMetadata: {} },
        isLoaded: true,
      });
      useUserMock.mockReturnValue({
        user: { publicMetadata: {} },
        isLoaded: true,
      });

      const { result } = renderHook(() => useServiceTier());

      await waitFor(() => {
        expect(result.current.tier).toBe("free");
      });
    });

    it("sets loading true when org or user not loaded", async () => {
      useOrganizationMock.mockReturnValue({
        organization: null,
        isLoaded: false,
      });
      useUserMock.mockReturnValue({
        user: null,
        isLoaded: false,
      });

      const { result } = renderHook(() => useServiceTier());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(true);
      });
    });

    it("defaults to free when org tier is invalid and user tier is also invalid", async () => {
      useOrganizationMock.mockReturnValue({
        organization: { publicMetadata: { tier: "invalid_tier" } },
        isLoaded: true,
      });
      useUserMock.mockReturnValue({
        user: { publicMetadata: { tier: "also_invalid" } },
        isLoaded: true,
      });

      const { result } = renderHook(() => useServiceTier());

      await waitFor(() => {
        expect(result.current.tier).toBe("free");
        expect(result.current.isFree).toBe(true);
      });
    });
  });
});
