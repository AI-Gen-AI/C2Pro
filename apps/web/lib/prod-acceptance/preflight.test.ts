import { describe, expect, it } from "vitest";

import {
  ProdPreflightError,
  type ProdPreflightFailureCode,
  assertProdPreflight,
  requireProdAcceptanceEnv,
  requireProductionOrigin,
  syntheticProjectName,
} from "./preflight";

const TENANT = "11111111-1111-4111-8111-111111111111";
const ORG = "org_prod_acceptance";
const BACKEND = "a".repeat(40);
const FRONTEND = "b".repeat(40);
const FIXTURE = "c".repeat(64);

function valid(overrides: Record<string, unknown> = {}) {
  return {
    baseUrl: "https://c2pro.io",
    runId: "20260927T220000Z",
    expectedTenantId: TENANT,
    activeTenantId: TENANT,
    expectedOrganizationId: ORG,
    activeOrganizationId: ORG,
    tenantMarkedSynthetic: true,
    expectedBackendSha: BACKEND,
    observedBackendSha: BACKEND,
    expectedFrontendSha: FRONTEND,
    observedFrontendSha: FRONTEND,
    expectedFixtureSha256: FIXTURE,
    observedFixtureSha256: FIXTURE,
    ...overrides,
  };
}

function expectCode(
  overrides: Record<string, unknown>,
  code: ProdPreflightFailureCode,
) {
  expect(() => assertProdPreflight(valid(overrides))).toThrowError(
    expect.objectContaining<Partial<ProdPreflightError>>({ code }),
  );
}

describe("production acceptance preflight", () => {
  it("accepts only the canonical production hosts over HTTPS", () => {
    expect(() => assertProdPreflight(valid())).not.toThrow();
    expect(requireProductionOrigin("https://c2pro.io/sign-in")).toBe("https://c2pro.io");
    expect(requireProductionOrigin("https://www.c2pro.io/projects")).toBe("https://www.c2pro.io");
    expectCode({ baseUrl: "http://c2pro.io" }, "NON_PRODUCTION_HOST");
    expectCode({ baseUrl: "https://preview.example.com" }, "NON_PRODUCTION_HOST");
    expect(() => requireProductionOrigin("https://preview.example.com")).toThrowError(
      expect.objectContaining({ code: "NON_PRODUCTION_HOST" }),
    );
  });

  it("fails closed before mutation on tenant or organization mismatch", () => {
    expectCode({ activeTenantId: "22222222-2222-4222-8222-222222222222" }, "WRONG_TENANT");
    expectCode({ activeOrganizationId: "org_other" }, "WRONG_ORGANIZATION");
    expectCode({ tenantMarkedSynthetic: false }, "TENANT_NOT_MARKED_SYNTHETIC");
  });

  it("fails closed on backend or frontend deployment skew", () => {
    expectCode({ observedBackendSha: "d".repeat(40) }, "BACKEND_DEPLOYMENT_MISMATCH");
    expectCode({ observedFrontendSha: "e".repeat(40) }, "FRONTEND_DEPLOYMENT_MISMATCH");
  });

  it("fails closed on fixture hash mismatch", () => {
    expectCode({ observedFixtureSha256: "f".repeat(64) }, "FIXTURE_HASH_MISMATCH");
  });

  it("creates only deterministic synthetic project names", () => {
    expect(syntheticProjectName("20260927T220000Z")).toBe("ACCEPT-706-20260927T220000Z");
    expect(() => syntheticProjectName("bad")).toThrowError(
      expect.objectContaining({ code: "INVALID_RUN_ID" }),
    );
  });

  it("reports only missing environment variable names, never existing values", () => {
    const existingValue = `present-${Date.now()}`;
    expect(() =>
      requireProdAcceptanceEnv(
        { PROD_ACCEPTANCE_USER: existingValue },
        ["PROD_ACCEPTANCE_USER", "PROD_ACCEPTANCE_PASSWORD"],
      ),
    ).toThrow("PROD_ACCEPTANCE_MISSING_ENV:PROD_ACCEPTANCE_PASSWORD");

    try {
      requireProdAcceptanceEnv(
        { PROD_ACCEPTANCE_USER: existingValue },
        ["PROD_ACCEPTANCE_USER", "PROD_ACCEPTANCE_PASSWORD"],
      );
    } catch (error) {
      expect(String(error)).not.toContain(existingValue);
    }
  });
});
