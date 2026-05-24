import { test as setup } from "@playwright/test";
import { clerkSetup } from "@clerk/testing/playwright";

setup("global setup", async () => {
  await clerkSetup();
});
