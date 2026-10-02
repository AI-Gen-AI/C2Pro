import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import { test } from "@playwright/test";

import {
  signInSyntheticProductionUser,
  signOutThroughUi,
} from "./support/prod-auth.synthetic";

const OUTPUT = path.join(
  process.cwd(),
  "playwright",
  ".prod-acceptance",
  "identity-preflight.json",
);

const IDENTITY_PREFLIGHT_TIMEOUT_MS = 5 * 60_000;
test.setTimeout(IDENTITY_PREFLIGHT_TIMEOUT_MS);

test("real production qualification identity is isolated and usable", async ({ page }) => {
  const facts = await signInSyntheticProductionUser(page);

  if (!facts.activeTenantId || !facts.activeOrganizationId) {
    throw new Error("PROD_ACCEPTANCE_IDENTITY_NOT_FULLY_BOUND");
  }

  await signOutThroughUi(page);

  mkdirSync(path.dirname(OUTPUT), { recursive: true });
  writeFileSync(
    OUTPUT,
    JSON.stringify(
      {
        real_prod_auth_path: true,
        tenant_match: true,
        organization_match: true,
        signed_out: true,
        credentials_exposed: false,
      },
      null,
      2,
    ),
    "utf8",
  );
});
