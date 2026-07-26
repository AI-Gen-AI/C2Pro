import { expect, test as setup } from "@playwright/test";
import { clerk, setupClerkTestingToken } from "@clerk/testing/playwright";

const authFile = "playwright/.auth/user.json";

setup("authenticate", async ({ page }) => {
  await setupClerkTestingToken({ page });
  await page.goto("/");
  await clerk.signIn({
    page,
    signInParams: {
      strategy: "password",
      identifier: "testuser@c2pro.com",
      password: "Testpasword123",
    },
  });

  await page.goto("/projects");
  await expect(page.locator('h1:has-text("Projects")')).toBeVisible();
  await page.context().storageState({ path: authFile });
});
