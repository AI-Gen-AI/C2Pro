import { describe, expect, it } from "vitest";
import {
  getTenantIdFromOrganizationMetadata,
  hasOrganizationAccess,
  isDemoOrganization,
} from "./clerk-tenant";

describe("clerk-tenant helpers", () => {
  it("extracts tenant ids only from non-empty string metadata", () => {
    expect(
      getTenantIdFromOrganizationMetadata({
        publicMetadata: { tenant_id: "tenant-123" },
      } as never),
    ).toBe("tenant-123");
    expect(
      getTenantIdFromOrganizationMetadata({
        publicMetadata: { tenant_id: "" },
      } as never),
    ).toBeNull();
  });

  it("detects demo organizations from Clerk metadata", () => {
    expect(
      isDemoOrganization({ publicMetadata: { is_demo: true } } as never),
    ).toBe(true);
    expect(
      isDemoOrganization({ publicMetadata: { is_demo: false } } as never),
    ).toBe(false);
  });

  it("treats an active organization as sufficient authorization context", () => {
    expect(hasOrganizationAccess({ id: "org_123" } as never)).toBe(true);
    expect(hasOrganizationAccess(null as never)).toBe(false);
  });
});
