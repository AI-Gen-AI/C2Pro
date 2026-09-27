import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  assertProdPreflight,
  requireProdAcceptanceEnv,
  sha256File,
  syntheticProjectName,
  type ProdPreflightContract,
} from "../../../../../lib/prod-acceptance/preflight";

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const PROD_ACCEPTANCE_FIXTURE = path.resolve(
  HERE,
  "../../test-data/sample-contract.pdf",
);
export const PROD_ACCEPTANCE_FIXTURE_SHA256 =
  "f0bc7170cf002570be58f9225f9affc534720a4756fa1da39ae7ad328d63a9b9";

export const PROD_ACCEPTANCE_REQUIRED_ENV = [
  "PROD_ACCEPTANCE_RUN_ID",
  "PROD_ACCEPTANCE_BASE_URL",
  "PROD_ACCEPTANCE_EXPECTED_TENANT_ID",
  "PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID",
  "PROD_ACCEPTANCE_CLERK_EMAIL",
  "PROD_ACCEPTANCE_CLERK_PASSWORD",
  "PROD_ACCEPTANCE_EXPECTED_BACKEND_SHA",
  "PROD_ACCEPTANCE_OBSERVED_BACKEND_SHA",
  "PROD_ACCEPTANCE_EXPECTED_FRONTEND_SHA",
  "PROD_ACCEPTANCE_OBSERVED_FRONTEND_SHA",
] as const;

export interface BrowserIdentityFacts {
  activeTenantId: string | null;
  activeOrganizationId: string | null;
}

export function buildSyntheticProjectName(env: NodeJS.ProcessEnv = process.env): string {
  const values = requireProdAcceptanceEnv(env, ["PROD_ACCEPTANCE_RUN_ID"]);
  return syntheticProjectName(values.PROD_ACCEPTANCE_RUN_ID);
}

export function assertProductionJourneyPreflight(
  facts: BrowserIdentityFacts,
  tenantMarkedSynthetic: boolean,
  env: NodeJS.ProcessEnv = process.env,
): void {
  const values = requireProdAcceptanceEnv(env, PROD_ACCEPTANCE_REQUIRED_ENV);
  const contract: ProdPreflightContract = {
    baseUrl: values.PROD_ACCEPTANCE_BASE_URL,
    runId: values.PROD_ACCEPTANCE_RUN_ID,
    expectedTenantId: values.PROD_ACCEPTANCE_EXPECTED_TENANT_ID,
    activeTenantId: facts.activeTenantId,
    expectedOrganizationId: values.PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID,
    activeOrganizationId: facts.activeOrganizationId,
    tenantMarkedSynthetic,
    expectedBackendSha: values.PROD_ACCEPTANCE_EXPECTED_BACKEND_SHA,
    observedBackendSha: values.PROD_ACCEPTANCE_OBSERVED_BACKEND_SHA,
    expectedFrontendSha: values.PROD_ACCEPTANCE_EXPECTED_FRONTEND_SHA,
    observedFrontendSha: values.PROD_ACCEPTANCE_OBSERVED_FRONTEND_SHA,
    expectedFixtureSha256: PROD_ACCEPTANCE_FIXTURE_SHA256,
    observedFixtureSha256: sha256File(PROD_ACCEPTANCE_FIXTURE),
  };
  assertProdPreflight(contract);
}
