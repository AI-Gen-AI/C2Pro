import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

const COMMIT_SHA_RE = /^[0-9a-f]{40}$/;
const FIXTURE_SHA_RE = /^[0-9a-f]{64}$/;
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const RUN_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{7,63}$/;
const PRODUCTION_HOSTS = new Set(["c2pro.io", "www.c2pro.io"]);
const PRODUCTION_API_HOSTS = new Set(["c2pro-production.up.railway.app"]);

export type ProdPreflightFailureCode =
  | "INVALID_BASE_URL"
  | "NON_PRODUCTION_HOST"
  | "NON_PRODUCTION_API_HOST"
  | "INVALID_RUN_ID"
  | "INVALID_TENANT_ID"
  | "WRONG_TENANT"
  | "WRONG_ORGANIZATION"
  | "TENANT_NOT_MARKED_SYNTHETIC"
  | "INVALID_BACKEND_SHA"
  | "INVALID_FRONTEND_SHA"
  | "BACKEND_DEPLOYMENT_MISMATCH"
  | "FRONTEND_DEPLOYMENT_MISMATCH"
  | "INVALID_FIXTURE_SHA"
  | "FIXTURE_HASH_MISMATCH";

export class ProdPreflightError extends Error {
  constructor(public readonly code: ProdPreflightFailureCode) {
    super(`PROD_ACCEPTANCE_PREFLIGHT_FAILED:${code}`);
    this.name = "ProdPreflightError";
  }
}

export interface ProdPreflightContract {
  baseUrl: string;
  runId: string;
  expectedTenantId: string;
  activeTenantId: string | null;
  expectedOrganizationId: string;
  activeOrganizationId: string | null;
  tenantMarkedSynthetic: boolean;
  expectedBackendSha: string;
  observedBackendSha: string;
  expectedFrontendSha: string;
  observedFrontendSha: string;
  expectedFixtureSha256: string;
  observedFixtureSha256: string;
}

function requireCommit(value: string, code: "INVALID_BACKEND_SHA" | "INVALID_FRONTEND_SHA"): void {
  if (!COMMIT_SHA_RE.test(value)) throw new ProdPreflightError(code);
}

export function syntheticProjectName(runId: string): string {
  if (!RUN_ID_RE.test(runId)) throw new ProdPreflightError("INVALID_RUN_ID");
  return `ACCEPT-706-${runId}`;
}

export function sha256File(path: string): string {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

export function requireProductionOrigin(baseUrl: string): string {
  let parsed: URL;
  try {
    parsed = new URL(baseUrl);
  } catch {
    throw new ProdPreflightError("INVALID_BASE_URL");
  }
  if (
    parsed.protocol !== "https:" ||
    parsed.port !== "" ||
    !PRODUCTION_HOSTS.has(parsed.hostname)
  ) {
    throw new ProdPreflightError("NON_PRODUCTION_HOST");
  }
  return parsed.origin;
}

export function requireProductionApiOrigin(apiUrl: string): string {
  let parsed: URL;
  try {
    parsed = new URL(apiUrl);
  } catch {
    throw new ProdPreflightError("INVALID_BASE_URL");
  }
  if (
    parsed.protocol !== "https:" ||
    parsed.port !== "" ||
    !PRODUCTION_API_HOSTS.has(parsed.hostname)
  ) {
    throw new ProdPreflightError("NON_PRODUCTION_API_HOST");
  }
  return parsed.origin;
}

export function assertProdPreflight(contract: ProdPreflightContract): void {
  requireProductionOrigin(contract.baseUrl);

  syntheticProjectName(contract.runId);

  if (!UUID_RE.test(contract.expectedTenantId)) {
    throw new ProdPreflightError("INVALID_TENANT_ID");
  }
  if (contract.activeTenantId !== contract.expectedTenantId) {
    throw new ProdPreflightError("WRONG_TENANT");
  }
  if (contract.activeOrganizationId !== contract.expectedOrganizationId) {
    throw new ProdPreflightError("WRONG_ORGANIZATION");
  }
  if (!contract.tenantMarkedSynthetic) {
    throw new ProdPreflightError("TENANT_NOT_MARKED_SYNTHETIC");
  }

  requireCommit(contract.expectedBackendSha, "INVALID_BACKEND_SHA");
  requireCommit(contract.observedBackendSha, "INVALID_BACKEND_SHA");
  if (contract.observedBackendSha !== contract.expectedBackendSha) {
    throw new ProdPreflightError("BACKEND_DEPLOYMENT_MISMATCH");
  }

  requireCommit(contract.expectedFrontendSha, "INVALID_FRONTEND_SHA");
  requireCommit(contract.observedFrontendSha, "INVALID_FRONTEND_SHA");
  if (contract.observedFrontendSha !== contract.expectedFrontendSha) {
    throw new ProdPreflightError("FRONTEND_DEPLOYMENT_MISMATCH");
  }

  if (
    !FIXTURE_SHA_RE.test(contract.expectedFixtureSha256) ||
    !FIXTURE_SHA_RE.test(contract.observedFixtureSha256)
  ) {
    throw new ProdPreflightError("INVALID_FIXTURE_SHA");
  }
  if (contract.expectedFixtureSha256 !== contract.observedFixtureSha256) {
    throw new ProdPreflightError("FIXTURE_HASH_MISMATCH");
  }
}

export function requireProdAcceptanceEnv(
  env: Readonly<Record<string, string | undefined>>,
  names: readonly string[],
): Record<string, string> {
  const values: Record<string, string> = {};
  const missing: string[] = [];
  for (const name of names) {
    const value = env[name];
    if (!value) missing.push(name);
    else values[name] = value;
  }
  if (missing.length > 0) {
    // Names are safe to emit; values are deliberately never included.
    throw new Error(`PROD_ACCEPTANCE_MISSING_ENV:${missing.join(",")}`);
  }
  return values;
}
