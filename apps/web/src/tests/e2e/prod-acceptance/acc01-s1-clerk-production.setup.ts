/** Read-only Production Clerk testing-token setup; no user/org provisioning. */
import { clerkSetup } from "@clerk/testing/playwright";
import { test } from "@playwright/test";

test("obtain a bounded Clerk Production testing token", async () => {
  if (process.env.PROD_S1_CONFIRM_READONLY !== "RUN-S1-READONLY") {
    throw new Error("S1_READONLY_NOT_EXPLICITLY_AUTHORIZED");
  }
  if (!process.env.CLERK_SECRET_KEY?.startsWith("sk_live_")) {
    throw new Error("S1_READONLY_REQUIRES_PRODUCTION_CLERK_KEY");
  }
  if (!process.env.CLERK_PUBLISHABLE_KEY?.startsWith("pk_live_")) {
    throw new Error("S1_READONLY_REQUIRES_PRODUCTION_CLERK_PUBLISHABLE_KEY");
  }
  await clerkSetup();
});
